# Arduino Cloud am Laptop testen

Es handelt sich ausschliesslich um simulierte Daten, nicht um Messwerte des Trucks.
Die Simulation schreibt in das Thing des eingegebenen Geraets. Diese Daten gehoeren nicht in einen echten Temperaturnachweis.

## Start unter Windows PowerShell

```powershell
cd C:\Users\tiebeg\Desktop\coolroom
.\.venv-cloud\Scripts\python.exe cloud\test_cloud.py
```

Device-ID und Secret Key werden interaktiv abgefragt und nicht gespeichert.
Der Secret Key bleibt bei der Eingabe unsichtbar. Er gehoert nicht ins Repository.
Das Passwort ist der Geraete-Secret-Key, nicht das Arduino-Kontopasswort.

Das Dashboard muss die fuenf Variablen temperatur_ntc, temperatur_dht, tuer_offen,
luefter_pwm und klappe_prozent mit dem zugeordneten Thing verknuepfen.
Alle zehn Sekunden stellt der Simulator neue Werte bereit. Nach zehn Minuten endet die Testschleife;
Verbindungsversuche koennen diese Laufzeit verlaengern. Strg+C beendet auch einen laufenden Verbindungsversuch.
Eine Konsolenausgabe allein bestaetigt noch keine Speicherung. Den Empfang und Verlauf im Dashboard pruefen.

## Neuinstallation der Umgebung

```powershell
py -m venv .venv-cloud
.\.venv-cloud\Scripts\python.exe -m pip install -r cloud\requirements.txt
```

## Lokaler Test ohne Zugangsdaten

```powershell
.\.venv-cloud\Scripts\python.exe cloud\test_cloud.py --preview
```

Der Client verbindet sich mit iot.arduino.cc:8884 (TLS, Geraete-ID/Secret).
Zertifikats- und Hostnamenpruefung sind ausdruecklich aktiviert; die offizielle
Arduino-CA stammt aus dem Client-Paket. Das certifi-Paket stellt zusaetzlich die oeffentlichen Stammzertifikate bereit, die Python unter Windows nicht automatisch ueber diesen Client laedt. Bei Zertifikatsfehlern nicht die Pruefung abschalten.
Systemzeit, Client-Version und Netzverbindung pruefen.

Vor dem spaeteren Einsatz am Pi diesen Simulator beenden: Nicht gleichzeitig dieselbe
Geraete-ID von zwei Programmen verwenden. main.py und die Arduino-Sketches bleiben unveraendert.
Die echte MQTT-Cloud-Bruecke ist der anschliessende Arbeitsschritt.

Quelle: https://github.com/arduino/arduino-iot-cloud-py


## Windows-Zertifikate / Schulnetz

Der Simulator uebernimmt zusaetzlich die bereits im Betriebssystem vertrauten
CA-Zertifikate. Das ist bei diesem Laptop fuer die Zscaler-TLS-Inspektion erforderlich.
Zscaler terminiert und prueft dabei die TLS-Verbindung; es handelt sich nicht um eine
unveraenderte Ende-zu-Ende-TLS-Verbindung direkt zu Arduino. Fuer die
Sicherheitsdokumentation diese Netzwerkkomponente beruecksichtigen.
Es werden keine unbekannten Zertifikate automatisch akzeptiert.

# Echte MQTT-Werte uebertragen: cloud_bridge.py

Die Datei liegt im Repository-Root neben main.py. main.py, Mosquitto und die
Arduino-Sketches bleiben unveraendert. Kein direkter I2C-Zugriff durch die Bruecke.

## Auf den Pi kopieren

Nur cloud_bridge.py und cloud/requirements.txt werden fuer die Bruecke benoetigt.
Die Windows-Umgebung .venv-cloud NICHT kopieren. Auf dem Pi im Projektordner:

```bash
python3 -m venv .venv-cloud
.venv-cloud/bin/python -m pip install -r cloud/requirements.txt
.venv-cloud/bin/python cloud_bridge.py --dry-run
```

Bei fehlendem venv-Modul zuerst das Betriebssystempaket python3-venv installieren.
Fuer --dry-run muessen main.py und Mosquitto laufen. Es werden keine Daten in die
Cloud gesendet, keine Cloud-Zugangsdaten abgefragt und keine Aktoren angesteuert.
Danach mit Strg+C beenden und die Cloud-Uebertragung starten:

```bash
.venv-cloud/bin/python cloud_bridge.py
```

Device-/Client-ID des Geraets und Secret Key eingeben. Der Key wird nicht gespeichert.
Alternativ liest das Programm ARDUINO_DEVICE_ID und ARDUINO_SECRET_KEY aus der
Prozessumgebung (fuer einen spaeteren systemd-Dienst aus einer geschuetzten Datei
AUSSERHALB des Repositorys laden). Zugangsdaten nicht in Shell-Befehle einschreiben.
LOCAL_MQTT_USER und LOCAL_MQTT_PASSWORD sind optional fuer den lokalen Broker.

Vorher den Laptop-Simulator stoppen: dieselbe Cloud-Geraete-ID nur einmal verwenden.
In der Cloud alle fuenf Variablen als Read Only belassen.

## Verhalten und Grenzen

- Lokaler Broker: localhost:1883. Cloud: iot.arduino.cc:8884, TLS mit Zertifikats-
  und Hostnamenpruefung. Lokales MQTT ist standardmaessig unverschluesselt ueber Loopback.
- Die Cloud bekommt etwa alle 30 Sekunden aktuelle Werte. --interval aendert dies.
- Servo 0..180 Grad wird in 0..100 Prozent umgerechnet.
- Erst nach Empfang ALLER fuenf frischen Werte werden Daten bereitgestellt.
  Werte aelter als 15 Sekunden, ungueltige Nutzlasten und retained Nachrichten
  werden nicht als neue Messungen verwendet. --max-age aendert die Frist.
- Bei Verbindungsabbruechen versuchen die MQTT-Clients eine Neuverbindung.
- Das Cloud-Geraet kann online bleiben, obwohl main.py keine Daten mehr liefert.
  In diesem Fall bleiben die letzten Cloud-Werte stehen. Das Alter im Dashboard
  beachten; ein gesonderter Fehler-/Heartbeat-Kanal ist noch nicht vorhanden.
- Auf den bestehenden Aktor-Topics stehen Bedienbefehle UND bestaetigte Werte.
  Die Bruecke kann deren Herkunft nicht unterscheiden. Die Anzeige ist daher
  keine ausschliesslich bestaetigte Aktorrueckmeldung. Hierzu spaeter getrennte
  state-Topics in main.py und der Bruecke einfuehren.
- KEIN dauerhafter Offline-Puffer und KEIN Nachsenden historischer Messungen:
  Nach einem Ausfall werden nur wieder aktuelle Werte uebertragen. Die lokale
  SQLite-Protokollierung von main.py bleibt bestehen. Fuer eine vollstaendige
  Archivloesung fehlen Zeitstempel, dauerhafte Warteschlange und getesteter Import
  historischer Werte. On-change-Einstellungen der Cloud koennen gleiche Werte
  zusammenfassen. Konsolenausgaben bestaetigen nicht die dauerhafte Cloud-Speicherung.
- Die Prototyp-Authentifizierung uebernimmt bereits vom Betriebssystem vertraute
  CAs. Auf dem Schul-Laptop gehoert dazu Zscaler. Auf dem Pi kann der Truststore
  anders sein; Zertifikatsprobleme dort gezielt pruefen, niemals Pruefung abschalten.

## Warum ist .venv-cloud so gross?

Die virtuelle Umgebung enthaelt Python und installierte Bibliotheken, nicht nur
unseren Code. Sie ist lokal, in .gitignore ausgeschlossen und wird auf jedem
Betriebssystem aus requirements.txt neu erstellt. Die eigentlichen Projektdateien
sind cloud_bridge.py, cloud/test_cloud.py, cloud/requirements.txt und diese Anleitung.
