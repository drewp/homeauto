#include "mqtt.h"

#include "config.h"
#include "fingerprint.h"
#include "wifi.h"

namespace mqtt {
AsyncMqttClient mqttClient;
TimerHandle_t mqttReconnectTimer;
std::string pendingCmd = "";

void StopTimer() {
  xTimerStop(mqttReconnectTimer,
             0);  // ensure we don't reconnect to MQTT while reconnecting
                  // to Wi-Fi
}

void Publish(std::string subtopic, std::string msg) {
  std::string topic = "fingerprint/" + subtopic;
  mqttClient.publish(topic.c_str(), 1, /*retain=*/false, msg.c_str());
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
  std::string cmd(payload, len);
  pendingCmd = cmd;
}

bool HasPendingCommand() {
    return pendingCmd != "";
}
std::string PopPendingCommand() {
    std::string cmd = pendingCmd;
    pendingCmd = "";
    return cmd;
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
