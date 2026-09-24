#include <DHT.h>
#include <Wire.h>
#include <math.h>

const byte addr = 0x11;
volatile byte sensorData[3] = {0, 0, 2};

const int SENSOR_PIN = 2;
const int LED_PIN = 6;

#define SENSOR_TYPE DHT11

const float LED_MIN_TEMP = -10.0;
const float LED_MAX_TEMP = 40.0;

DHT sensor(SENSOR_PIN, SENSOR_TYPE);

void sendSensorData() {
  byte response[3];

  for (byte i = 0; i < 3; i++) {
    response[i] = sensorData[i];
  }

  Wire.write(response, sizeof(response));
}

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
  sensor.begin();

  Wire.begin(addr);

  //IMPORTANT: Interne Pull-ups für einen extern auf 3,3 V gezogenen Bus deaktivieren.
  digitalWrite(SDA, LOW);
  digitalWrite(SCL, LOW);

  Wire.onRequest(sendSensorData);

  delay(2000); //NOTE: Sensor braucht bisschen Zeit
}

void loop() {
  float temperature = sensor.readTemperature();

  if (isnan(temperature)) {
    analogWrite(LED_PIN, 0);

    noInterrupts();
    sensorData[0] = 0;
    sensorData[1] = 0;
    sensorData[2] = 1;
    interrupts();

    printDebugI2C();
    Serial.println("ERR;B;SENSOR");

    delay(2000);
    return;
  }

  float fraction =
      (temperature - LED_MIN_TEMP) / (LED_MAX_TEMP - LED_MIN_TEMP);
  fraction = constrain(fraction, 0.0, 1.0);

  int brightness = (int)(fraction * 255.0 + 0.5);
  analogWrite(LED_PIN, brightness);

  int16_t temperatureX10 = (int16_t)round(temperature * 10.0);
  uint16_t temperatureBits = (uint16_t)temperatureX10;

  noInterrupts();
  sensorData[0] = (byte)(temperatureBits & 0xFF);
  sensorData[1] = (byte)(temperatureBits >> 8);
  sensorData[2] = 0;
  interrupts();

  printDebugI2C();

  // USB-Ausgabe: B;Temperatur_in_Grad_Celsius
  Serial.print("B;");
  Serial.println(temperature, 1);
  delay(2000);
}

void printDebugI2C() {
  byte debugData[3];

  noInterrupts();
  for (byte i = 0; i < 3; i++) {
    debugData[i] = sensorData[i];
  }
  interrupts();

  Serial.print("I2C-Paket: [");

  for (byte i = 0; i < 3; i++) {
    if (i > 0) {
      Serial.print(", ");
    }
    Serial.print(debugData[i]);
  }

  Serial.println("]");
}