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

# LCD1602 am Aktor-Arduino anschließen

Dieser Plan gilt für das LCD1602 mit **16 Pins ohne I²C-Adapter**.

**Vor dem Verdrahten alle Versorgungen ausschalten.** Die Pinbeschriftungen am LCD beachten.

## Bauteile

- LCD1602
- 10-kΩ-Potentiometer
- 220-Ω-Widerstand
- Verbindungskabel

## Anschlussplan

| LCD-Pin | Bezeichnung | Anschluss |
|---|---|---|
| 1 | VSS | Arduino GND |
| 2 | VDD | Arduino 5V |
| 3 | VO – Kontrast | Mittlerer Anschluss des Potentiometers |
| 4 | RS | Arduino D7 |
| 5 | RW | Arduino GND |
| 6 | E | Arduino D8 |
| 7–10 | D0–D3 | Nicht anschließen |
| 11 | D4 | Arduino D4 |
| 12 | D5 | Arduino D6 |
| 13 | D6 | Arduino D10 |
| 14 | D7 | Arduino D11 |
| 15 | A / LED+ | Über 220 Ω an Arduino 5V |
| 16 | K / LED− | Arduino GND |

**Achtung:** LCD-D5 wird mit **Arduino D6** verbunden.
Arduino D5 bleibt für den Lüfter, D9 für den Servo und A4/A5 für I²C reserviert.

## Potentiometer

| Anschluss | Verbindung |
|---|---|
| Ein äußerer Anschluss | Arduino 5V |
| Anderer äußerer Anschluss | Arduino GND |
| Mittlerer Anschluss | LCD-Pin 3 (VO) |

Am Potentiometer drehen, um den Kontrast einzustellen.

**LCD und Potentiometer mit Arduino-5V versorgen. Diese Leitung nicht mit der externen Motor-5V-Schiene verbinden. Die Masse ist gemeinsam.**

## Sketch

Bibliothek: **LiquidCrystal von Arduino**

Die Pinbelegung im Sketch lautet:

```cpp
// RS, E, LCD-D4, LCD-D5, LCD-D6, LCD-D7
LiquidCrystal lcd(7, 8, 4, 6, 10, 11);
```

Den aktualisierten Sketch auf Arduino 3 hochladen.

## Anzeige

```text
Ventil:  50%
Luefter: 69%
```

Angezeigt werden die eingestellte Klappenöffnung und die Lüfteransteuerung in Prozent – keine gemessene Position oder Drehzahl.