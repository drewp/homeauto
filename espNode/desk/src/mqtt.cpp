#include "mqtt.h"

#include "config.h"
#include "fingerprint.h"
#include "wifi.h"

namespace mqtt {
AsyncMqttClient mqttClient;
TimerHandle_t mqttReconnectTimer;

#define MAX_INCOMING_PAYLOAD 1536
class IncomingMessage {
 public:
  bool complete;
  std::string topic;
  std::vector<byte> payload;
};
IncomingMessage incomingMessage;

void StopTimer() {
  xTimerStop(mqttReconnectTimer,
             0);  // ensure we don't reconnect to MQTT while reconnecting
                  // to Wi-Fi
}

void Publish(std::string subtopic, std::string msg) {
  std::string topic = "fingerprint/" + subtopic;
  mqttClient.publish(topic.c_str(), 1, /*retain=*/false, msg.data(),
                     msg.size());
  // yield();
}

void ConnectToMqtt() {
  Serial.println("Connecting to MQTT...");
  mqttClient.connect();
}

void SendTemperature() {
  float temp_c = temperatureRead();
  char buf[20];
  snprintf(buf, sizeof(buf), "%.3fC", temp_c);
  mqttClient.publish("fingerprint/temperature", 1, /*retain=*/true, buf);
}
void onMqttConnect(bool sessionPresent) {
  Serial.println("Connected to MQTT.");
  Serial.print("Session present: ");
  Serial.println(sessionPresent);

  mqttClient.subscribe("fingerprint/command", 1);
  mqttClient.subscribe("fingerprint/set/#", 1);

  SendTemperature();

  mqttClient.setWill("fingerprint/status", 1, /*retain=*/true, "offline");
  mqttClient.publish("fingerprint/status", 1, /*retain=*/true, "online");

  Serial.println("queuing a blink change");
  fingerprint::QueueBlinkConnected();
}

void onMqttDisconnect(AsyncMqttClientDisconnectReason reason) {
  Serial.println("Disconnected from MQTT.");
  fingerprint::BlinkNotConnected();

  if (wifi::IsConnected()) {
    xTimerStart(mqttReconnectTimer, 0);
  }
}

void onMqttMessage(char* topic, char* payload,
                   AsyncMqttClientMessageProperties properties, size_t len,
                   size_t index, size_t total) {
  if (index == 0) {
    incomingMessage.complete = false;
    incomingMessage.topic = std::string(topic);
    incomingMessage.payload.clear();
  }

  for (int i = 0; i < len; i++) {
    incomingMessage.payload.push_back(payload[i]);
  }

  if (index + len == total) {
    incomingMessage.complete = true;
  }
}

// Don't do command right away; wait for main loop to ask for it.
bool HasPendingMessage() { return incomingMessage.complete; }
std::pair<std::string, std::vector<byte>> PopPendingMessage() {
  std::pair<std::string, std::vector<byte>> ret{incomingMessage.topic,
                                                incomingMessage.payload};
  incomingMessage.complete = false;
  return ret;
}

void Setup() {
  mqttReconnectTimer =
      xTimerCreate("mqttTimer", pdMS_TO_TICKS(2000), pdFALSE, (void*)0,
                   reinterpret_cast<TimerCallbackFunction_t>(ConnectToMqtt));

  mqttClient.onConnect(onMqttConnect);
  mqttClient.onDisconnect(onMqttDisconnect);
  mqttClient.onMessage(onMqttMessage);
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
}

}  // namespace mqtt
