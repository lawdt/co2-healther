// MQTT with Home Assistant discovery: CO2/temperature/humidity sensors,
// alert binary sensor, a switch for the buzzer and the night mode hours

#include <PubSubClient.h>
#include <EEPROM.h>

#define DEVICE_ID "co2monitor"
#define TOPIC_BASE DEVICE_ID
#define TOPIC_STATUS TOPIC_BASE "/status"
#define TOPIC_STATE TOPIC_BASE "/state"
#define TOPIC_BUZZER_SET TOPIC_BASE "/buzzer/set"
#define TOPIC_BUZZER_STATE TOPIC_BASE "/buzzer/state"
#define TOPIC_NIGHT_FROM_SET TOPIC_BASE "/night_from/set"
#define TOPIC_NIGHT_FROM_STATE TOPIC_BASE "/night_from/state"
#define TOPIC_NIGHT_TO_SET TOPIC_BASE "/night_to/set"
#define TOPIC_NIGHT_TO_STATE TOPIC_BASE "/night_to/state"
#define DISCOVERY_PREFIX "homeassistant"

#define MQTT_PUBLISH_MS 30000
#define MQTT_RETRY_MS 10000

// EEPROM layout: magic byte, buzzer flag, LEDs flag, night start hour, night end hour.
// Bytes added later read as 0xFF on older layouts: LEDs on, default night hours
#define EEPROM_MAGIC 0xC2

WiFiClient net;
PubSubClient mqtt(net);

void loadSettings() {
  EEPROM.begin(8);
  if (EEPROM.read(0) == EEPROM_MAGIC) {
    buzzerEnabled = EEPROM.read(1);
    ledsEnabled = EEPROM.read(2) != 0;
    uint8_t from = EEPROM.read(3), to = EEPROM.read(4);
    if (from < 24 && to < 24) {
      nightFrom = from;
      nightTo = to;
    }
  }
}

void saveSettings() {
  EEPROM.write(0, EEPROM_MAGIC);
  EEPROM.write(1, buzzerEnabled);
  EEPROM.write(2, ledsEnabled);
  EEPROM.write(3, nightFrom);
  EEPROM.write(4, nightTo);
  EEPROM.commit();
}

void publishBuzzerState() {
  mqtt.publish(TOPIC_BUZZER_STATE, buzzerEnabled ? "ON" : "OFF", true);
}

void publishNightHours() {
  char value[4];
  snprintf(value, sizeof(value), "%u", nightFrom);
  mqtt.publish(TOPIC_NIGHT_FROM_STATE, value, true);
  snprintf(value, sizeof(value), "%u", nightTo);
  mqtt.publish(TOPIC_NIGHT_TO_STATE, value, true);
}

void publishDiscovery(const char *component, const char *key, const char *extra) {
  char topic[96];
  snprintf(topic, sizeof(topic), DISCOVERY_PREFIX "/%s/" DEVICE_ID "/%s/config", component, key);

  char payload[640];
  snprintf(payload, sizeof(payload),
           "{\"unique_id\":\"" DEVICE_ID "_%s\",\"object_id\":\"" DEVICE_ID "_%s\","
           "\"availability_topic\":\"" TOPIC_STATUS "\",%s,"
           "\"device\":{\"identifiers\":[\"" DEVICE_ID "\"],\"name\":\"CO2 Monitor\","
           "\"model\":\"ESP8266 + SCD41\",\"manufacturer\":\"DIY\"}}",
           key, key, extra);
  mqtt.publish(topic, payload, true);
}

void publishAllDiscovery() {
  publishDiscovery("sensor", "co2",
                   "\"name\":\"CO2\",\"state_topic\":\"" TOPIC_STATE "\","
                   "\"value_template\":\"{{ value_json.co2 }}\",\"unit_of_measurement\":\"ppm\","
                   "\"device_class\":\"carbon_dioxide\",\"state_class\":\"measurement\"");
  publishDiscovery("sensor", "temperature",
                   "\"name\":\"Temperature\",\"state_topic\":\"" TOPIC_STATE "\","
                   "\"value_template\":\"{{ value_json.temperature }}\",\"unit_of_measurement\":\"°C\","
                   "\"device_class\":\"temperature\",\"state_class\":\"measurement\"");
  publishDiscovery("sensor", "humidity",
                   "\"name\":\"Humidity\",\"state_topic\":\"" TOPIC_STATE "\","
                   "\"value_template\":\"{{ value_json.humidity }}\",\"unit_of_measurement\":\"%\","
                   "\"device_class\":\"humidity\",\"state_class\":\"measurement\"");
  publishDiscovery("binary_sensor", "alert",
                   "\"name\":\"CO2 alert\",\"state_topic\":\"" TOPIC_STATE "\","
                   "\"value_template\":\"{{ 'ON' if value_json.alert else 'OFF' }}\","
                   "\"device_class\":\"problem\"");
  publishDiscovery("switch", "buzzer",
                   "\"name\":\"Buzzer\",\"command_topic\":\"" TOPIC_BUZZER_SET "\","
                   "\"state_topic\":\"" TOPIC_BUZZER_STATE "\",\"icon\":\"mdi:volume-high\"");
  publishDiscovery("number", "night_from",
                   "\"name\":\"Night from\",\"command_topic\":\"" TOPIC_NIGHT_FROM_SET "\","
                   "\"state_topic\":\"" TOPIC_NIGHT_FROM_STATE "\",\"min\":0,\"max\":23,\"step\":1,"
                   "\"mode\":\"box\",\"unit_of_measurement\":\"h\",\"entity_category\":\"config\","
                   "\"icon\":\"mdi:weather-night\"");
  publishDiscovery("number", "night_to",
                   "\"name\":\"Night to\",\"command_topic\":\"" TOPIC_NIGHT_TO_SET "\","
                   "\"state_topic\":\"" TOPIC_NIGHT_TO_STATE "\",\"min\":0,\"max\":23,\"step\":1,"
                   "\"mode\":\"box\",\"unit_of_measurement\":\"h\",\"entity_category\":\"config\","
                   "\"icon\":\"mdi:weather-sunny\"");
}

// Hour from an MQTT payload like "21" or "21.0"; -1 if it is not 0..23
int parseHour(byte *payload, unsigned int length) {
  char text[8];
  if (length == 0 || length >= sizeof(text)) return -1;
  memcpy(text, payload, length);
  text[length] = 0;
  char *end;
  float value = strtof(text, &end);
  if (end == text || value < 0 || value > 23) return -1;
  return (int)value;
}

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  bool from = strcmp(topic, TOPIC_NIGHT_FROM_SET) == 0;
  if (from || strcmp(topic, TOPIC_NIGHT_TO_SET) == 0) {
    int hour = parseHour(payload, length);
    if (hour >= 0) {
      (from ? nightFrom : nightTo) = hour;
      Serial.printf("MQTT night %02u:00-%02u:00\n", nightFrom, nightTo);
      saveSettings();
    }
    publishNightHours();
    return;
  }
  if (strcmp(topic, TOPIC_BUZZER_SET) != 0) return;

  bool on = length == 2 && memcmp(payload, "ON", 2) == 0;
  Serial.printf("MQTT buzzer -> %s\n", on ? "ON" : "OFF");
  if (on != buzzerEnabled) {
    buzzerEnabled = on;
    saveSettings();
  }
  publishBuzzerState();
}

void setupMqtt() {
  loadSettings();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(768);
  // Keep a dead broker from freezing the display for long
  net.setTimeout(3000);
}

void mqttLoop() {
  static wl_status_t lastWifi = (wl_status_t)-1;
  wl_status_t wifi = WiFi.status();
  if (wifi != lastWifi) {
    lastWifi = wifi;
    Serial.printf("WiFi status %d", wifi);
    if (wifi == WL_CONNECTED) Serial.printf(", %s, IP %s, RSSI %d", WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WiFi.RSSI());
    Serial.println();
  }
  if (wifi != WL_CONNECTED) return;

  if (!mqtt.connected()) {
    static uint32_t lastAttempt = 0;
    if (lastAttempt && millis() - lastAttempt < MQTT_RETRY_MS) return;
    lastAttempt = millis();

    if (!mqtt.connect(DEVICE_ID, MQTT_USER, MQTT_PASSWORD, TOPIC_STATUS, 0, true, "offline")) {
      Serial.printf("MQTT connect failed, state %d\n", mqtt.state());
      return;
    }
    Serial.println("MQTT connected");
    mqtt.publish(TOPIC_STATUS, "online", true);
    publishAllDiscovery();
    publishBuzzerState();
    publishNightHours();
    mqtt.subscribe(TOPIC_BUZZER_SET);
    mqtt.subscribe(TOPIC_NIGHT_FROM_SET);
    mqtt.subscribe(TOPIC_NIGHT_TO_SET);
  }
  mqtt.loop();
}

// Called after every measurement; throttled to MQTT_PUBLISH_MS
void publishMeasurement() {
  static uint32_t lastPublish = 0;
  if (!mqtt.connected()) return;
  if (lastPublish && millis() - lastPublish < MQTT_PUBLISH_MS) return;
  lastPublish = millis();

  char payload[128];
  snprintf(payload, sizeof(payload),
           "{\"co2\":%u,\"temperature\":%.1f,\"humidity\":%.1f,\"alert\":%s}",
           co2, temperature, humidity, alertActive ? "true" : "false");
  mqtt.publish(TOPIC_STATE, payload);
}
