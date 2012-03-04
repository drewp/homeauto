/*
board is like diecimila with atmega168

*/
#include <SoftwareSerial.h>
int datapin  = 10; // DI
int latchpin = 11; // LI
int enablepin = 12; // EI
int clockpin = 13; // CI

unsigned long SB_CommandPacket;
int SB_CommandMode;
int SB_BlueCommand;
int SB_RedCommand;
int SB_GreenCommand;

#define MAXCHANS 16
int vals[MAXCHANS * 3];

int addr = 0; // which vals element to set next
int currentChans = MAXCHANS;

unsigned char rotation = 0; // position of knob
unsigned char lastRotPosition = 0; // 2*A+1*B

#define TEMP_ENABLED 1

#if TEMP_ENABLED
#include <OneWire.h>
#include <DallasTemperature.h>

OneWire oneWire(4); // digital IO 4
DallasTemperature sensors(&oneWire);
DeviceAddress tempSensorAddress;
#endif

/*
barcode red: +5V
barcode white: gnd
 */
SoftwareSerial barcode =  SoftwareSerial(/* rx pin, green */ 3, 
					 /* tx pin, black */ 2,
					 /* inverse */ true);

void shiftOutLocal(uint8_t dataPin, uint8_t clockPin, byte val)
{
  int i;
  
  for (i = 0; i < 8; i++)  {
    digitalWrite(dataPin, !!(val & (1 << (7 - i))));
    
    digitalWrite(clockPin, HIGH);
    digitalWrite(clockPin, LOW);            
  }
}

void SB_SendPacket() {
   SB_CommandPacket = SB_CommandMode & B11;
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_BlueCommand & 1023);
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_RedCommand & 1023);
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_GreenCommand & 1023);

   shiftOutLocal(datapin, clockpin, SB_CommandPacket >> 24);
   shiftOutLocal(datapin, clockpin, SB_CommandPacket >> 16);
   shiftOutLocal(datapin, clockpin, SB_CommandPacket >> 8);
   shiftOutLocal(datapin, clockpin, SB_CommandPacket);

}
void latch() {
   delayMicroseconds(100);
   digitalWrite(latchpin,HIGH); // latch data into registers
   delayMicroseconds(100);
   digitalWrite(latchpin,LOW); 
}
void refresh() {
  /* send all pixels */
  SB_CommandMode = B00;
  for (int pixel=0; pixel < currentChans; pixel++) {
    SB_RedCommand = vals[pixel * 3 + 0];
    SB_GreenCommand = vals[pixel * 3 + 1];
    SB_BlueCommand = vals[pixel * 3 + 2];
    SB_SendPacket();
  } 
  latch();
}
#define F 1023
#define PIXEL(i, r, g, b) { vals[i*3+0] = r; vals[i*3+1] = g; vals[i*3+2] = b; }

void setCurrent(unsigned char r, unsigned char g, unsigned char b) { 
 /* 127 = max */ 
   SB_CommandMode = B01; // Write to current control registers
   SB_RedCommand = r; 
   SB_GreenCommand = g;
   SB_BlueCommand = b;
   SB_SendPacket();
   latch();
}
void setup() {
   pinMode(datapin, OUTPUT);
   pinMode(latchpin, OUTPUT);
   pinMode(enablepin, OUTPUT);
   pinMode(clockpin, OUTPUT);

   digitalWrite(latchpin, LOW);
   digitalWrite(enablepin, LOW);

   for (int i=0; i < MAXCHANS; i++) {
     setCurrent(127, 127, 127);
   }

   PIXEL(0, F, 0, 0);
   PIXEL(1, 0, F, 0);
   PIXEL(2, 0, 0, F);
   PIXEL(3, F, F, 0);
   PIXEL(4, 0, F, F);
   refresh(); 

#if TEMP_ENABLED
   sensors.begin();
   sensors.getAddress(tempSensorAddress, 0);
   sensors.setResolution(tempSensorAddress, 12);
#endif

   Serial.begin(9600);
   Serial.flush();

   pinMode(5, INPUT);
   pinMode(6, INPUT);
   pinMode(7, INPUT);
   pinMode(8, INPUT);
   pinMode(9, INPUT);
   digitalWrite(6, HIGH); 
   digitalWrite(8, HIGH); 
   digitalWrite(9, HIGH); 


   barcode.begin(1200);
   digitalWrite(2, 0); // inverse logic: don't hold this high

   /*
   barcode.write("\x1b\x42\x0d"); // blink
   */
   /*
   barcode.write("\x1b\x46\x0d"); // off
   */ 
}

void loop() {
  /*
    send 0xff, 
    then a byte for the number of channels you're going to send,
    then nchans*3 bytes of r-g-b levels from 0x00-0xfe.

    second byte 0xfe means to return temp in F, followed by \n
    second byte 0xfd means to return a line describing the state of buttons
    second byte 0xfc means to beep the barcode scanner
    second byte 0xfb means to fetch any recent scanned barcode
   */

  unsigned char curPos = (digitalRead(8) << 1) | digitalRead(9);

  if (curPos == 0 && lastRotPosition == 2) { rotation--; }
  if (curPos == 0 && lastRotPosition == 1) { rotation++; }
  if (curPos == 1 && lastRotPosition == 0) { rotation--; }
  if (curPos == 1 && lastRotPosition == 3) { rotation++; }
  if (curPos == 3 && lastRotPosition == 1) { rotation--; }
  if (curPos == 3 && lastRotPosition == 2) { rotation++; }
  if (curPos == 2 && lastRotPosition == 3) { rotation--; }
  if (curPos == 2 && lastRotPosition == 0) { rotation++; }

  lastRotPosition = curPos;

  int inb = Serial.read();
  if (inb == -1) {
    return;
  }
  if (inb == 0xff) {
    addr = -1;
    return;
  }
  if (addr == -1) {
    if (inb == 0xfe) {
#if TEMP_ENABLED
      sensors.requestTemperatures();
      float tempF = sensors.getTempF(tempSensorAddress);
      Serial.print(tempF);
      Serial.print("\n");
#endif
      addr = -1;
      return;
    }
    if (inb == 0xfb) {
      if (barcode.available() < 1) {
	Serial.print("{\"barcode\":\"\"}\n");
      } else {
	Serial.print("{\"barcode\":\"");
	char last=1;
	while (barcode.available() > 0) {
	  last = barcode.read();
	  Serial.print((int)last);
	  Serial.print(" ");
	}
	Serial.print("\"}\n");
      } 
      return;
    }
    if (inb == 0xfc) {
      barcode.write("\x1b\x54\x0d");// beep
      barcode.write("\x1b\x3f\x0d"); // requisition
      Serial.print("{\"ok\":1}\n");
    }

    if (inb == 0xfd) {
      // read ariremote buttons, where some buttons are combined on
      // the same pins
      digitalWrite(5, HIGH); Serial.print(digitalRead(5));  
      Serial.print(" ");
      digitalWrite(5, LOW);  Serial.print(!digitalRead(5)); 
      Serial.print(" ");
      digitalWrite(7, HIGH); Serial.print(digitalRead(7));  
      Serial.print(" ");
      digitalWrite(7, LOW);  Serial.print(!digitalRead(7)); 
      Serial.print(" ");
      Serial.print(!digitalRead(6)); 
      Serial.print(" ");
      Serial.print((int)rotation);
      Serial.print("\n");
    }
    currentChans = inb;
    addr = 0;
    return; 
  }
  
  vals[addr] = inb * 4; // SB levels are 10-bit. log scale might be better
  addr ++; 
  if (addr >= currentChans * 3) {
    refresh();  
    addr = 0;
  }
  
}
