/*
board is Arduino UNO with '328
 */

int datapin  = 7; // DI
int latchpin = 9; // LI
int clockpin = 8; // CI

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


void setup()   {                
  
  pinMode(2, INPUT);
  digitalWrite(2, LOW); 
// PIR sensor on here is a 
// http://octopart.com/555-28027-parallax-708653 in a 
// http://octopart.com/1551ggy-hammond-15686 box
  
  // the phototransistor on analog2 is jameco 2006414

  pinMode(3, OUTPUT);
  digitalWrite(3, LOW);
  // this drives a relay for the garage door. There is a 
  // LP filter on it so the garage doesn't open if there's 
  // an arduino power-on glitch. It may be that atmel has 
  // circuitry to prevent such glitches, so a pull-down
  // resistor may be enough. I haven't checked carefully.

  pinMode(4, OUTPUT);
  pinMode(5, OUTPUT);
  // video input selector. picks which video input will be multiplexed
  // into the bt848 capture card

  pinMode(6, OUTPUT);  // front yard light

  pinMode(7, OUTPUT); // bathroom shiftbrite data
  pinMode(8, OUTPUT); // bathroom shiftbrite clk
  pinMode(9, OUTPUT); // bathroom shiftbrite latch

  for (int i=0; i < 1; i++) {
    setCurrent(127, 127, 127);
  }

  Serial.begin(115200);
}

int newBlinks = 0;
int lastLevel = 0;
int threshold = 750;
int hold = 3; // pulse must last this many loops. Guessing-- I don't know the loop rate or the pulse width
int seenFor = 0;

void loop()                     
{
  unsigned char head, cmd, arg;
  int level = analogRead(3) < threshold;
  
  if (level) {
     seenFor++; 
     if (seenFor == hold) {
        newBlinks++; 
     }
  } else {
     seenFor = 0;
  }

  if (Serial.available() >= 3) {
    head = Serial.read();
    if (head != 0x60) {
      Serial.flush();
      return;
    }
    cmd = Serial.read();
    arg = Serial.read();
    Serial.flush();
    if (cmd == 0x00) {
      Serial.print("{\"ok\":true}\n");
    } else if (cmd == 0x01) { // poll
      Serial.print("{\"newBlinks\":");
      Serial.print(newBlinks);
      Serial.print(", \"motion\":");
      Serial.print(digitalRead(2) ? "true" : "false");
      Serial.print("}\n");
      newBlinks = 0;
    } else if (cmd == 0x02) {
      // current level
      Serial.print("{\"z\":");
      Serial.print(analogRead(3));
      Serial.print("}\n");
    } else if (cmd == 0x03) {
      if (arg != 0) {
        threshold = arg << 2;
      }
      Serial.print("{\"threshold\":");
      Serial.print(threshold);
      Serial.print("}\n");
    } else if (cmd == 0x04) {
      digitalWrite(3, arg);
      Serial.print("{\"garage\":");
      Serial.print(arg ? "true" : "false");
      Serial.print("}\n");     
    } else if (cmd == 0x05) { // set video	
      digitalWrite(4, arg & 1);
      digitalWrite(5, arg & 2);
      Serial.print("{\"videoSelect\":");
      Serial.print(arg);
      Serial.print("}\n");     
    } else if (cmd == 0x06) { // talk to shiftbrite
      /*
        one byte for the string length, then a buffer to be shifted
        out to all the shiftbrites
      */
      /*
      for (int i=0; i < arg / 4; i++) {
        setCurrent(127, 127, 127);
      }
      */
      for (int i=0; i<arg; i++) {
        while (Serial.available() == 0) NULL;
        SHIFT(Serial.read());
      }
      latch();
      Serial.print("{\"ok\":1}\n");

    }   
  }
}

	
