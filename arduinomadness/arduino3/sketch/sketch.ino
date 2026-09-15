#include <Servo.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

const int SERVO_PIN = 9;
const int FAN_PIN = 5; //NOTE: Simuliert als LED, da kein Gleichstrommotor in Wokwi exisitiert

const int VALVE_CLOSED_ANGLE = 0;
const int VALVE_OPEN_ANGLE = 180;

const unsigned long COMMAND_TIMEOUT_MS = 5000;

Servo valve;

int fanPower = 0;
int valvePercent = 0;

unsigned long lastCommandTime = 0;
bool commandActive = false;

char receiveBuffer[40];
size_t receiveLength = 0;
bool lineTooLong = false;

void applyOutputs() {
  analogWrite(FAN_PIN, fanPower);

  int angle = map(
      valvePercent, 0, 100,
      VALVE_CLOSED_ANGLE, VALVE_OPEN_ANGLE
  );

  valve.write(angle);
}

bool readValue(char *&position, long maximum, long &value) {
  if (*position < '0' || *position > '9') {
    return false;
  }

  char *end;
  errno = 0;
  value = strtol(position, &end, 10);

  if (errno == ERANGE || value < 0 || value > maximum) {
    return false;
  }

  position = end;
  return true;
}

void processCommand(char *command) {
  // Erwartetes Format: SET;Lüfterwert;Klappenprozent
  if (strncmp(command, "SET;", 4) != 0) {
    Serial.println("ERR;ACTOR;COMMAND");
    return;
  }

  char *position = command + 4;
  long newFanPower;
  long newValvePercent;

  if (!readValue(position, 255, newFanPower)) {
    Serial.println("ERR;ACTOR;FAN");
    return;
  }

  if (*position != ';') {
    Serial.println("ERR;ACTOR;FORMAT");
    return;
  }
  position++;

  if (!readValue(position, 100, newValvePercent)) {
    Serial.println("ERR;ACTOR;VALVE");
    return;
  }

  // Nach dem letzten Wert darf kein weiterer Text stehen
  if (*position != '\0') {
    Serial.println("ERR;ACTOR;FORMAT");
    return;
  }

  // Erst einen vollständig gültigen Befehl übernehmen
  fanPower = (int)newFanPower;
  valvePercent = (int)newValvePercent;
  applyOutputs();

  lastCommandTime = millis();
  commandActive = true;

  // Bestätigung über USB senden
  Serial.print("OK;");
  Serial.print(fanPower);
  Serial.print(";");
  Serial.println(valvePercent);
}

void setup(){
  pinMode(FAN_PIN, OUTPUT);
  analogWrite(FAN_PIN, 0);

  valve.write(VALVE_CLOSED_ANGLE);
  valve.attach(SERVO_PIN);

  Serial.begin(9600);
  Serial.println("READY;ACTOR");
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = (char)Serial.read();

    // Unterstützt sowohl LF als auch CRLF als Zeilenende
    if (incoming == '\r') {
      continue;
    }

    if (incoming == '\n') {
      if (lineTooLong) {
        Serial.println("ERR;ACTOR;LINE_TOO_LONG");
      } else if (receiveLength > 0) {
        receiveBuffer[receiveLength] = '\0';
        processCommand(receiveBuffer);
      }

      receiveLength = 0;
      lineTooLong = false;
    } else if (!lineTooLong) {
      if (receiveLength < sizeof(receiveBuffer) - 1) {
        receiveBuffer[receiveLength++] = incoming;
      } else {
        lineTooLong = true;
      }
    }
  }

  if (commandActive &&
      millis() - lastCommandTime >= COMMAND_TIMEOUT_MS) {
    fanPower = 0;
    valvePercent = 0;
    applyOutputs();

    commandActive = false;
    Serial.println("ERR;ACTOR;TIMEOUT");
  }
}