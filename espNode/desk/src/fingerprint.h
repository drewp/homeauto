#ifndef INCLUDED_FINGERPRINT
#define INCLUDED_FINGERPRINT
#include <FPM.h>
#include <HardwareSerial.h>

namespace fingerprint {
void Setup();
void ExecuteAnyQueued();
void BlinkProgress();
void BlinkNotConnected();
void BlinkConnected();
void QueueBlinkConnected(); // for inside an ISR
void BlinkSuccess();
void BlinkClearSuccess();
void ScanLoop();
void Enroll();
void DownloadPrintImage(uint16_t fid);
void DeleteAll();
}
#endif