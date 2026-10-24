#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

struct PinPair { uint8_t sda; uint8_t scl; };

// Common SDA/SCL wiring on ESP8266 boards with an onboard OLED
const PinPair candidates[] = {
  {14, 12},  // D6/D5
  {12, 14},  // D5/D6
  {4, 5},    // D2/D1
  {5, 4},    // D1/D2
  {2, 14},   // D4/D5
  {0, 2},    // D3/D4
};

uint8_t oledAddr = 0;
PinPair found = {0, 0};

bool probe(uint8_t addr) {
  Wire.beginTransmission(addr);
  return Wire.endTransmission() == 0;
}

bool findDisplay() {
  for (const PinPair &p : candidates) {
    Wire.begin(p.sda, p.scl);
    for (uint8_t addr : {0x3C, 0x3D}) {
      if (probe(addr)) {
        found = p;
        oledAddr = addr;
        return true;
      }
    }
  }
  return false;
}

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println();
  Serial.println("OLED test start");

  if (!findDisplay()) {
    Serial.println("OLED not found on any candidate pins");
    return;
  }
  Serial.printf("OLED found: addr=0x%02X SDA=GPIO%d SCL=GPIO%d\n", oledAddr, found.sda, found.scl);

  if (!display.begin(SSD1306_SWITCHCAPVCC, oledAddr)) {
    Serial.println("SSD1306 init failed");
    return;
  }

  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(0, 0);
  display.println("Hello!");
  display.setTextSize(1);
  display.printf("addr 0x%02X\n", oledAddr);
  display.printf("SDA %d  SCL %d\n", found.sda, found.scl);
  display.print("chip ");
  display.println(ESP.getChipId(), HEX);
  display.drawRect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, SSD1306_WHITE);
  display.display();
  delay(3000);
}

void loop() {
  if (!oledAddr) {
    delay(1000);
    return;
  }

  static int x = 0, dx = 3;
  static uint32_t frames = 0;

  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.printf("uptime %lus\n", millis() / 1000);
  display.printf("frames %lu\n", frames++);
  display.printf("heap %u\n", ESP.getFreeHeap());
  display.fillCircle(x, 50, 8, SSD1306_WHITE);
  display.drawLine(0, 63, SCREEN_WIDTH - 1, 63, SSD1306_WHITE);
  display.display();

  x += dx;
  if (x < 8 || x > SCREEN_WIDTH - 9) dx = -dx;
  delay(30);
}
