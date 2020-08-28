#include <Arduino.h>

#include <string>

#include "display.h"
#include "fingerprint.h"
#include "mqtt.h"
#include "wifi.h"

#define ADC_EN 14
#define ADC_PIN 34

// #include <Button2.h>
// #define BUTTON_1 35
// #define BUTTON_2 0

void setup() {
  Serial.begin(115200);
  Serial.println("Serial.begin");

  fingerprint::Setup();  // go early since the others display status on our LED
  display::Setup();
  display::Message("Hello world");
  wifi::Setup();
  mqtt::Setup();
}

namespace {
uint16_t LastComponentNumber(const std::string &s) {
  return atoi(s.substr(s.rfind("/") + 1).c_str());
}
}  // namespace

void HandleCommand(const std::string &payload_string) {
  if (payload_string == "enroll") {
    fingerprint::Enroll();
  } else if (payload_string == "show_success") {
    fingerprint::BlinkSuccess();
    while (!mqtt::HasPendingMessage()) yield();
    mqtt::PopPendingMessage();
    // hope it's "clear_success", but who cares
    fingerprint::BlinkClearSuccess();
  } else if (payload_string == "delete_all") {
    fingerprint::DeleteAll();
  } else if (payload_string.rfind("delete/model/", 0) == 0) {
    uint16_t fid = LastComponentNumber(payload_string);
    fingerprint::DeleteModel(fid);
  } else if (payload_string.rfind("get/model/", 0) == 0) {
    uint16_t fid = LastComponentNumber(payload_string);
    fingerprint::DownloadModel(fid);
  }
}

void loop() {
  Serial.println("--loop--");

  fingerprint::ExecuteAnyQueued();

  fingerprint::ScanLoop();

  if (mqtt::HasPendingMessage()) {
    std::pair<std::string, std::vector<byte>> msg = mqtt::PopPendingMessage();
    const std::string &topic = msg.first;
    const std::vector<byte> &payload = msg.second;

    if (topic == "fingerprint/command") {
      const std::string payload_string(payload.begin(), payload.end());
      HandleCommand(payload_string);
    } else if (topic.rfind("fingerprint/set/model/", 0) == 0) {
      uint16_t fid = LastComponentNumber(topic);

      fingerprint::SetModel(fid, payload);
    }
  }
}
