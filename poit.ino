#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <time.h>

#define RELAY_PIN 27
#define SOIL_PIN 34

const char* ssid = "wifi name";
const char* password = "wifi password";

//const char* dataUrl = "server ip:5000/data";
//const char* statusUrl = "server ip:5000/status";

const char* statusUrl = "server ip:5000/status";
const char* dataUrl   = "server ip:5000/data";


int threshold = 2000;

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // alapból KI

  WiFi.begin(ssid, password);
  Serial.print("WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected: " + WiFi.localIP().toString());

  // idő szinkron NTP-vel
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.print("Time...");
  while (time(nullptr) < 100000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(" OK!");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    HTTPClient statusHttp;
    statusHttp.begin(statusUrl);
    int statusCode = statusHttp.GET();

    if (statusCode == 200) {
      String statusBody = statusHttp.getString();
      StaticJsonDocument<200> statusDoc;
      DeserializationError error = deserializeJson(statusDoc, statusBody);

      if (!error) {
        bool initialized = statusDoc["initialized"];
        bool monitoring = statusDoc["monitoring"];

        if (statusDoc.containsKey("threshold")) {
          threshold = statusDoc["threshold"].as<int>();
        }

        String mode = "auto";
        int remotePumpState = 0;
        if (statusDoc.containsKey("mode")) {
          mode = statusDoc["mode"].as<String>();
        }
        if (statusDoc.containsKey("pump")) {
          remotePumpState = statusDoc["pump"].as<int>();
        }

        if (initialized) {
          int soilValue = analogRead(SOIL_PIN);
          int pumpState;

          if (mode == "auto") {
            pumpState = (soilValue >= threshold) ? 1 : 0;
          } else {
            pumpState = remotePumpState;
          }

          digitalWrite(RELAY_PIN, pumpState ? LOW : HIGH);

          Serial.print("Soil: "); Serial.print(soilValue);
          Serial.print(" | Pump: "); Serial.print(pumpState);
          Serial.print(" | Mode: "); Serial.println(mode);

          if (monitoring) {
            time_t now = time(nullptr);
            struct tm* t = localtime(&now);
            char isoTime[30];
            strftime(isoTime, sizeof(isoTime), "%Y-%m-%dT%H:%M:%S", t);

            HTTPClient dataHttp;
            dataHttp.begin(dataUrl);
            dataHttp.addHeader("Content-Type", "application/json");

            StaticJsonDocument<200> dataJson;
            dataJson["soil"] = soilValue;
            dataJson["pump"] = pumpState;
            dataJson["timestamp"] = isoTime;

            String payload;
            serializeJson(dataJson, payload);
            int httpCode = dataHttp.POST(payload);
            Serial.print("POST: ");
            Serial.println(httpCode);
            dataHttp.end();
          }
        } else {
          Serial.println("Waiting for initialization. The pump is currently OFF.");
          digitalWrite(RELAY_PIN, HIGH);
        }
      }
    } else {
      Serial.print("Error /status: ");
      Serial.println(statusCode);
    }

    statusHttp.end();
  }

  delay(3000);
}


