#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <SensirionI2cScd4x.h>
#include <ESP8266WiFi.h>
#include <time.h>
#include "secrets.h"

// Europe/Podgorica
#define TZ_INFO "CET-1CEST,M3.5.0,M10.5.0/3"
// Wi-Fi: scan for known networks and join the strongest one
#define WIFI_CONNECT_TIMEOUT_MS 60000
#ifndef WIFI_PASSWORD_2
#define WIFI_PASSWORD_2 WIFI_PASSWORD
#endif
// Night mode: no beeps, no LEDs, no blinking
#define NIGHT_FROM_HOUR 21
#define NIGHT_TO_HOUR 9
// OLED contrast, 0..255. With the library default VCOMH (0x40) contrast barely
// changes brightness; VCOMH 0x00 gives the widest usable range
#define OLED_VCOMH 0x00
#define OLED_PRECHARGE 0xF1
#define CONTRAST_DAY 200
#define CONTRAST_NIGHT 1

// HW-364A: onboard OLED wired to SDA=GPIO14 (D5), SCL=GPIO12 (D6)
#define I2C_SDA 14
#define I2C_SCL 12
// SCD41 shares the bus with the OLED. If its SDA/SCL wires are ever crossed,
// swap these two: the bus is switched to them around every sensor transaction
#define SCD41_SDA I2C_SDA
#define SCD41_SCL I2C_SCL
#define OLED_ADDR 0x3C

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
// Top 16 rows of the panel are yellow, the rest is blue
#define HEADER_HEIGHT 16

// Active buzzer (TMB12A05) driven through an NPN transistor
#define BUZZER_PIN 13
#define CO2_ALERT_ON 1200
#define CO2_ALERT_OFF 1000
#define ALERT_MIN_INTERVAL_MS (5UL * 60 * 1000)

// Button to GND: short press toggles sound, long press toggles the display
#define BUTTON_PIN 0
#define BUTTON_DEBOUNCE_MS 30
#define BUTTON_LONG_MS 1000
#define BUTTON_DOUBLE_MS 400
#define LED_TEST_MS 1000
#define TOAST_MS 1500

#define LED_YELLOW_PIN 5
#define LED_RED_PIN 4
#define CO2_WARN 1000
#define WARN_BLINK_MS 500
#define ALERT_BLINK_MS 200

// Trend graph on the right of the blue area; each bar averages SAMPLES_PER_BAR
// measurements (~5 s each), so 17 bars of one sample cover ~85 s
#define GRAPH_X 76
#define GRAPH_W (SCREEN_WIDTH - GRAPH_X)
#define GRAPH_TOP (HEADER_HEIGHT + 2)
#define GRAPH_H (SCREEN_HEIGHT - GRAPH_TOP)
#define GRAPH_MIN_SPAN 50
#define BAR_W 2
#define BAR_GAP 1
#define BAR_COUNT ((GRAPH_W + BAR_GAP) / (BAR_W + BAR_GAP))
#define SAMPLES_PER_BAR 1

// CO2 readings are unreliable right after start; hide them behind a countdown
#define WARMUP_MS (2UL * 60 * 1000)
#define WARMUP_CX 30
#define WARMUP_CY 37
#define WARMUP_R 17

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
SensirionI2cScd4x scd4x;

bool sensorOk = false;
uint16_t co2 = 0;
float temperature = 0, humidity = 0;
bool hasData = false;
uint32_t warmupStart = 0;
bool alertActive = false;
bool alertBeeped = false;
uint32_t lastAlertBeep = 0;
// Runtime mute switch, toggled over MQTT or the button and kept in EEPROM
bool buzzerEnabled = false;
bool ledsEnabled = true;
uint32_t ledTestStart = 0;
bool ledTest = false;
bool displayOn = true;
const char *toastText = nullptr;
uint32_t toastStart = 0;

// Last entry is the bar still being filled, updated on every sample
uint16_t history[BAR_COUNT];
uint8_t historyLen = 0;
uint32_t barSum = 0;
uint8_t barSamples = 0;

void pushHistory(uint16_t value) {
  if (barSamples == 0) {
    if (historyLen < BAR_COUNT) {
      historyLen++;
    } else {
      memmove(history, history + 1, (BAR_COUNT - 1) * sizeof(history[0]));
    }
  }
  barSum += value;
  barSamples++;
  history[historyLen - 1] = barSum / barSamples;
  if (barSamples == SAMPLES_PER_BAR) {
    barSum = 0;
    barSamples = 0;
  }
}

struct WifiNetwork {
  const char *ssid;
  const char *password;
};

const WifiNetwork WIFI_NETWORKS[] = {
  {WIFI_SSID, WIFI_PASSWORD},
#ifdef WIFI_SSID_2
  {WIFI_SSID_2, WIFI_PASSWORD_2},
#endif
};

// While disconnected, scan in the background and join the known network with the best signal;
// if it does not connect in time, scan again. A weak signal can take 30-40 s to join
void wifiLoop() {
  static uint32_t lastAttempt = 0;
  static bool attempted = false;
  if (WiFi.status() == WL_CONNECTED) return;
  if (attempted && millis() - lastAttempt < WIFI_CONNECT_TIMEOUT_MS) return;

  int8_t found = WiFi.scanComplete();
  if (found == WIFI_SCAN_RUNNING) return;
  if (found < 0) {
    WiFi.scanNetworks(true);
    return;
  }

  int best = -1;
  const WifiNetwork *network = nullptr;
  for (int i = 0; i < found; i++) {
    for (const WifiNetwork &n : WIFI_NETWORKS) {
      if (WiFi.SSID(i) == n.ssid && (best < 0 || WiFi.RSSI(i) > WiFi.RSSI(best))) {
        best = i;
        network = &n;
      }
    }
  }
  attempted = true;
  lastAttempt = millis();
  if (best < 0) {
    Serial.println("WiFi: no known networks found");
  } else {
    Serial.printf("WiFi: joining %s, RSSI %d\n", network->ssid, WiFi.RSSI(best));
    WiFi.begin(network->ssid, network->password);
  }
  WiFi.scanDelete();
}

// Until NTP time is known, stay quiet as if it were night
bool isNight() {
  time_t now = time(nullptr);
  if (now < 1700000000) return true;
  struct tm local;
  localtime_r(&now, &local);
  return local.tm_hour >= NIGHT_FROM_HOUR || local.tm_hour < NIGHT_TO_HOUR;
}

void beep(uint16_t ms, uint8_t times = 1, uint16_t gap = 150) {
  if (!buzzerEnabled || isNight()) return;
  for (uint8_t i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(ms);
    digitalWrite(BUZZER_PIN, LOW);
    if (i + 1 < times) delay(gap);
  }
}

// Beep once on entering the alert zone; re-armed only after CO2 drops below CO2_ALERT_OFF,
// and never more often than ALERT_MIN_INTERVAL_MS
void updateAlert() {
  if (!alertActive && co2 >= CO2_ALERT_ON) {
    alertActive = true;
    if (!alertBeeped || millis() - lastAlertBeep >= ALERT_MIN_INTERVAL_MS) {
      alertBeeped = true;
      lastAlertBeep = millis();
      beep(70, 3);
    }
  } else if (alertActive && co2 < CO2_ALERT_OFF) {
    alertActive = false;
  }
}

void updateLeds() {
  static uint32_t lastNightCheck = 0;
  static bool night = true;
  if (millis() - lastNightCheck >= 1000) {
    lastNightCheck = millis();
    night = isNight();
  }
  // Both LEDs light up briefly when they are switched on, day or night
  if (ledTest && millis() - ledTestStart < LED_TEST_MS) {
    digitalWrite(LED_YELLOW_PIN, HIGH);
    digitalWrite(LED_RED_PIN, HIGH);
    return;
  }
  ledTest = false;
  if (night || !ledsEnabled) {
    digitalWrite(LED_YELLOW_PIN, LOW);
    digitalWrite(LED_RED_PIN, LOW);
    return;
  }

  bool warn = hasData && !alertActive && co2 >= CO2_WARN;
  bool yellowOn = warn && (millis() / WARN_BLINK_MS) % 2;
  bool redOn = alertActive && (millis() / ALERT_BLINK_MS) % 2;
  digitalWrite(LED_YELLOW_PIN, yellowOn);
  digitalWrite(LED_RED_PIN, redOn);
}

void showToast(const char *text) {
  toastText = text;
  toastStart = millis();
}

void toggleSound() {
  buzzerEnabled = !buzzerEnabled;
  saveSettings();
  publishBuzzerState();
  Serial.printf("Button: sound %s\n", buzzerEnabled ? "on" : "off");
  showToast(buzzerEnabled ? "sound on" : "sound off");
  drawScreen();
  beep(30);
}

void toggleLeds() {
  ledsEnabled = !ledsEnabled;
  saveSettings();
  Serial.printf("Button: leds %s\n", ledsEnabled ? "on" : "off");
  showToast(ledsEnabled ? "leds on" : "leds off");
  drawScreen();
  if (ledsEnabled) {
    ledTest = true;
    ledTestStart = millis();
  }
}

void toggleDisplay() {
  displayOn = !displayOn;
  Serial.printf("Button: display %s\n", displayOn ? "on" : "off");
  display.ssd1306_command(displayOn ? SSD1306_DISPLAYON : SSD1306_DISPLAYOFF);
  if (displayOn) drawScreen();
}

// Long press fires as soon as it is held long enough. A short press waits BUTTON_DOUBLE_MS
// after release for a second one: single toggles sound, double toggles the LEDs
void handleButton() {
  static bool lastRaw = HIGH, pressed = false, longDone = false, shortPending = false;
  static uint32_t changedAt = 0, pressedAt = 0, releasedAt = 0;

  if (shortPending && !pressed && millis() - releasedAt >= BUTTON_DOUBLE_MS) {
    shortPending = false;
    toggleSound();
  }

  bool raw = digitalRead(BUTTON_PIN);
  if (raw != lastRaw) {
    lastRaw = raw;
    changedAt = millis();
  }
  if (millis() - changedAt < BUTTON_DEBOUNCE_MS) return;

  bool down = lastRaw == LOW;
  if (!pressed && down) {
    pressed = true;
    longDone = false;
    pressedAt = millis();
  } else if (pressed && down && !longDone && millis() - pressedAt >= BUTTON_LONG_MS) {
    longDone = true;
    shortPending = false;
    toggleDisplay();
  } else if (pressed && !down) {
    pressed = false;
    if (longDone) return;
    if (shortPending) {
      shortPending = false;
      toggleLeds();
    } else {
      shortPending = true;
      releasedAt = millis();
    }
  }
}

void printError(const char *what, int16_t error) {
  char msg[64];
  errorToString(error, msg, sizeof(msg));
  Serial.printf("%s: %s\n", what, msg);
}

void drawHeader(const char *title) {
  display.setTextSize(1);
  display.setCursor(0, 4);
  display.print(title);
  drawWifiIcon(49, 2);
  drawClockIcon(63, 3);
  if (!buzzerEnabled) drawMuteIcon(75, 3);
  if (alertActive) {
    display.setCursor(SCREEN_WIDTH - 6 * 4, 4);
    display.print("HIGH");
    // Screen is redrawn once per second, so the icon toggles on every redraw
    static bool iconOn = false;
    iconOn = !iconOn;
    if (iconOn || isNight()) drawWarningIcon(SCREEN_WIDTH - 6 * 4 - 17, 1);
  }
}

// 11x10 signal bars by RSSI; a cross when Wi-Fi is down
void drawWifiIcon(int x, int y) {
  if (WiFi.status() != WL_CONNECTED) {
    display.drawLine(x + 1, y + 2, x + 7, y + 8, SSD1306_WHITE);
    display.drawLine(x + 7, y + 2, x + 1, y + 8, SSD1306_WHITE);
    return;
  }
  int rssi = WiFi.RSSI();
  int level = rssi > -60 ? 4 : rssi > -70 ? 3 : rssi > -80 ? 2 : 1;
  for (int i = 0; i < 4; i++) {
    int h = 3 + i * 2;
    int bx = x + i * 3;
    if (i < level) {
      display.fillRect(bx, y + 10 - h, 2, h, SSD1306_WHITE);
    } else {
      display.drawFastHLine(bx, y + 9, 2, SSD1306_WHITE);
    }
  }
}

// 9x9 clock; blinks until NTP time is known
void drawClockIcon(int x, int y) {
  if (time(nullptr) < 1700000000 && (millis() / 1000) % 2) return;
  display.drawCircle(x + 4, y + 4, 4, SSD1306_WHITE);
  display.drawFastVLine(x + 4, y + 2, 3, SSD1306_WHITE);
  display.drawFastHLine(x + 4, y + 4, 3, SSD1306_WHITE);
}

// 11x9 speaker with a cross
void drawMuteIcon(int x, int y) {
  display.fillRect(x, y + 3, 2, 3, SSD1306_WHITE);
  display.fillTriangle(x + 2, y + 4, x + 5, y, x + 5, y + 8, SSD1306_WHITE);
  display.drawLine(x + 7, y + 2, x + 10, y + 6, SSD1306_WHITE);
  display.drawLine(x + 10, y + 2, x + 7, y + 6, SSD1306_WHITE);
}

// 13x13 warning triangle with an exclamation mark cut out
void drawWarningIcon(int x, int y) {
  display.fillTriangle(x, y + 12, x + 12, y + 12, x + 6, y, SSD1306_WHITE);
  display.drawFastVLine(x + 6, y + 4, 4, SSD1306_BLACK);
  display.drawPixel(x + 6, y + 10, SSD1306_BLACK);
}

void drawGraph() {
  if (historyLen < 2) return;

  uint16_t lo = history[0], hi = history[0];
  for (uint8_t i = 1; i < historyLen; i++) {
    lo = min(lo, history[i]);
    hi = max(hi, history[i]);
  }
  // Keep sensor noise from filling the whole height
  if (hi - lo < GRAPH_MIN_SPAN) {
    uint16_t mid = (lo + hi) / 2;
    lo = mid > GRAPH_MIN_SPAN / 2 ? mid - GRAPH_MIN_SPAN / 2 : 0;
    hi = lo + GRAPH_MIN_SPAN;
  }

  // Newest bar on the right edge
  for (uint8_t i = 0; i < historyLen; i++) {
    int x = SCREEN_WIDTH - BAR_W - (historyLen - 1 - i) * (BAR_W + BAR_GAP);
    int h = 1 + (long)(history[i] - lo) * (GRAPH_H - 1) / (hi - lo);
    display.fillRect(x, SCREEN_HEIGHT - h, BAR_W, h, SSD1306_WHITE);
  }
}

bool warmingUp() {
  return millis() - warmupStart < WARMUP_MS;
}

// Pie countdown: the filled sector shrinks clockwise from 12 o'clock
void drawWarmup() {
  float remaining = 1.0f - (float)(millis() - warmupStart) / WARMUP_MS;
  display.drawCircle(WARMUP_CX, WARMUP_CY, WARMUP_R, SSD1306_WHITE);

  const float step = 6 * DEG_TO_RAD;
  float end = remaining * TWO_PI;
  for (float a = 0; a < end; a += step) {
    float b = min(a + step, end);
    display.fillTriangle(
        WARMUP_CX, WARMUP_CY,
        WARMUP_CX + WARMUP_R * sin(a), WARMUP_CY - WARMUP_R * cos(a),
        WARMUP_CX + WARMUP_R * sin(b), WARMUP_CY - WARMUP_R * cos(b),
        SSD1306_WHITE);
  }
}

void updateContrast() {
  static int8_t lastNight = -1;
  bool night = isNight();
  if (night == lastNight) return;
  lastNight = night;
  display.ssd1306_command(SSD1306_SETCONTRAST);
  display.ssd1306_command(night ? CONTRAST_NIGHT : CONTRAST_DAY);
}

void logTimeOnce() {
  static bool logged = false;
  time_t now = time(nullptr);
  if (logged || now < 1700000000) return;
  logged = true;
  struct tm local;
  localtime_r(&now, &local);
  Serial.printf("Time synced: %02d:%02d, %s mode\n", local.tm_hour, local.tm_min, isNight() ? "night" : "day");
}

void drawToast() {
  if (!toastText) return;
  if (millis() - toastStart >= TOAST_MS) {
    toastText = nullptr;
    return;
  }
  int w = 6 * strlen(toastText) + 12;
  int x = (SCREEN_WIDTH - w) / 2;
  int y = HEADER_HEIGHT + 10;
  display.fillRect(x, y, w, 18, SSD1306_BLACK);
  display.drawRect(x, y, w, 18, SSD1306_WHITE);
  display.setTextSize(1);
  display.setCursor(x + 6, y + 5);
  display.print(toastText);
}

void drawScreen() {
  if (!displayOn) return;
  updateContrast();
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  drawHeader("CO2 ppm");

  if (!sensorOk) {
    display.setCursor(0, HEADER_HEIGHT + 8);
    display.println("SCD41 not found");
    display.println("check wiring");
  } else if (!hasData) {
    display.setCursor(0, HEADER_HEIGHT + 8);
    display.println("warming up...");
  } else {
    if (warmingUp()) {
      drawWarmup();
    } else {
      // Size 3 fits 4 digits next to the graph; 5 digits need size 2
      display.setTextSize(co2 < 10000 ? 3 : 2);
      display.setCursor(0, HEADER_HEIGHT + 6);
      display.print(co2);
    }

    display.setTextSize(1);
    display.setCursor(0, SCREEN_HEIGHT - 8);
    display.print(temperature, 1);
    display.write(248);  // degree sign in CP437
    display.printf("C %.0f%%", humidity);

    drawGraph();
  }
  drawToast();
  display.display();
}

void sensorBus() {
  Wire.begin(SCD41_SDA, SCD41_SCL);
}

void displayBus() {
  Wire.begin(I2C_SDA, I2C_SCL);
}

void setupSensor() {
  scd4x.begin(Wire, SCD41_I2C_ADDR_62);

  // Sensor may still be measuring after an MCU reset
  scd4x.wakeUp();
  scd4x.stopPeriodicMeasurement();
  scd4x.reinit();

  uint64_t serial = 0;
  int16_t error = scd4x.getSerialNumber(serial);
  if (error) {
    printError("getSerialNumber", error);
    return;
  }
  Serial.printf("SCD41 serial: 0x%04X%08X\n", (uint32_t)(serial >> 32), (uint32_t)serial);

  error = scd4x.startPeriodicMeasurement();
  if (error) {
    printError("startPeriodicMeasurement", error);
    return;
  }
  sensorOk = true;
  warmupStart = millis();
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();

  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(LED_YELLOW_PIN, OUTPUT);
  pinMode(LED_RED_PIN, OUTPUT);
  pinMode(BUTTON_PIN, INPUT_PULLUP);

  // Wi-Fi for NTP time and MQTT; connects in the background
  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  configTime(TZ_INFO, "pool.ntp.org", "time.google.com");
  setupMqtt();

  Wire.begin(I2C_SDA, I2C_SCL);

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    Serial.println("SSD1306 init failed");
  }
  // Use the correct CP437 code points for symbols like the degree sign
  display.cp437(true);
  display.ssd1306_command(SSD1306_SETVCOMDETECT);
  display.ssd1306_command(OLED_VCOMH);
  display.ssd1306_command(SSD1306_SETPRECHARGE);
  display.ssd1306_command(OLED_PRECHARGE);

  sensorBus();
  setupSensor();
  displayBus();
  drawScreen();
  beep(50);
}

void loop() {
  handleButton();
  updateLeds();
  wifiLoop();
  mqttLoop();

  static uint32_t lastPoll = 0;
  if (millis() - lastPoll < 1000) return;
  lastPoll = millis();
  logTimeOnce();

  if (sensorOk) {
    bool ready = false;
    sensorBus();
    int16_t error = scd4x.getDataReadyStatus(ready);
    if (error) {
      printError("getDataReadyStatus", error);
    } else if (ready) {
      uint16_t c;
      float t, h;
      error = scd4x.readMeasurement(c, t, h);
      if (error) {
        printError("readMeasurement", error);
      } else if (c > 0) {
        temperature = t;
        humidity = h;
        hasData = true;
        Serial.printf("CO2: %u ppm, T: %.1f C, RH: %.1f %%%s\n", c, t, h, warmingUp() ? " (warmup)" : "");
        if (!warmingUp()) {
          co2 = c;
          pushHistory(co2);
          updateAlert();
          publishMeasurement();
        }
      }
    }
    displayBus();
  }

  drawScreen();
}
