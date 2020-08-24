#ifndef INCLUDED_WIFI
#define INCLUDED_WIFI

#include "WiFi.h"
extern "C" {
#include "freertos/FreeRTOS.h"
#include "freertos/timers.h"
}

namespace wifi {
void Setup();
bool IsConnected();
}  // namespace wifi
#endif