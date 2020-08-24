#ifndef INCLUDED_MQTT
#define INCLUDED_MQTT
#include <AsyncMqttClient.h>

#include <string>

// #include "esp_adc_cal.h"

extern "C" {
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"
}

namespace mqtt {

void Setup();
void Publish(std::string subtopic, std::string msg);
void StopTimer();
void ConnectToMqtt();
bool HasPendingCommand();
std::string PopPendingCommand();

}  // namespace mqtt
#endif