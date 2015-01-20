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

#define debugLed 13

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
  uint32_t w = 0x00ff0000;
  w |= (cmd << 8) & 0xff00;
  w |= (~cmd) & 0xff;
  irsend.sendNEC(w, 32);
 delay(100);
}

void setup(void) {
  pinMode(debugLed, OUTPUT);
  Serial.begin(115200);
  keypad.setRate(10);
  lcd.begin(16,2);


  for (int i = 0; i < 1; i++) {
    digitalWrite(debugLed,1);
    /*
44 key remote. command chart: http://blog.allgaiershops.com/2012/05/
Up  Down Play Pwr
0x3A 0xBA 0x82 0x02

Red  Grn  Blu  Wht
1A   9A   A2   22

2A   AA   92   12

0A   8A   B2   32

38   B8   78   F8

18   98   58   D8

RUp  GUp  BUp  Quick
28   A8   68   E8

RDn  GDn  BDn  Slow
08   88   48   C8

DIY1 DIY2 DIY3 AUTO
30   B0   70   F0

DIY4 DIY5 DIY6 Flash
10   90   50   D0

JMP3 JMP7 Fade Fade7
20   A0   60   E0
      
    irsend.sendNEC(0xff0002fd, 32);
    irsend.sendNEC(0x00ff02fd, 32);
    irsend.sendNEC(0x00ff40bf, 32);
    irsend.sendNEC(0xff0040bf, 32);
    */
    delay(100);

    // LED618 remote command byte (addr is ff)
    // see https://github.com/alistairallan/RgbIrLed/blob/master/RgbIrLed.cpp#L44
#define ON                0xE0
#define OFF               0x60
#define BRIGHTNESS_UP     0xA0
#define BRIGHTNESS_DOWN   0x20
#define FLASH             0xF0
#define STROBE            0xE8
#define FADE              0xD8
#define SMOOTH            0xC8
 
#define RED               0x90
#define GREEN             0x10
#define BLUE              0x50
#define WHITE             0xD0
 
#define ORANGE            0xB0
#define YELLOW_DARK       0xA8
#define YELLOW_MEDIUM     0x98
#define YELLOW_LIGHT      0x88
 
#define GREEN_LIGHT       0x30
#define GREEN_BLUE1       0x28
#define GREEN_BLUE2       0x18
#define GREEN_BLUE3       0x08
 
#define BLUE_RED          0x70
#define PURPLE_DARK       0x68
#define PURPLE_LIGHT      0x58
#define PINK              0x48
    sendnec(0xff, ON);
    
    digitalWrite(debugLed,0);
    delay(100);
  }
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
  } else {
    // unknown command
  }
}
