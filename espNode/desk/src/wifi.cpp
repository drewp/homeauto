#include "wifi.h"

#include "config.h"
#include "mqtt.h"
#include "fingerprint.h"

namespace wifi {

TimerHandle_t wifiReconnectTimer;
namespace {
void connectToWifi() {
  Serial.println("Connecting to Wi-Fi...");
  fingerprint::BlinkNotConnected();
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}
void WiFiEvent(WiFiEvent_t event) {
  Serial.printf("[WiFi-event] event: %d\n", event);
  switch (event) {
    case SYSTEM_EVENT_STA_GOT_IP:
      Serial.println("WiFi connected");
      Serial.println("IP address: ");
      Serial.println(WiFi.localIP());
      mqtt::ConnectToMqtt();
      break;
    case SYSTEM_EVENT_STA_DISCONNECTED:
      Serial.println("WiFi lost connection");
      mqtt::StopTimer();
      xTimerStart(wifiReconnectTimer, 0);
      break;
    default:
      // ??
      break;
  }
}
}  // namespace
void Setup() {
  wifiReconnectTimer =
      xTimerCreate("wifiTimer", pdMS_TO_TICKS(2000), pdFALSE, (void*)0,
                   reinterpret_cast<TimerCallbackFunction_t>(connectToWifi));

  WiFi.onEvent(WiFiEvent);
  connectToWifi();
}
bool IsConnected() { return WiFi.isConnected(); }
}  // namespace wifi