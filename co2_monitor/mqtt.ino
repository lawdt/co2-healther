// MQTT with Home Assistant discovery: CO2/temperature/humidity sensors,
// alert binary sensor and a switch for the buzzer

#include <PubSubClient.h>
#include <EEPROM.h>

#define DEVICE_ID "co2monitor"
#define TOPIC_BASE DEVICE_ID
#define TOPIC_STATUS TOPIC_BASE "/status"
#define TOPIC_STATE TOPIC_BASE "/state"
#define TOPIC_BUZZER_SET TOPIC_BASE "/buzzer/set"
#define TOPIC_BUZZER_STATE TOPIC_BASE "/buzzer/state"
#define DISCOVERY_PREFIX "homeassistant"

#define MQTT_PUBLISH_MS 30000
#define MQTT_RETRY_MS 10000

// EEPROM layout: magic byte, buzzer flag, LEDs flag (0xFF on older layouts means on)
#define EEPROM_MAGIC 0xC2

WiFiClient net;
PubSubClient mqtt(net);

void loadSettings() {
  EEPROM.begin(4);
  if (EEPROM.read(0) == EEPROM_MAGIC) {
    buzzerEnabled = EEPROM.read(1);
    ledsEnabled = EEPROM.read(2) != 0;
  }
}

void saveSettings() {
  EEPROM.write(0, EEPROM_MAGIC);
  EEPROM.write(1, buzzerEnabled);
  EEPROM.write(2, ledsEnabled);
  EEPROM.commit();
}

void publishBuzzerState() {
  mqtt.publish(TOPIC_BUZZER_STATE, buzzerEnabled ? "ON" : "OFF", true);
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
}

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
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
    mqtt.subscribe(TOPIC_BUZZER_SET);
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
