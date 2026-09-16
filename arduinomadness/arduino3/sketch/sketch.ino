#include <Servo.h>
#include <Wire.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>

const byte addr = 0x12;

const int SERVO_PIN = 9;
const int FAN_PIN = 5;  // In Wokwi: LED als Lüfter-Testanzeige

const int VALVE_CLOSED_ANGLE = 0;
const int VALVE_OPEN_ANGLE = 180;

const unsigned long COMMAND_TIMEOUT_MS = 5000;

Servo valve;

int fanPower = 0;
int valvePercent = 0;

unsigned long lastCommandTime = 0;
bool commandActive = false;

volatile byte actuatorData[3] = {0, 0, 1};

volatile byte pendingFan = 0;
volatile byte pendingValve = 0;
volatile bool commandPending = false;
volatile bool i2cErrorPending = false;

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

void updateStatus(byte status) {
  noInterrupts();

  actuatorData[0] = (byte)fanPower;
  actuatorData[1] = (byte)valvePercent;
  actuatorData[2] = status;

  interrupts();
}

void receiveI2C(int count) {
  if (count != 2 || Wire.available() != 2) {
    while (Wire.available() > 0) {
      Wire.read();
    }

    i2cErrorPending = true;
    return;
  }

  byte newFan = (byte)Wire.read();
  byte newValve = (byte)Wire.read();

  if (newValve > 100) {
    i2cErrorPending = true;
    return;
  }

  pendingFan = newFan;
  pendingValve = newValve;
  commandPending = true;
}

void sendActuatorData() {
  byte response[3];

  for (byte i = 0; i < 3; i++) {
    response[i] = actuatorData[i];
  }

  Wire.write(response, sizeof(response));
}

void acceptCommand(int newFan, int newValve) {
  fanPower = newFan;
  valvePercent = newValve;
  applyOutputs();

  lastCommandTime = millis();
  commandActive = true;
  updateStatus(0);

  printDebugI2C();

  Serial.print("OK;");
  Serial.print(fanPower);
  Serial.print(";");
  Serial.println(valvePercent);
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

  if (*position != '\0') {
    Serial.println("ERR;ACTOR;FORMAT");
    return;
  }

  acceptCommand((int)newFanPower, (int)newValvePercent);
}

void pollUSB() {
  for (byte i = 0; i < 40 && Serial.available() > 0; i++) {
    char incoming = (char)Serial.read();

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
}

void setup() {
  pinMode(FAN_PIN, OUTPUT);
  analogWrite(FAN_PIN, 0);

  valve.write(VALVE_CLOSED_ANGLE);
  valve.attach(SERVO_PIN);

  Serial.begin(9600);

  Wire.begin(addr);

  //IMPORTANT: Interne Pull-ups für einen extern auf 3,3 V gezogenen Bus deaktivieren.
  digitalWrite(SDA, LOW);
  digitalWrite(SCL, LOW);

  Wire.onReceive(receiveI2C);
  Wire.onRequest(sendActuatorData);

  Serial.println("READY;ACTOR");
}

void loop() {
  pollUSB();

  byte newFan;
  byte newValve;
  bool hasCommand;
  bool hasError;

  noInterrupts();

  hasCommand = commandPending;
  newFan = pendingFan;
  newValve = pendingValve;
  commandPending = false;

  hasError = i2cErrorPending;
  i2cErrorPending = false;

  interrupts();

  if (hasError) {
    Serial.println("ERR;ACTOR;I2C_COMMAND");
  }

  if (hasCommand) {
    acceptCommand(newFan, newValve);
  }

  if (commandActive &&
      millis() - lastCommandTime >= COMMAND_TIMEOUT_MS) {
    fanPower = 0;
    valvePercent = 0;
    applyOutputs();

    commandActive = false;
    updateStatus(2);

    printDebugI2C();

    Serial.println("ERR;ACTOR;TIMEOUT");
  }
}

void printDebugI2C() {
  byte debugData[3];

  noInterrupts();
  for (byte i = 0; i < 3; i++) {
    debugData[i] = actuatorData[i];
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