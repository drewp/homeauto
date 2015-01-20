// rewritten from distro version by drewp 2015-01-04

#include "Arduino.h"
#include "DFR_Key.h"

static int DEFAULT_KEY_PIN = 0; 
static int DEFAULT_THRESHOLD = 5;

// Updated for my board
static int UPKEY_ARV = 103; //that's read "analogue read value"
static int DOWNKEY_ARV = 266;
static int LEFTKEY_ARV = 426;
static int RIGHTKEY_ARV = 0;
static int SELKEY_ARV = 668;
static int NOKEY_ARV = 1023;

DFR_Key::DFR_Key()
{	
  _refreshRate = 10;
  _keyPin = DEFAULT_KEY_PIN;
  _threshold = DEFAULT_THRESHOLD;
  _keyIn = NO_KEY;
  _curInput = NO_KEY;
  _curKey = NO_KEY;
  _prevInput = NO_KEY;
  _prevKey = NO_KEY;
  _oldTime = 0;
}

int DFR_Key::getKey()
{
  if (millis() < _oldTime + _refreshRate) {
    return SAMPLE_WAIT;
  }

  _prevInput = _curInput;
  _curInput = analogRead(_keyPin);
  _oldTime = millis();

  if (_curInput != _prevInput) {
    // We could be in the middle of a key change
    return SAMPLE_WAIT;
  }

  _prevKey = _curKey;

  int curLo = _curInput - _threshold;
  int curHi = _curInput + _threshold;
  if (      curHi > UPKEY_ARV    && curLo < UPKEY_ARV)    _curKey = UP_KEY;
  else if ( curHi > DOWNKEY_ARV  && curLo < DOWNKEY_ARV)  _curKey = DOWN_KEY;
  else if ( curHi > RIGHTKEY_ARV && curLo < RIGHTKEY_ARV) _curKey = RIGHT_KEY;
  else if ( curHi > LEFTKEY_ARV  && curLo < LEFTKEY_ARV)  _curKey = LEFT_KEY;
  else if ( curHi > SELKEY_ARV   && curLo < SELKEY_ARV)   _curKey = SELECT_KEY;
  else                                                    _curKey = NO_KEY;      

  return _curKey;
}

void DFR_Key::setRate(int rate)
{
  _refreshRate = rate;
}
