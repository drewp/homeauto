/*
board is like a diecimila '168

shopping:
volume knob 4x
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_776386_-1

pretty metal button 4x
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_2131274_-1

music selector
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_317850_-1

alarm check green button 1x
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_315678_-1

similar red:
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_315660_-1

similar black:
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_315651_-1

illuminated red:
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_315820_-1

momentary on/on switch for lighting or audio selector 2x
http://www.jameco.com/webapp/wcs/stores/servlet/ProductDisplay?langId=-1&sub_attr_name=Switch+Configuration&position=1&productId=317252&catalogId=10001&refineType=1&refineValue=%28ON%29-OFF-%28ON%29&storeId=10001&refine=1&history=22t4lgkv%7CsubCategoryName%7ESwitches%5Ecategory%7E3540%5EcategoryName%7Ecat_35%5EprodPage%7E50%5Epage%7ESEARCH%252BNAV%40f2zj2rdd%7Ccategory%7E354070%5EcategoryName%7Ecat_3540%5Eposition%7E1%5Erefine%7E1%5EsubCategoryName%7ESwitches%2B%252F%2BToggle%5EprodPage%7E50%5Epage%7ESEARCH%252BNAV&ddkey=http:StoreCatalogDrillDownView

demultiplexer
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_894024_-1
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_12909_-1

stereo out jack 4x
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_2095437_-1


audio switch relay
http://www.jameco.com/webapp/wcs/stores/servlet/Product_10001_10001_139977_-1

need two channels of relay or ssr for audio

PIR reset switch

motion

music volume knob, maybe two of them on each side of the bed

alarm check

drive the rgb leds

switch the main speakers or just pillow speaker

Control corner light and red ball light

Alternate light switch at door and repeated at each side of the bed

*/

#define SWITCH_X 3
#define SWITCH_Y 4
#define SWITCH_SELECT_A 7
#define SWITCH_SELECT_B 9
#define SWITCH_SELECT_C 8
#define SPEAKER_CHOICE 13

void setup()   {                
  
  pinMode(2, INPUT);
  digitalWrite(2, LOW); 
// PIR sensor DC-SS015 from http://www.gadgettown.com/Pyroelectric-Infrared-PIR-Motion-Sensor-Detector-Module-E2013.html

  pinMode(SWITCH_X, INPUT); digitalWrite(SWITCH_X, LOW);
  pinMode(SWITCH_Y, INPUT); digitalWrite(SWITCH_Y, LOW);

  pinMode(SWITCH_SELECT_A, OUTPUT);
  pinMode(SWITCH_SELECT_B, OUTPUT);
  pinMode(SWITCH_SELECT_C, OUTPUT);
  pinMode(SPEAKER_CHOICE, OUTPUT);

  Serial.begin(115200);
}

#define setSelect(a,b,c) \
  digitalWrite(SWITCH_SELECT_A, a); \
  digitalWrite(SWITCH_SELECT_B, b); \
  digitalWrite(SWITCH_SELECT_C, c);

void loop()                     
{
  unsigned char head, cmd, arg;

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
      Serial.print("{\"motion\":");
      Serial.print(analogRead(4));

#define printXy \
      Serial.print(digitalRead(SWITCH_X)); \
      Serial.print(","); \
      Serial.print(digitalRead(SWITCH_Y)); \
      
      Serial.print(", \"spkrL\":[");
      setSelect(0,0,0); delay(2); printXy

      Serial.print("], \"volR\":[");
      setSelect(1,0,0); delay(2); printXy

      Serial.print("], \"lightL\":[");
      setSelect(0,1,0); delay(2); printXy

      Serial.print("], \"lightR\":[");
      setSelect(1,1,0); delay(2); printXy

      Serial.print("], \"volL\":[");
      setSelect(0,0,1); delay(2); printXy

      Serial.print("], \"alarmCheck\":");
      setSelect(1,1,1); 
      Serial.print(digitalRead(SWITCH_X));
      Serial.print(", \"door\":");
      Serial.print(digitalRead(SWITCH_Y));

      Serial.print("}\n");
    } else if (cmd == 0x02) { // speaker
      digitalWrite(SPEAKER_CHOICE, arg);
      Serial.print("{\"speakerChoice\":");
      Serial.print((int)arg);
      Serial.print("}\n");
    }
  }
}

	
