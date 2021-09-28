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
  finger.led_control(led_breathe, led_medium, led_purple, /*times=*/1);
}
void BlinkError() {
  finger.led_control(led_flash, led_medium, led_red, /*times=*/3);
  delay(500);
}
void BlinkStartEnroll() {
  finger.led_control(led_flash, led_slow, led_blue, led_forever);
}
void BlinkStartEnrollRepeat() {
  finger.led_control(led_flash, led_medium, led_blue, led_forever);
}
void BlinkClearEnroll() {
  finger.led_control(led_flash, led_slow, led_blue, /*times=*/1);
}

void (*queued)() = nullptr;
void QueueBlinkConnected() { queued = BlinkConnected; }
void ExecuteAnyQueued() {
  if (queued) {
    queued();
    queued = nullptr;
  }
}
namespace {
bool NeedToGetBackToMainLoopSoon() {
  return mqtt::HasPendingMessage() || queued;
}

void LogStatus(const std::string& log_mode, const std::string& msg) {
  mqtt::Publish(log_mode + "/status", msg);
}
void LogError(const std::string& log_mode, const std::string& caller,
              const std::string& err) {
  mqtt::Publish(log_mode + "/error/" + caller, err);
}
void LogStore(const std::string& msg) { mqtt::Publish("store", msg); }
void LogDetect(const std::string& msg) { mqtt::Publish("detected", msg); }

void PublishModel(uint16_t fid, char* model, size_t model_len) {
  std::string msg(model, model_len);
  char subtopic[50];
  snprintf(subtopic, sizeof(subtopic), "model/%d", fid);
  mqtt::Publish(subtopic, msg);
}

void PublishImage(char* image_data, size_t image_len) {
  std::string msg(image_data, image_len);
  char subtopic[50];
  snprintf(subtopic, sizeof(subtopic), "image/%d", -1);
  mqtt::Publish(subtopic, msg);
}

void LogFpmError(const std::string& log_mode, const std::string& caller,
                 int16_t p) {
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
    case FPM_DBCLEARFAIL:
      errStr = "Could not clear database";
      break;
    default:
      char buf[100];
      snprintf(buf, sizeof(buf), "Unknown error (%d)", p);
      errStr = buf;
      break;
  }
  LogError(log_mode, caller, errStr);
}

bool GetImage(const std::string& log_mode) {
  int16_t p = -1;
  LogStatus(log_mode, "Waiting for valid finger");

  while (p != FPM_OK) {
    p = finger.getImage();

    if (p == FPM_OK) {
      LogStatus(log_mode, "Image taken");
    } else if (p == FPM_NOFINGER) {
      if (NeedToGetBackToMainLoopSoon()) {
        return false;
      }
    } else {
      LogFpmError(log_mode, "getImage", p);
      return false;
    }
    yield();
  }
  LogStatus(log_mode, "Got image");

  BlinkProgress();
  return true;
}

bool ConvertImage(const std::string& log_mode, uint8_t slot = 1) {
  int16_t p = -1;
  p = finger.image2Tz(slot);
  if (p == FPM_OK) {
    LogStatus(log_mode, "Image converted");
  } else {
    LogFpmError(log_mode, "image2Tz", p);
    return false;
  }
  return true;
}

bool SearchDatabase(const std::string& log_mode, uint16_t* fid,
                    uint16_t* score) {
  int16_t p = -1;
  p = finger.searchDatabase(fid, score);

  /* now wait to remove the finger, though not necessary;
     this was moved here after the search because of the R503 sensor,
     which seems to wipe its buffers after each scan */
  LogStatus(log_mode, "Waiting for finger removal");
  while (finger.getImage() != FPM_NOFINGER) {
    delay(500);
  }

  if (p != FPM_OK) {
    LogFpmError(log_mode, "searchDatabase", p);

    if (p == FPM_NOTFOUND) {
      BlinkError();
    }
    return false;
  }
  return true;
}

void ReportFoundMatch(uint16_t fid, uint16_t score) {
  char msg[100];
  snprintf(msg, sizeof(msg), "Found id %d confidence %d", fid, score);
  LogDetect(msg);
}
}  // namespace
void ScanLoop() {
  const std::string& log_mode = "scan";
  if (!GetImage(log_mode)) {
    return;
  }

  if (!ConvertImage(log_mode)) {
    return;
  }

  uint16_t fid, score;
  if (!SearchDatabase(log_mode, &fid, &score)) {
    return;
  }

  ReportFoundMatch(fid, score);
}
namespace {
bool get_free_id(const std::string& log_mode, int16_t* fid) {
  int16_t p = -1;
  for (int page = 0; page < (params.capacity / FPM_TEMPLATES_PER_PAGE) + 1;
       page++) {
    p = finger.getFreeIndex(page, fid);
    if (p != FPM_OK) {
      LogFpmError(log_mode, "getFreeIndex", p);
      return false;
    }
    if (*fid != FPM_NOFREEINDEX) {
      char buf[100];
      snprintf(buf, sizeof(buf), "Free slot at id %d", *fid);
      LogStatus(log_mode, buf);
      return true;
    }
    yield();
  }
  LogStatus(log_mode, "getFreeIndex: No free slots");
  return false;
}

void WaitForRemove(const std::string& log_mode) {
  int16_t p = -1;
  LogStatus(log_mode, "Remove finger");
  delay(2000);
  p = 0;
  while (p != FPM_NOFINGER) {
    p = finger.getImage();
    yield();
  }
}

void EnrollFailed(const std::string& log_mode) {
  LogStatus(log_mode, "Exiting enroll");
  BlinkError();
  WaitForRemove(log_mode);
}

void enroll_finger(const std::string& log_mode, int16_t fid) {
  int16_t p = -1;
  LogStatus(log_mode, "Waiting for valid finger to enroll");
  BlinkStartEnroll();
  if (!GetImage(log_mode)) {
    return EnrollFailed(log_mode);
  }

  if (!ConvertImage(log_mode, 1)) {
    return EnrollFailed(log_mode);
  }

  WaitForRemove(log_mode);

  BlinkStartEnrollRepeat();
  LogStatus(log_mode, "Place same finger again");
  if (!GetImage(log_mode)) {
    return EnrollFailed(log_mode);
  }
  if (!ConvertImage(log_mode, 2)) {
    return EnrollFailed(log_mode);
  }

  p = finger.createModel();
  if (p == FPM_OK) {
    LogStatus(log_mode, "Prints matched");
  } else {
    LogFpmError(log_mode, "createModel", p);
    return EnrollFailed(log_mode);
  }

  p = finger.storeModel(fid);
  if (p == FPM_OK) {
    char buf[100];
    snprintf(buf, sizeof(buf), "Stored as id %d", fid);
    LogStore(buf);
    BlinkSuccess();
    WaitForRemove(log_mode);
    BlinkClearSuccess();
    return;
  } else {
    LogFpmError(log_mode, "storeModel", p);
    return EnrollFailed(log_mode);
  }
}
}  // namespace
void Enroll() {
  const std::string log_mode = "enroll";
  BlinkStartEnroll();
  LogStatus(log_mode, "Searching for a free slot to store the template...");
  int16_t fid;
  if (!get_free_id(log_mode, &fid)) {
    BlinkError();
    return;
  }
  enroll_finger(log_mode, fid);
}

// a GetImage image must be in the buffer to get the real bitmap image
void DownloadLastImage(const std::string& log_mode) {
  LogStatus(log_mode, "Starting image stream");
  finger.downImage();
  std::vector<char> image(256 * 288 / 2);
  size_t image_pos = 0;
  bool read_complete = false;
  uint16_t read_len;

  while (true) {
    read_len = image.size() - image_pos;
    if (!finger.readRaw(FPM_OUTPUT_TO_BUFFER, image.data() + image_pos,
                        &read_complete, &read_len)) {
      LogFpmError(log_mode, "readRaw", -1);
      return;
    }
    image_pos += read_len;
    if (read_complete) {
      break;
    }
  }
  size_t image_len = image_pos;

  char buf[100];
  snprintf(buf, sizeof(buf), "Got %d bytes to download", image_len);
  LogStatus(log_mode, buf);

  PublishImage(image.data(), image_len);
}

void DownloadModel(uint16_t fid) {
  const std::string log_mode = "download";
  int p = -1;
  LogStatus(log_mode, "Retrieve model for download");
  p = finger.loadModel(fid);
  if (p != FPM_OK) {
    LogFpmError(log_mode, "loadModel", p);
    return;
  }
  p = finger.downloadModel(fid);
  if (p != FPM_OK) {
    LogFpmError(log_mode, "downloadModel", p);
    return;
  }
  char model[2048];  // expect 1536 bytes
  size_t model_pos = 0;
  bool read_complete = false;
  uint16_t read_len;
  while (true) {
    read_len = sizeof(model) - model_pos;
    if (!finger.readRaw(FPM_OUTPUT_TO_BUFFER, model + model_pos, &read_complete,
                        &read_len)) {
      LogFpmError(log_mode, "readRaw", -1);
      return;
    }
    model_pos += read_len;
    if (read_complete) {
      break;
    }
  }
  size_t model_len = model_pos;
  char buf[100];

  snprintf(buf, sizeof(buf), "Got %d bytes to download", model_len);
  LogStatus(log_mode, buf);

  PublishModel(fid, model, model_len);
}

void SetModel(uint16_t fid, const std::vector<uint8_t>& payload) {
  const std::string log_mode = "setModel";
  int16_t p = -1;
  LogStatus(log_mode, "Upload buffer to slot 1");

  p = finger.uploadModel();
  if (p != FPM_OK) {
    LogFpmError(log_mode, "uploadModel", p);
    return;
  }
  yield();
  finger.writeRaw(const_cast<uint8_t*>(payload.data()), payload.size());
  delay(
      100);  // load-bearing sleep. Without this, the storeModel doesn't answer.

  LogStatus(log_mode, "Store model from slot 1 to fid");
  p = finger.storeModel(fid);
  if (p != FPM_OK) {
    LogFpmError(log_mode, "storeModel", p);
    return;
  }
  char buf[100];
  snprintf(buf, sizeof(buf), "SetModel successful for id %d", fid);
  LogStore(buf);
}

void DeleteModel(uint16_t fid) {
  const std::string log_mode = "deleteModel";
  int16_t p = finger.deleteModel(fid);
  if (p == FPM_OK) {
    char msg[100];
    snprintf(msg, sizeof(msg), "Deleted id %d", fid);
    LogStore(msg);
  } else {
    LogFpmError(log_mode, "deleteModel", p);
  }
}

void DeleteAll() {
  int16_t p = finger.emptyDatabase();
  if (p == FPM_OK) {
    LogStore("Database cleared");
  } else {
    LogFpmError("deleteAll", "emptyDatabase", p);
  }
}

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