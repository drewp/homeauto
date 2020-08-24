#include "display.h"

#include <TFT_eSPI.h>
#include <Wire.h>

// see https://github.com/JakubAndrysek/TTGO_T_Display

namespace display {

TFT_eSPI tft(135, 240);

void Setup() {
  tft.init();
  tft.fontHeight(2);
  tft.setRotation(1);
  tft.fillScreen(TFT_BLACK);
}

void Message(std::string msg) {
  tft.drawString(msg.c_str(), tft.width() / 4, tft.height() / 2,
                 4);  // string,start x,start y, font weight {1;2;4;6;7;8}
}

}