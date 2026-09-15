//NOTE: Tempsensor ist in der Realität ein anderer (generischer Them)
#include <math.h>

const int TEMP_PIN = A0;
const int LEDTEMP_PIN = 3;

const int DOOR_PIN = 2;
const int LEDDOOR_PIN = 4;

const float FIXED_RESISTOR = 10000.0;  // Fester Widerstand in Ohm
const float NTC_AT_25 = 10000.0;       // NTC-Widerstand bei 25 °C
const float BETA = 3950.0;            // Beta-Wert des NTC in Kelvin
const float REFERENCE_TEMP_K = 298.15; // 25 °C in Kelvin

const float LED_MIN_TEMP = -10.0;  // LED aus
const float LED_MAX_TEMP = 40.0;   // LED maximal hell

void setup() {
  pinMode(DOOR_PIN, INPUT_PULLUP);
  pinMode(LEDDOOR_PIN, OUTPUT);
  pinMode(LEDTEMP_PIN, OUTPUT);

  Serial.begin(9600);
}

void loop() {
  // Tür: 0 = geschlossen, 1 = offen
  int doorOpen = digitalRead(DOOR_PIN);
  digitalWrite(LEDDOOR_PIN, doorOpen);

  int measurement = analogRead(TEMP_PIN);

  if (measurement <= 0 || measurement >= 1023) {
    analogWrite(LEDTEMP_PIN, 0);

    Serial.print("ERR;A;SENSOR;");
    Serial.println(doorOpen);

    delay(200);
    return;
  }

  float temperature =
      1.0 / (1.0 / REFERENCE_TEMP_K
             + log(ntcResistance / NTC_AT_25) / BETA)
      - 273.15;

  float fraction =
      (temperature - LED_MIN_TEMP) / (LED_MAX_TEMP - LED_MIN_TEMP);
  fraction = constrain(fraction, 0.0, 1.0);

  int brightness = (int)(fraction * 255.0 + 0.5);
  analogWrite(LEDTEMP_PIN, brightness);

  // USB-Ausgabe: A;Temperatur_in_Grad_Celsius;Türzustand
  Serial.print("A;");
  Serial.print(temperature, 1);
  Serial.print(";");
  Serial.println(doorOpen);

  delay(200);
}