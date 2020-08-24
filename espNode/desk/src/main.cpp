#include <Arduino.h>

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

void loop() {
  Serial.println("--loop--");
  fingerprint::ExecuteAnyQueued();
  fingerprint::ScanLoop();
  if (mqtt::HasPendingCommand()) {
    std::string cmd = mqtt::PopPendingCommand();
    if (cmd == "enroll") {
      fingerprint::Enroll();
    } else if (cmd == "show_success") {
      fingerprint::BlinkSuccess();
      while (!mqtt::HasPendingCommand()) yield();
      cmd = mqtt::PopPendingCommand();
      // hope it's "clear_success", but who cares
      fingerprint::BlinkClearSuccess();
    }
  }
}
