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