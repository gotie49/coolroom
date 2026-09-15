#include <DHT.h>

const int SENSOR_PIN = 2;
const int LED_PIN = 6;

#define SENSOR_TYPE DHT22 //NOTE: Wir haben in echt den DHT11

const float LED_MIN_TEMP = -10.0;
const float LED_MAX_TEMP = 40.0;

DHT sensor(SENSOR_PIN, SENSOR_TYPE);

void setup() {
  pinMode(LED_PIN, OUTPUT);
  Serial.begin(9600);
  sensor.begin();

  delay(2000); //NOTE: Sensor bruacht bisschen Zeit
}

void loop() {
  float temperature = sensor.readTemperature();

  if (isnan(temperature)) {
    analogWrite(LED_PIN, 0);
    Serial.println("ERR;B;SENSOR")
    delay(2000);
    return;
  }
  float fraction =
      (temperature - LED_MIN_TEMP) / (LED_MAX_TEMP - LED_MIN_TEMP);
  fraction = constrain(fraction, 0.0, 1.0);

  int brightness = (int)(fraction * 255.0 + 0.5);
  analogWrite(LED_PIN, brightness);

  // USB-Ausgabe: B;Temperatur_in_Grad_Celsius
  Serial.print("B;")
  Serial.println(temperature, 1);
  delay(2000);
}