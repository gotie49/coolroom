# Arduino-Prototyp 
- **Arduino 1:** NTC, Türkontakt und zwei Status-LEDs.
- **Arduino 2:** DHT-Temperatursensor und Temperatur-LED.
- **Arduino 3:** Servo und Lüftersteuerung; in Wokwi ersetzt eine LED den Gleichstrommotor.

## USB-Datenformat

9600 Baud, eine Nachricht pro Zeile:

| Nachricht | Bedeutung |
|---|---|
| `A;23.4;0` | Sensor A: Temperatur in °C, Tür 0 = zu / 1 = offen |
| `B;23.8` | Sensor B: Temperatur in °C |
| `SET;128;50` | Aktorbefehl: Lüfter 0–255, Klappe 0–100 % |
| `OK;128;50` | Aktor bestätigt übernommene Werte |
| `ERR;…` | Fehler oder Zeitüberschreitung |

Ohne gültigen Befehl für fünf Sekunden schaltet der Aktor den Lüfter aus und schließt die Klappe.

## Reale Hardware

- Sensor B: `DHT22` durch `DHT11` ersetzen.
- NTC-Kennwerte und Spannungsteiler prüfen.
- Motor über L293D betreiben; Motor und Servo benötigen eine geeignete separate Versorgung mit gemeinsamer Masse zum Aktor.
- Power Supply Module für externe 5V Versorgung.

```text 
                      Kerbe
                   ┌────∪────┐
Arduino D5 ───── 1 │         │ 16 ───── Arduino 5V
Arduino 5V ───── 2 │         │ 15 ───── GND
Motorkabel 1 ─── 3 │         │ 14 ───── frei
GND ──────────── 4 │  L293D  │ 13 ───── GND
GND ──────────── 5 │         │ 12 ───── GND
Motorkabel 2 ─── 6 │         │ 11 ───── frei
GND ──────────── 7 │         │ 10 ───── GND
Externe 5V ───── 8 │         │  9 ───── GND
                   └─────────┘
```

### Wichtig
Interne Pull-ups für einen extern auf 3,3 V gezogenen Bus deaktivieren. In der `Wire.h` Bibliothek.
```code
$ cd ..\libraries\Wire\src\utility\twi.c
digitalWrite(SDA, LOW);
digitalWrite(SCL, LOW);
```

### I2C-Datenformat
- **Sensor A (`0x10`):** Lesen `[Temperatur Low, Temperatur High, Tür, Status]`; Tür: `0=zu`, `1=offen`.
- **Sensor B (`0x11`):** Lesen `[Temperatur Low, Temperatur High, Status]`; Sensorstatus: `0=gültig`, `1=Fehler`, `2=noch kein Wert`.
- **Temperatur:** Vorzeichenbehaftete 16-Bit-Zahl, Little Endian, in 0,1 °C (`234=23,4 °C`); bei Status ≠ 0 ignorieren.
- **Aktor (`0x12`):** Schreiben `[Lüfter 0–255, Klappe 0–100 %]`; Lesen `[übernommener Lüfterwert, Klappenwert, Status]`; Status: `0=aktiv`, `1=kein Befehl`, `2=Timeout`.
- **Zeitüberwachung:** Stellbefehl jede Sekunde senden; nach 5 Sekunden ohne gültigen Befehl Lüfter aus, Klappe zu, Status `[0,0,2]`; Lesen verlängert die Frist nicht.