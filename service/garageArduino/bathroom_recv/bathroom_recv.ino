/*
  board: 'Digispark (Tiny Core)'
  programmer: 'Digispark'
  
  pin 0 DI from radio
  pin 1 DO to radio (and green status led)
  pin 2 SCK to radio
  pin 3 output to LED string
  pin 4 input from garage arduino
  pin 5 output to garage arduino
    
  (attiny85 pin 5 is MOSI, pin 6 is MISO, 7 might be clock)  
  
*/
#include <VirtualWire.h>

#include <Adafruit_NeoPixel.h>

// Parameter 1 = number of pixels in strip
// Parameter 2 = pin number (most are valid)
// Parameter 3 = pixel type flags, add together as needed:
//   NEO_RGB     Pixels are wired for RGB bitstream
//   NEO_GRB     Pixels are wired for GRB bitstream
//   NEO_KHZ400  400 KHz bitstream (e.g. FLORA pixels)
//   NEO_KHZ800  800 KHz bitstream (e.g. High Density LED strip)
Adafruit_NeoPixel strip = Adafruit_NeoPixel(4, 3, NEO_GRB + NEO_KHZ800);

#define SET(i, r, g, b) strip.setPixelColor(i, strip.Color(r, g, b)); strip.show();

int numLeds = 4;

void wakeUpPattern() { 
  for (int t = 0; t < 255; t += 2) {
    for (int i = 0; i < numLeds; i++) {
      //SET(i, 255 - t, max(0, 255 - t * 2), max(0, 255 - t * 3)); 
      SET(i, 
        (i % 2) ? (255 - t) : 0,
        (i % 2) ? 0 : (255 - t),
        (i % 2) ? (255 - t) : 0);
    }
    delay(10);
  }
  SET(0, 0, 0, 0);
  SET(1, 0, 0, 0);
  SET(2, 0, 0, 0);
  SET(3, 0, 0, 0);
}

void blinkFailedMessageError() {
  digitalWrite(1, 1);
  delay(100);
  digitalWrite(1, 0);
}

void blinkShortBufferError() {
  digitalWrite(1, 1);
  delay(100);
  digitalWrite(1, 0);
  delay(50);
  digitalWrite(1, 1);
  delay(100);
  digitalWrite(1, 0);
}

void setup() {
  pinMode(1, OUTPUT); // for errors
  
  vw_set_rx_pin(4);
  vw_setup(2000);	 // Bits per sec

  vw_rx_start();       // Start the receiver PLL running

  strip.begin();
  strip.show();

  wakeUpPattern();
}

void loop() {
  uint8_t buf[VW_MAX_MESSAGE_LEN];
  uint8_t buflen = VW_MAX_MESSAGE_LEN;

  vw_wait_rx();
  int success = vw_get_message(buf, &buflen);
  if (!success) {
    blinkFailedMessageError();
    return;
  }
  if (buflen < numLeds * 3) { 
    blinkShortBufferError();
    return;
  }

  for (int i=0; i < numLeds; i++) {
    strip.setPixelColor(i, strip.Color(
    buf[i * 3 + 0], 
    buf[i * 3 + 1], 
    buf[i * 3 + 2]));
  }
  strip.show();
}

