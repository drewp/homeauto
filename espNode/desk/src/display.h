#ifndef INCLUDED_DISPLAY
#define INCLUDED_DISPLAY
#include <string>

#ifndef TFT_DISPOFF
#define TFT_DISPOFF 0x28
#endif

#ifndef TFT_SLPIN
#define TFT_SLPIN 0x10
#endif

namespace display {
void Setup();
void Message(std::string msg);
}  // namespace display
#endif