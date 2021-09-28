// Auto generated code by esphome
// ========== AUTO GENERATED INCLUDE BLOCK BEGIN ===========
#include "esphome.h"
using namespace esphome;
logger::Logger *logger_logger;
wifi::WiFiComponent *wifi_wificomponent;
ota::OTAComponent *ota_otacomponent;
mqtt::MQTTClientComponent *mqtt_mqttclientcomponent;
using namespace mqtt;
using namespace json;
// ========== AUTO GENERATED INCLUDE BLOCK END ==========="

// camera.cpp
extern void cam_setup();

void setup() {
  // ===== DO NOT EDIT ANYTHING BELOW THIS LINE =====
  // ========== AUTO GENERATED CODE BEGIN ===========
  // async_tcp:
  // esphome:
  //   name: garage_hall_cam
  //   platform: ESP32
  //   board: nodemcu-32s
  //   build_path: garage_hall_cam
  //   arduino_version: espressif32@1.12.4
  //   platformio_options: {}
  //   includes: []
  //   libraries: []
  App.pre_setup("garage_hall_cam", __DATE__ ", " __TIME__);
  // logger:
  //   baud_rate: 115200
  //   level: DEBUG
  //   id: logger_logger
  //   tx_buffer_size: 512
  //   hardware_uart: UART0
  //   logs: {}
  logger_logger = new logger::Logger(115200, 512, logger::UART_SELECTION_UART0);
  logger_logger->pre_setup();
  App.register_component(logger_logger);
  // wifi:
  //   domain: ''
  //   use_address: 10.2.0.74
  //   id: wifi_wificomponent
  //   reboot_timeout: 15min
  //   power_save_mode: LIGHT
  //   fast_connect: false
  //   networks:
  //   - ssid: !secret 'wifi_ssid'
  //     password: !secret 'wifi_password'
  //     id: wifi_wifiap
  //     priority: 0.0
  wifi_wificomponent = new wifi::WiFiComponent();
  wifi_wificomponent->set_use_address("10.2.0.74");
  wifi::WiFiAP wifi_wifiap = wifi::WiFiAP();
  wifi_wifiap.set_ssid("...");
  wifi_wifiap.set_password("...");
  wifi_wifiap.set_priority(0.0f);
  wifi_wificomponent->add_sta(wifi_wifiap);
  wifi_wificomponent->set_reboot_timeout(900000);
  wifi_wificomponent->set_power_save_mode(wifi::WIFI_POWER_SAVE_LIGHT);
  wifi_wificomponent->set_fast_connect(false);
  App.register_component(wifi_wificomponent);
  // ota:
  //   id: ota_otacomponent
  //   safe_mode: true
  //   port: 3232
  //   password: ''
  ota_otacomponent = new ota::OTAComponent();
  ota_otacomponent->set_port(3232);
  ota_otacomponent->set_auth_password("");
  App.register_component(ota_otacomponent);
  ota_otacomponent->start_safe_mode();
  // mqtt:
  //   broker: 10.2.0.1
  //   port: 1883
  //   username: ''
  //   password: ''
  //   id: mqtt_mqttclientcomponent
  //   discovery: true
  //   discovery_retain: true
  //   discovery_prefix: homeassistant
  //   topic_prefix: garage_hall_cam
  //   keepalive: 15s
  //   reboot_timeout: 15min
  //   birth_message:
  //     topic: garage_hall_cam/status
  //     payload: online
  //     qos: 0
  //     retain: true
  //   will_message:
  //     topic: garage_hall_cam/status
  //     payload: offline
  //     qos: 0
  //     retain: true
  //   shutdown_message:
  //     topic: garage_hall_cam/status
  //     payload: offline
  //     qos: 0
  //     retain: true
  //   log_topic:
  //     topic: garage_hall_cam/debug
  //     qos: 0
  //     retain: true
  mqtt_mqttclientcomponent = new mqtt::MQTTClientComponent();
  App.register_component(mqtt_mqttclientcomponent);
  mqtt_mqttclientcomponent->set_broker_address("10.2.0.1");
  mqtt_mqttclientcomponent->set_broker_port(1883);
  mqtt_mqttclientcomponent->set_username("");
  mqtt_mqttclientcomponent->set_password("");
  mqtt_mqttclientcomponent->set_discovery_info("homeassistant", true);
  mqtt_mqttclientcomponent->set_topic_prefix("garage_hall_cam");
  mqtt_mqttclientcomponent->set_birth_message(mqtt::MQTTMessage{
      .topic = "garage_hall_cam/status",
      .payload = "online",
      .qos = 0,
      .retain = true,
  });
  mqtt_mqttclientcomponent->set_last_will(mqtt::MQTTMessage{
      .topic = "garage_hall_cam/status",
      .payload = "offline",
      .qos = 0,
      .retain = true,
  });
  mqtt_mqttclientcomponent->set_shutdown_message(mqtt::MQTTMessage{
      .topic = "garage_hall_cam/status",
      .payload = "offline",
      .qos = 0,
      .retain = true,
  });
  mqtt_mqttclientcomponent->set_log_message_template(mqtt::MQTTMessage{
      .topic = "garage_hall_cam/debug",
      .payload = "",
      .qos = 0,
      .retain = true,
  });
  mqtt_mqttclientcomponent->set_keep_alive(15);
  mqtt_mqttclientcomponent->set_reboot_timeout(900000);
  // json:
  // =========== AUTO GENERATED CODE END ============
  // ========= YOU CAN EDIT AFTER THIS LINE =========
  App.setup();
  cam_setup();
}

void loop() {
  App.loop();
}
