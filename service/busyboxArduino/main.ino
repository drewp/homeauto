/*
D0 <---------
D1 lcd rw
D2 <---------
D3 ir out -----
D4 lcd 4
D5 lcd 5
D6 lcd 6
D7 lcd 7
D8 lcd rs
D9 lcd en
D10 lcd backlight
D11 tbd <------------ 
D12 motion in <--------
D13 debug led <--------

 */
#include <Arduino.h>
#include <LiquidCrystal.h>
#include "DFR_Key.h"
#include "IRremote.h"

#define motionIn 12


// see http://www.dfrobot.com/image/data/DFR0009/LCDKeypad%20Shield%20V1.0%20SCH.pdf
#define I2C_ADDR      0x27 // I2C address of PCF8574A
#define BACKLIGHT_PIN 10
#define En_pin        9
#define Rw_pin        1
#define Rs_pin        8
#define D4_pin        4
#define D5_pin        5
#define D6_pin        6
#define D7_pin        7

LiquidCrystal lcd(Rs_pin, Rw_pin, En_pin, D4_pin, D5_pin, D6_pin, D7_pin, BACKLIGHT_PIN, POSITIVE);
DFR_Key keypad;

byte backlightStandard = 0;
byte backlightCurrent = 0;
byte backlightKeypressBoost = 30;

int lastKey = -1;
int lastUnsentKeydown = -1;
uint16_t steps = 0;
uint16_t stepDelayPerBrightnessFade = 2048;

// uses pin 3
IRsend irsend;

void sendnec(byte addr, byte cmd) {
  uint32_t w =
    ((uint32_t(addr) << 24)    & 0xff000000) |
    (((~uint32_t(addr)) << 16) & 0x00ff0000) |
    ((uint32_t(cmd) << 8)      & 0x0000ff00) |
    ((~uint32_t(cmd))          & 0x000000ff);
  irsend.sendNEC(w, 32);
}

void setup(void) {
  pinMode(motionIn, INPUT);
  digitalWrite(motionIn, 1);
  
  Serial.begin(115200);
  keypad.setRate(10);
  lcd.begin(16,2);
}


void loop() {
  while (Serial.available() <= 2) {
    int localKey = keypad.getKey();
    if (localKey != SAMPLE_WAIT) {
      if (localKey != lastKey) {
        if (lastKey == 0) {
          backlightCurrent = min(255, backlightStandard +
                                 backlightKeypressBoost);
          lastUnsentKeydown = localKey;
        }
        lastKey = localKey;
      }
    }

    if (backlightCurrent > backlightStandard) {
      steps++;
      if (steps % stepDelayPerBrightnessFade == 0) {
        backlightCurrent--;
      }
    } else if (backlightCurrent < backlightStandard) {
      backlightCurrent = backlightStandard;
    }
    lcd.setBacklight(backlightCurrent);
  }
  byte i = Serial.read();
  if (i != 0x60) {
    return;
  }
  i = Serial.read(); // command
  if (i == 0) { // get status
    Serial.print('{');
    if (lastUnsentKeydown != -1) {
      Serial.print("\"keyDown\":");
      Serial.print(lastUnsentKeydown);
      Serial.print(",");
      lastUnsentKeydown = -1;
    }
    Serial.print("\"slider1\":"); Serial.print(analogRead(1));
    Serial.print(",\"slider2\":"); Serial.print(analogRead(2));
    Serial.print(",\"slider3\":"); Serial.print(analogRead(3));
    Serial.print(",\"slider4\":"); Serial.print(analogRead(4));
    Serial.print(",\"motion\":"); Serial.print(digitalRead(motionIn));
    Serial.print("}\n");
  } else if (i == 1) { // write text
    while (Serial.available() < 3) NULL;
    byte row = Serial.read();
    byte col = Serial.read();
    byte nchars = Serial.read();
    char buf[32];
    char *p=buf;
    while (nchars--) {
      while (Serial.available() < 1) NULL;
      *(p++) = Serial.read();
    }
    *p = 0;
    lcd.setCursor(row, col);
    lcd.print(buf);
  } else if (i == 2) { // set backlight
    while (Serial.available() < 1) NULL;
    backlightStandard = Serial.read();
  } else if (i == 3) { // IR NEC protocol
    while (Serial.available() < 2) NULL;
    byte addr = Serial.read();
    sendnec(addr, Serial.read());
  } else {
    // unknown command
  }
}
