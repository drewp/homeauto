#include "fingerprint.h"

#include <string>
#include <vector>

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
    case FPM_UPLOADFAIL:
      errStr = "Cannot transfer the image";
      break;
    case FPM_DBREADFAIL:
      errStr = "Invalid model";
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
      if (mqtt::HasPendingMessage() || queued) {
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
  p = finger.image2Tz(slot);
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
  mqtt::Publish("messages", "mode=enroll; exiting enroll");
  BlinkError();
  WaitForRemove();
}

void enroll_finger(int16_t fid) {
  int16_t p = -1;
  mqtt::Publish("messages", "mode=enroll; Waiting for valid finger to enroll");
  BlinkStartEnroll();
  if (!GetImage()) {
    return EnrollFailed();
  }

  if (!ConvertImage(1)) {
    return EnrollFailed();
  }

  WaitForRemove();

  BlinkStartEnrollRepeat();
  mqtt::Publish("messages", "mode=enroll; Place same finger again");
  if (!GetImage()) {
    return EnrollFailed();
  }
  if (!ConvertImage(2)) {
    return EnrollFailed();
  }

  p = finger.createModel();
  if (p == FPM_OK) {
    mqtt::Publish("messages", "mode=enroll; createModel: Prints matched");
  } else {
    PublishError("createModel", p);
    return EnrollFailed();
  }

  p = finger.storeModel(fid);
  if (p == FPM_OK) {
    char buf[100];
    snprintf(buf, sizeof(buf), "mode=enroll; stored as id %d", fid);
    mqtt::Publish("messages", "mode=enroll; Stored!");
    BlinkSuccess();
    WaitForRemove();
    BlinkClearSuccess();
    return;
  } else {
    PublishError("storeModel", p);
    return EnrollFailed();
  }
}

void Enroll() {
  BlinkStartEnroll();
  mqtt::Publish("messages",
                "mode=enroll; Searching for a free slot to store the template...");
  int16_t fid;
  if (get_free_id(&fid)) {
    enroll_finger(fid);
  } else {
    mqtt::Publish("messages", "mode=enroll; No free slot in flash library!");
    BlinkError();
  }
}

// a GetImage image must be in the buffer to get the real bitmap image
void DownloadLastImage() {
  mqtt::Publish("messages", "Starting image stream");
  finger.downImage();
  std::vector<char> image(256 * 288 / 2);
  size_t image_pos = 0;
  bool read_complete = false;
  uint16_t read_len;

  while (true) {
    read_len = image.size() - image_pos;
    if (!finger.readRaw(FPM_OUTPUT_TO_BUFFER, image.data() + image_pos,
                        &read_complete, &read_len)) {
      mqtt::Publish("messages", "readRaw: failed");
      return;
    }
    image_pos += read_len;
    if (read_complete) {
      break;
    }
  }
  size_t image_len = image_pos;

  char buf[100];
  snprintf(buf, sizeof(buf), "got %d bytes to download", image_len);
  mqtt::Publish("messages", buf);

  std::string msg(image.data(), image_len);
  char subtopic[50];
  snprintf(subtopic, sizeof(subtopic), "image/%d", -1);
  mqtt::Publish(subtopic, msg);
}

void DownloadModel(uint16_t fid) {
  int p = -1;
  mqtt::Publish("messages", "retrieve model for download");
  p = finger.loadModel(fid);
  if (p != FPM_OK) {
    PublishError("loadModel", p);
    return;
  }
  p = finger.downloadModel(fid);
  if (p != FPM_OK) {
    PublishError("downloadModel", p);
    return;
  }
  byte model[2048];  // expect 1536 bytes
  size_t model_pos = 0;
  bool read_complete = false;
  uint16_t read_len;
  while (true) {
    read_len = sizeof(model) - model_pos;
    if (!finger.readRaw(FPM_OUTPUT_TO_BUFFER, model + model_pos, &read_complete,
                        &read_len)) {
      mqtt::Publish("messages", "readRaw: failed");
      return;
    }
    model_pos += read_len;
    if (read_complete) {
      break;
    }
  }
  size_t model_len = model_pos;
  char buf[100];

  snprintf(buf, sizeof(buf), "got %d bytes to download", model_len);
  mqtt::Publish("messages", buf);

  std::string msg(reinterpret_cast<char*>(model), model_len);
  char subtopic[50];
  snprintf(subtopic, sizeof(subtopic), "model/%d", fid);
  mqtt::Publish(subtopic, msg);
}

void SetModel(uint16_t fid, const std::vector<uint8_t>& payload) {
  int16_t p = -1;
  mqtt::Publish("messages", "upload buffer to slot 1");

  p = finger.uploadModel();
  if (p != FPM_OK) {
    PublishError("uploadModel", p);
    return;
  }
  yield();
  finger.writeRaw(const_cast<uint8_t*>(payload.data()), payload.size());
  delay(
      100);  // load-bearing sleep. Without this, the storeModel doesn't answer.

  mqtt::Publish("messages", "store model from slot 1 to fid");
  p = finger.storeModel(fid);
  if (p != FPM_OK) {
    PublishError("storeModel", p);
    return;
  }
  mqtt::Publish("messages", "SetModel successful");
}

void DeleteModel(uint16_t fid) {
  int16_t p = finger.deleteModel(fid);
  if (p == FPM_OK) {
    char msg[100];
    snprintf(msg, sizeof(msg), "deleted id %d", fid);
    mqtt::Publish("messages", msg);
  } else {
    PublishError("deleteModel", p);
  }
}

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