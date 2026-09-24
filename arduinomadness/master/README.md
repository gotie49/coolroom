# Raspberry-Pi-Steuerung

`main.py` steuert die drei Unos ueber I2C. MQTT und SQLite bleiben aktiv.

## Start auf dem Pi

I2C mit `sudo raspi-config` aktivieren. Im Ordner mit `main.py`:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install smbus2 'paho-mqtt>=2,<3'
python main.py
```

Falls `venv` fehlt: `sudo apt install python3-venv`.
Mit Strg+C beenden; das Skript sendet einen Stoppbefehl und prueft die Rueckmeldung.
Auch SIGTERM und das Schliessen der SSH-Sitzung (SIGHUP) loesen diesen Ablauf aus.

## Einstellungen oben in main.py

- `SOLL_TEMPERATUR = 27.0`: Sollwert fuer den Raumtemperaturtest; die bisherige Begrenzung auf -10 bis +10 Grad C ist entfernt.
- `HYSTERESE = 1.0`: Kuehlung startet bei >=28 C und endet bei <=26 C. Dazwischen bleibt der vorherige Ein-/Aus-Zustand bestehen.
- Nur Sensor B (DHT11, 0x11) regelt. Sensor A (NTC) wird weiterhin angezeigt und gespeichert; sein unkalibrierter Temperaturwert beeinflusst die Stellwerte nicht. Sein Tuerkontakt bleibt aktiv.
- Bei offener Tuer: Luefter aus und Klappe geschlossen. Nach Schliessen startet die Kuehlung wieder, wenn die Einschaltschwelle erreicht ist.
- Bei aktiver Kuehlung steigen PWM und Klappenoeffnung mit der Temperatur. Ab Soll+5 C werden 255 und 100 Prozent gesendet. Mindestwerte: PWM 128, Klappe 20 Prozent. Ob der Motor bei PWM 128 anlaeuft, muss praktisch geprueft werden.
- Bei 26 C bleibt die Kuehlung aus. Ab 28 C beginnt die Kuehlung; ab 32 C wird volle Leistung angefordert. Der Luefter erzeugt keine Kaelte: Es braucht eine externe Kaeltequelle hinter der Klappe.
- `BROKER = "10.110.177.32"`: bisherige Broker-IP beibehalten; bei Bedarf aendern.
- `MQTT_AKTIV` und `DB_AKTIV` lassen sich einzeln auf `False` setzen.

## Datenformat

| Board | Adresse | Paket |
|---|---|---|
| Sensor A | 0x10 | Lesen: Temperatur Low, High, Tuer, Status (4 Bytes) |
| Sensor B | 0x11 | Lesen: Temperatur Low, High, Status (3 Bytes) |
| Aktor | 0x12 | Schreiben: PWM 0..255, Klappe 0..100 (2 Bytes) |
| Aktor | 0x12 | Lesen: PWM, Klappe, Status (3 Bytes) |

Temperatur: vorzeichenbehaftete 16-Bit-Zahl, Little Endian, geteilt durch 10 ergibt Grad C.
Nur Sensorstatus 0 ist gueltig; Status 1 bedeutet Fehler, 2 bedeutet noch kein Messwert.
I2C-Nachrichten enthalten kein zusaetzliches Registerbyte.
Die Aktor-Rueckmeldung wird bis zu 0,4 Sekunden abgefragt, da der Uno Befehle erst in seiner Hauptschleife uebernimmt. Sie bestaetigt Stellwerte, keine gemessene Drehzahl/Position.
Befehle werden etwa einmal pro Sekunde erneuert. Nach 5 Sekunden ohne gueltigen Befehl schaltet der Arduino selbst ab.

## Fehlerverhalten

Bei Sensorfehlern, I2C-Fehlern, fehlender Aktorbestaetigung oder Datenbankfehlern versucht das Skript, den Aktor zu stoppen, und beendet sich mit Fehlercode 1. Nach Fehlerbehebung neu starten.
Ein nicht erreichbarer MQTT-Broker blockiert die Regelung nicht; waehrenddessen werden keine MQTT-Messwerte nachgeliefert.

## MQTT und SQLite

MQTT-Payloads sind Zahlen als Text (ohne den bisherigen Praefix `Temperature:`):

- `temperature/0x10/room`: Temperatur A in C
- `door/0x10/state`: 0 geschlossen, 1 offen
- `temperature/0x11/room`: Temperatur B in C
- `aktor/0x12/servo`: bestaetigte Klappenoeffnung in Prozent
- `aktor/0x12/propeller`: bestaetigter PWM-Wert 0..255

Bestehende MQTT-Abonnenten muessen diese Topics und Payloads verwenden.
Die Aktortopics sind Rueckmeldungen; Steuerung per MQTT ist nicht implementiert.
Bei Programmende wird keine abschliessende MQTT-Stoppmeldung garantiert.

`Icetruck.db` liegt neben `main.py`. Temperaturwerte bleiben in `MEASUREMENTS (ARD_ID, SENSOR_ID, TEMP)`, Sensor-ID jeweils 0. Der Tuerzustand kommt in die neue Tabelle `DOOR_STATES` mit Zeitstempel. Fehlende Tabellen werden angelegt, vorhandene nicht ersetzt. Falls die alte Datenbank woanders liegt, vor dem Start `DB_DATEI` entsprechend einstellen.

## Praktische Grenzen

Der einstellbare Sollbereich ist keine Bestaetigung, dass die vorhandenen Sensoren im ganzen Bereich ausreichend genau messen. Vor Tests unter 0 C den Messbereich der konkreten DHT11-Version klaeren und den NTC kalibrieren. Der NTC muss vor seiner spaeteren Verwendung zur Regelung kalibriert werden. Ein gemeldeter Sensorfehler auf Board A oder dessen Ausfall beendet den Test weiterhin, da dieses Board auch den Tuerkontakt liefert.
Das aktuelle Arduino-Protokoll enthaelt keine Messzeit oder laufende Nummer: Ein eingefrorener, weiterhin antwortender Sensor ist nicht sicher erkennbar.
Die Software behebt keine I2C-Pegelprobleme zwischen Pi und 5-V-Unos. Busverdrahtung/Pull-ups sowie die Versorgung von Motor und Servo muessen separat geprueft sein.

## Lokale Tests ohne Hardware

```bash
python -B test_main.py
```

Simulierte I2C-Antworten pruefen Paketformat, Vorzeichen, Fehler, Aktorbestaetigung, Regelung, MQTT-Payloads und SQLite-Eintraege. Kein Test am echten Pi/Broker wurde ausgefuehrt.

API-Referenzen: [smbus2](https://smbus2.readthedocs.io/en/latest/operations.html), [Paho MQTT](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html).

## Raumtemperaturtest durchfuehren

1. Alle drei Adressen muessen erreichbar sein; einen bereits laufenden Regler vorher stoppen.
2. Skript starten. Tuerkontakt geschlossen halten (bei eurem Taster: gedrueckt).
3. Bei DHT-Anzeige <=26 C muessen Luefter und Klappe ausgeschaltet/geschlossen bleiben, auch wenn der NTC 46.7 C zeigt.
4. Den DHT vorsichtig mit der Hand erwaermen. Ab 28 C starten Luefter und Klappe. Mit steigender Temperatur steigt die Ansteuerung.
5. Hand entfernen. Bei <=26 C stoppt die Kuehlung; bei 27 C bleibt ein bereits gestarteter Kuehlvorgang aktiv.
6. Taster loslassen (Tuer offen): Luefter aus und Klappe geschlossen, unabhaengig von der Temperatur.
7. Mit Strg+C beenden. Ohne externe Kaeltequelle ist dies ein Test der Regelungsreaktion, kein Nachweis einer Abkuehlung unter Raumtemperatur.
