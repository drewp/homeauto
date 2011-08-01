 void setup()   {                
  
  pinMode(2, INPUT);
  digitalWrite(2, LOW); 
// PIR sensor on here is a 
// http://octopart.com/555-28027-parallax-708653 in a 
// http://octopart.com/1551ggy-hammond-15686 box
  
  // the phototransistor on analog2 is jameco 2006414

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
    }
  }
}

	
