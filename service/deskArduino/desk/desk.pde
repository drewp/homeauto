int datapin  = 10; // DI
int latchpin = 11; // LI
int enablepin = 12; // EI
int clockpin = 13; // CI

unsigned long SB_CommandPacket;
int SB_CommandMode;
int SB_BlueCommand;
int SB_RedCommand;
int SB_GreenCommand;

#define SHIFT(val) shiftOut(datapin, clockpin, MSBFIRST, val)

void SB_SendPacket() {
  /* high bits are 00 for color, 01 for current */
   SB_CommandPacket = SB_CommandMode & B11;
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_BlueCommand & 1023);
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_RedCommand & 1023);
   SB_CommandPacket = (SB_CommandPacket << 10)  | (SB_GreenCommand & 1023);

   SHIFT(SB_CommandPacket >> 24);
   SHIFT(SB_CommandPacket >> 16);
   SHIFT(SB_CommandPacket >> 8);
   SHIFT(SB_CommandPacket);

}
void latch() {
   delayMicroseconds(100);
   digitalWrite(latchpin,HIGH); // latch data into registers
   delayMicroseconds(100);
   digitalWrite(latchpin,LOW); 
}

void setCurrent(byte r, byte g, byte b) { 
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

   for (int i=0; i < 2; i++) {
     setCurrent(127, 127, 127);
   }

   SHIFT(0x3f); SHIFT(0xc0); SHIFT(0x00); SHIFT(0x00);
   SHIFT(0x00); SHIFT(0x0f); SHIFT(0xf0); SHIFT(0x00);
   latch();

   Serial.begin(115200);
   Serial.flush();
}

void loop() {
  byte head, cmd;
  if (Serial.available() >= 2) {
    head = Serial.read();
    if (head != 0x60) {
      Serial.flush();
      return;
    }
    cmd = Serial.read();
    if (cmd == 0x00) {
      Serial.print("{\"ok\":\"ping\"}\n");
    } else if (cmd == 0x01) {
      /*
	one byte for the string length, then a buffer to be shifted
	out to all the shiftbrites
      */

      while (Serial.available() == 0) NULL;
      byte count = Serial.read();
      /*
      for (int i=0; i < count / 4; i++) {
	setCurrent(127, 127, 127);
      }
      */
      for (int i=0; i<count; i++) {
	while (Serial.available() == 0) NULL;
	SHIFT(Serial.read());
      }
      latch();
      Serial.print("{\"ok\":1}\n");
    }
  }
}
