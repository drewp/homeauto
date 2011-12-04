/*
 note that the chip in this arduino has been replaced with a '328
 */
#include "ST7565.h"
#include <OneWire.h>
#include <DallasTemperature.h>

#define BACKLIGHT_LED 10

ST7565 glcd(9, 8, 7, 6, 5);

OneWire oneWire(3); // digital IO 3
DallasTemperature sensors(&oneWire);
DeviceAddress tempSensorAddress;
#define NUM_TEMPERATURE_RETRIES 5

char newtxt[21*8+1];
unsigned int written;
unsigned char cmd;

#define GETHEADER -2
#define GETCOMMAND -1

void setup()   {                
  Serial.begin(9600);
  Serial.flush();

  pinMode(11, INPUT); // low means door is closed
  digitalWrite(11, HIGH);

  pinMode(12, OUTPUT);
  digitalWrite(12, LOW);

  pinMode(BACKLIGHT_LED, OUTPUT);
  analogWrite(BACKLIGHT_LED, 200);

  glcd.st7565_init();
  glcd.st7565_command(CMD_DISPLAY_ON);
  glcd.st7565_command(CMD_SET_ALLPTS_NORMAL);
  glcd.st7565_set_brightness(0x18);

  glcd.display(); // show splashscreen

  newtxt[21*8] = 0;
  written = GETHEADER; // GETHEADER --recv 0xff--> GETCOMMAND --recv 0x00--> 0
}

void initSensors() {
  sensors.begin();
  sensors.getAddress(tempSensorAddress, 0);
  sensors.setResolution(tempSensorAddress, 12);
}

void loop() {
  /*
      send 0xff 0x00,
   then up to 21*8 bytes of text to replace the display, with a null terminator.
   
   or 0xff 0x01, then get back '0\n' or '1\n' for the door sensor
   
   or 0xff 0x02, then get back temperature followed by newline
   
   or 0xff 0x03 then a byte for the screen brightness

   or 0xff 0x0f then 00 or 01 to set the front lights on pin 12
   */
  float newTemp;
  int i, printed;
  int inb = Serial.read();
  if (inb == -1) {
    return;
  }

  if (written == GETHEADER) {
    if (inb == 0xff) {
      written = GETCOMMAND;
    }
  } 
  else if(written == GETCOMMAND) {
    cmd = inb;

    switch(cmd) {
    case 0:
      written = 0; // get chars below
      return;

    case 1:
      Serial.print(digitalRead(11) ? 
                   "{\"door\":\"open\"}\n" : 
                   "{\"door\":\"closed\"}\n");
      written = GETHEADER;
      return;

    case 2:    

      for (i=0; i<NUM_TEMPERATURE_RETRIES; i++) {

        sensors.requestTemperatures();
        newTemp = sensors.getTempF(tempSensorAddress);
        if (i < NUM_TEMPERATURE_RETRIES-1 && 
            (newTemp < -100 || newTemp > 180)) {
          // too many errors that were fixed by restarting arduino. 
          // trying repeating this much init
          initSensors();
          continue;
        }
        Serial.print("{\"temp\":");
        Serial.print(newTemp);
        Serial.print(", \"retries\":");
        Serial.print(i);
        Serial.print("}\n");
        break;
      }
      written = GETHEADER;
      return;

    case 3:
    case 4:
      written = 0; // these are handled below
      return;    

      // otherwise take chars 
    }  
  } 
  else {
    if (cmd == 3) {
      analogWrite(BACKLIGHT_LED, 255 - inb);
      written = GETHEADER;
      return; 
    }
    if (cmd == 4) {
      digitalWrite(12, inb);
      written = GETHEADER;
      return;
    }
    newtxt[written] = inb;
    written++;

    if (inb == 0 || (written > 21 * 8)) {
      glcd.clear();
      glcd.drawstring(0,0, newtxt); 
      glcd.display();

      written = GETHEADER;
      return;
    }
  }  
}






