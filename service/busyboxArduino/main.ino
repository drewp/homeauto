#include <Arduino.h>
#include <LiquidCrystal.h>

#define I2C_ADDR      0x27 // I2C address of PCF8574A
#define BACKLIGHT_PIN 3
#define En_pin        9
#define Rw_pin        1
#define Rs_pin        8
#define D4_pin        4
#define D5_pin        5
#define D6_pin        6
#define D7_pin        7

LiquidCrystal twilcd(Rs_pin, Rw_pin, En_pin, D4_pin, D5_pin, D6_pin, D7_pin, BACKLIGHT_PIN, POSITIVE);

#define debugLed 13


void setup(void) {
  int i;
  pinMode(debugLed, OUTPUT);

  Serial.begin(115200);
  
  twilcd.begin(16,2);
  twilcd.setBacklight(HIGH);
  twilcd.home();
  //1234567890123456
  //I2C/TWI BackPack
  twilcd.print("hello world");
  // ana read and display
  while (1) {
    while (Serial.available() <= 2) {
    }
    i = Serial.read();
    if (i != 0x60) {
      continue;
    }
    i = Serial.read(); // command
    if (i == 0) { // set strip: 0x60 0x00 <numPixels * 3 bytes>
      digitalWrite(debugLed, 1);
      delay(1000);
      digitalWrite(debugLed, 0);
    } else {
        // unknown command
    }
  }
}

void loop() {
}
