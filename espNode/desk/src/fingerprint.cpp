#include "fingerprint.h"

#include <string>

#include "mqtt.h"

namespace fingerprint {

HardwareSerial fserial(1);
FPM finger(&fserial);

constexpr uint8_t led_red = 0x01, led_blue = 0x02, led_purple = 0x03;
constexpr uint8_t led_breathe = 0x01, led_flash = 0x02, led_on = 0x03,
                  led_off = 0x04, led_gradual_on = 0x05, led_gradual_off = 0x06;
constexpr uint8_t led_fast = 0x30, led_medium = 0x60, led_slow = 0x80;
constexpr uint8_t led_forever = 0;

FPM_System_Params params;

void BlinkNotConnected() {
  finger.led_control(led_flash, led_fast, led_red, led_forever);
}
void BlinkConnected() {
  finger.led_control(led_flash, led_fast, led_red, /*times=*/1);
}
void BlinkProgress() {
  finger.led_control(led_flash, led_fast, led_blue, /*times=*/1);
}
void BlinkSuccess() {
  finger.led_control(led_breathe, led_medium, led_purple, led_forever);
}
void BlinkClearSuccess() {
  finger.led_control(led_breathe, led_medium, led_purple, 1);
}
void BlinkError() {
  finger.led_control(led_flash, led_medium, led_red, /*times=*/3);
  delay(500);
}
void BlinkDoorUnlocked() {}
void BlinkStartEnroll() {
  finger.led_control(led_flash, led_slow, led_blue, led_forever);
}
void BlinkStartEnrollRepeat() {
  finger.led_control(led_flash, led_medium, led_blue, led_forever);
}
void BlinkClearEnroll() {
  finger.led_control(led_flash, led_slow, led_blue, 1);
}

void (*queued)() = nullptr;
void QueueBlinkConnected() { queued = BlinkConnected; }
void ExecuteAnyQueued() {
  if (queued) {
    Serial.println("executing queued function");
    queued();
    queued = nullptr;
  }
}

void PublishError(std::string caller, int16_t p) {
  std::string errStr;
  switch (p) {
    case FPM_FEATUREFAIL:
      errStr = "Could not find fingerprint features";
      break;
    case FPM_IMAGEFAIL:
      errStr = "Imaging error";
      break;
    case FPM_IMAGEMESS:
      errStr = "Image too messy";
      break;
    case FPM_INVALIDIMAGE:
      errStr = "Could not find fingerprint features";
      break;
    case FPM_NOTFOUND:
      errStr = "Did not find a match";
      break;
    case FPM_PACKETRECIEVEERR:
      errStr = "Communication error";
      break;
    case FPM_READ_ERROR:
      errStr = "Got wrong PID or length";
      break;
    case FPM_BADLOCATION:
      errStr = "Could not store/delete in that location";
      break;
    case FPM_FLASHERR:
      errStr = "Error writing to flash";
      break;
    case FPM_TIMEOUT:
      errStr = "Timeout";
      break;
    case FPM_ENROLLMISMATCH:
      errStr = "Fingerprints did not match";
      break;
    default:
      char buf[100];
      snprintf(buf, sizeof(buf), "Unknown error (%d)", p);
      errStr = buf;
      break;
  }
  mqtt::Publish("messages", caller + ": " + errStr);
}

bool GetImage() {
  int16_t p = -1;
  mqtt::Publish("messages", "Waiting for valid finger");

  while (p != FPM_OK) {
    p = finger.getImage();

    if (p == FPM_OK) {
      mqtt::Publish("messages", "getImage: Image taken");
    } else if (p == FPM_NOFINGER) {
      if (mqtt::HasPendingCommand() || queued) {
        return false;
      }
    } else {
      PublishError("getImage", p);
      return false;
    }
    yield();
  }
  mqtt::Publish("messages", "getImage: got image");

  BlinkProgress();
  return true;
}

bool ConvertImage(uint8_t slot = 1) {
  int16_t p = -1;
  p = finger.image2Tz();
  if (p == FPM_OK) {
    mqtt::Publish("messages", "image2Tz: Image converted");
  } else {
    PublishError("image2Tz", p);
    return false;
  }
  return true;
}

bool SearchDatabase(uint16_t* fid, uint16_t* score) {
  int16_t p = -1;
  p = finger.searchDatabase(fid, score);

  /* now wait to remove the finger, though not necessary;
     this was moved here after the search because of the R503 sensor,
     which seems to wipe its buffers after each scan */
  mqtt::Publish("messages", "Waiting for finger removal");
  while (finger.getImage() != FPM_NOFINGER) {
    delay(500);
  }

  if (p != FPM_OK) {
    PublishError("searchDatabase", p);

    if (p == FPM_NOTFOUND) {
      BlinkError();
    }
    return false;
  }
  return true;
}

void ReportFoundMatch(uint16_t fid, uint16_t score) {
  char msg[100];
  snprintf(msg, sizeof(msg), "found id %d confidence %d", fid, score);
  mqtt::Publish("match", msg);
}

void ScanLoop() {
  if (!GetImage()) {
    return;
  }

  if (!ConvertImage()) {
    return;
  }

  uint16_t fid, score;
  if (!SearchDatabase(&fid, &score)) {
    return;
  }

  ReportFoundMatch(fid, score);
}

bool get_free_id(int16_t* fid) {
  int16_t p = -1;
  for (int page = 0; page < (params.capacity / FPM_TEMPLATES_PER_PAGE) + 1;
       page++) {
    p = finger.getFreeIndex(page, fid);
    if (p != FPM_OK) {
      PublishError("getFreeIndex", p);
      return false;
    }
    if (*fid != FPM_NOFREEINDEX) {
      char buf[100];
      snprintf(buf, sizeof(buf), "getFreeIndex: Free slot at id %d", *fid);
      mqtt::Publish("messages", buf);
      return true;
    }
    yield();
  }
  mqtt::Publish("messages", "getFreeIndex: No free slots");
  return false;
}

void WaitForRemove() {
  int16_t p = -1;
  mqtt::Publish("messages", "Remove finger");
  delay(2000);
  p = 0;
  while (p != FPM_NOFINGER) {
    p = finger.getImage();
    yield();
  }
}

void EnrollFailed() {
  mqtt::Publish("messages", "exiting enroll");
  BlinkError();
  WaitForRemove();
}

void enroll_finger(int16_t fid) {
  int16_t p = -1;
  mqtt::Publish("messages", "Waiting for valid finger to enroll");
  BlinkStartEnroll();
  if (!GetImage()) {
    return EnrollFailed();
  }

  if (!ConvertImage(1)) {
    return EnrollFailed();
  }

  WaitForRemove();

  BlinkStartEnrollRepeat();
  mqtt::Publish("messages", "Place same finger again");
  if (!GetImage()) {
    return EnrollFailed();
  }
  if (!ConvertImage(2)) {
    return EnrollFailed();
  }

  p = finger.createModel();
  if (p == FPM_OK) {
    mqtt::Publish("messages", "createModel: Prints matched");
  } else {
    PublishError("createModel", p);
    return EnrollFailed();
  }

  p = finger.storeModel(fid);
  if (p == FPM_OK) {
    mqtt::Publish("messages", "Stored!");
    BlinkSuccess();
    WaitForRemove();
    BlinkClearSuccess();
    return;
  } else {
    PublishError("storeModel", p);
    return EnrollFailed();
  }
}

void DeleteFingerprint(uint16_t fid) {
  int p = -1;

  p = finger.deleteModel(fid);

  if (p == FPM_OK) {
    Serial.println("Deleted!");
  } else {
    PublishError("deleteModel", p);
  }
}

void Enroll() {
  BlinkStartEnroll();
  mqtt::Publish("messages",
                "Searching for a free slot to store the template...");
  int16_t fid;
  if (get_free_id(&fid)) {
    enroll_finger(fid);
  } else {
    mqtt::Publish("messages", "No free slot in flash library!");
    BlinkError();
  }
}

void DownloadPrintImage(uint16_t fid) {}
void DeleteAll() {}

void Setup() {
  fserial.begin(57600, SERIAL_8N1, 26 /*rx*/, 27 /*tx*/);

  if (finger.begin()) {
    finger.readParams(&params);
    Serial.println("Found fingerprint sensor!");
    Serial.print("Capacity: ");
    Serial.println(params.capacity);
    Serial.print("Packet length: ");
    Serial.println(FPM::packet_lengths[params.packet_len]);
  } else {
    Serial.println("Did not find fingerprint sensor :(");
    while (1) yield();
  }
  BlinkNotConnected();
}
}  // namespace fingerprint