#ifndef INCLUDED_FINGERPRINT
#define INCLUDED_FINGERPRINT
#include <FPM.h>
#include <HardwareSerial.h>

#include <vector>

namespace fingerprint {
void Setup();
void ExecuteAnyQueued();
void BlinkProgress();
void BlinkNotConnected();
void BlinkConnected();
void QueueBlinkConnected();  // for inside an ISR
void BlinkSuccess();
void BlinkClearSuccess();
void ScanLoop();
void Enroll();
void DownloadLastImage();
void DownloadModel(uint16_t fid);
void DeleteAll();
void DeleteModel(uint16_t fid);
void SetModel(uint16_t fid, const std::vector<uint8_t>& payload);

}  // namespace fingerprint
#endif