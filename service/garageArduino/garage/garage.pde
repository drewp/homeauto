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
    }
  }
}

	
