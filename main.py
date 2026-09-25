"""Kuehlraumregelung fuer drei Unos; MQTT/SQLite protokollieren Messwerte.

Raumtemperaturtest: Nur der DHT11 regelt; der NTC wird protokolliert.
Der Luefter erzeugt selbst keine Kaelte.
"""

import math
import signal
import sqlite3
import time
from pathlib import Path

SENSOR_A = 0x10
SENSOR_B = 0x11
AKTOR = 0x12
I2C_BUS = 1
INTERVALL = 1.0  # Sekunden; Aktor-Timeout: 5 Sekunden

SOLL_TEMPERATUR = 27.0  # Raumtemperaturtest: an bei 28 C, aus bei 26 C
HYSTERESE = 1.0        # Start bei Soll+1, Stopp bei Soll-1
VOLLE_LEISTUNG_AB = 5.0  # Grad ueber Soll: volle Luefter-/Klappenansteuerung
MIN_LUEFTER = 128      # Mindest-PWM beim Kuehlen; am echten Motor pruefen
MIN_KLAPPE = 20        # Mindestoeffnung beim Kuehlen in Prozent

MQTT_AKTIV = True
DB_AKTIV = True
BROKER = "localhost"
PORT = 1883
DB_DATEI = Path(__file__).with_name("Icetruck.db")


def lesen(bus, adresse, anzahl):
    from smbus2 import i2c_msg

    # Kein Registerbyte voranstellen: Unsere Unos erwarten rohe I2C-Pakete.
    nachricht = i2c_msg.read(adresse, anzahl)
    bus.i2c_rdwr(nachricht)
    return bytes(nachricht)


def sensor_lesen(bus, adresse):
    daten = lesen(bus, adresse, 4 if adresse == SENSOR_A else 3)
    status = daten[-1]
    if status != 0:
        text = {1: "Sensorfehler", 2: "noch kein Messwert"}.get(
            status, "unbekannter Status"
        )
        raise ValueError(f"Sensor 0x{adresse:02x}: {text} ({status})")
    temperatur = int.from_bytes(daten[:2], "little", signed=True) / 10.0
    tuer = daten[2] if adresse == SENSOR_A else None
    if tuer is not None and tuer not in (0, 1):
        raise ValueError(f"Ungueltiger Tuerzustand: {tuer}")
    return temperatur, tuer


def stellen(bus, luefter, klappe):
    from smbus2 import i2c_msg

    if not 0 <= luefter <= 255 or not 0 <= klappe <= 100:
        raise ValueError("Luefter muss 0..255, Klappe 0..100 sein")
    bus.i2c_rdwr(i2c_msg.write(AKTOR, [luefter, klappe]))


def stellen_und_pruefen(bus, luefter, klappe):
    stellen(bus, luefter, klappe)
    # Der Uno uebernimmt den Befehl erst in loop(), nicht im I2C-Interrupt.
    ende = time.monotonic() + 0.4
    while time.monotonic() < ende:
        time.sleep(0.02)
        rueckmeldung = lesen(bus, AKTOR, 3)
        if rueckmeldung == bytes([luefter, klappe, 0]):
            return
    raise OSError("Aktor bestaetigt Stellwerte nicht innerhalb von 0,4 s")


class Regelung:
    def __init__(self):
        self.kuehlen = False

    def berechnen(self, temp_b, tuer):
        # NTC ist noch nicht kalibriert und beeinflusst die Stellwerte nicht.
        if tuer == 1:
            self.kuehlen = False
        elif temp_b >= SOLL_TEMPERATUR + HYSTERESE:
            self.kuehlen = True
        elif temp_b <= SOLL_TEMPERATUR - HYSTERESE:
            self.kuehlen = False

        if not self.kuehlen:
            return 0, 0
        anteil = max(0.0, min(1.0,
            (temp_b - SOLL_TEMPERATUR) / VOLLE_LEISTUNG_AB
        ))
        luefter = round(MIN_LUEFTER + anteil * (255 - MIN_LUEFTER))
        klappe = round(MIN_KLAPPE + anteil * (100 - MIN_KLAPPE))
        return luefter, klappe


def zyklus(bus, regelung):
    # Bei Fehlern sendet main() den Stoppbefehl und beendet das Programm.
    temp_a, tuer = sensor_lesen(bus, SENSOR_A)
    temp_b, _ = sensor_lesen(bus, SENSOR_B)
    luefter, klappe = regelung.berechnen(temp_b, tuer)
    stellen_und_pruefen(bus, luefter, klappe)
    return temp_a, tuer, temp_b, luefter, klappe


def connect_mqtt():
    from paho.mqtt import client as mqtt_client

    def on_connect(client, userdata, flags, reason_code, properties):
        print(f"MQTT-Verbindungsstatus: {reason_code}", flush=True)

    client = mqtt_client.Client(
        callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
    )
    client.on_connect = on_connect
    # Broker-Ausfall darf die I2C-Befehle nicht blockieren.
    client.connect_async(BROKER, PORT)
    client.loop_start()
    return client


def publish(client, temp_a, tuer, temp_b, luefter, klappe):
    if not client.is_connected():
        return
    for topic, wert in (
        ("temperature/0x10/room", temp_a),
        ("door/0x10/state", tuer),
        ("temperature/0x11/room", temp_b),
        ("aktor/0x12/servo", klappe),
        ("aktor/0x12/propeller", luefter),
    ):
        result = client.publish(topic, str(wert))
        if result.rc != 0:
            print(f"MQTT konnte {topic} nicht einreihen: {result.rc}")


def datenbank_oeffnen():
    conn = sqlite3.connect(DB_DATEI, timeout=0.2)
    # Vorhandene Tabellen werden nicht ersetzt.
    conn.execute("""CREATE TABLE IF NOT EXISTS MEASUREMENTS (
        ARD_ID INTEGER, SENSOR_ID INTEGER, TEMP REAL
    )""")
    # Tuerzustand separat speichern, nicht als vermeintliche Temperatur.
    conn.execute("""CREATE TABLE IF NOT EXISTS DOOR_STATES (
        RECORDED_AT TEXT DEFAULT CURRENT_TIMESTAMP,
        ARD_ID INTEGER, IS_OPEN INTEGER
    )""")
    conn.commit()
    return conn


def speichern(conn, temp_a, tuer, temp_b):
    with conn:
        conn.executemany(
            "INSERT INTO MEASUREMENTS (ARD_ID, SENSOR_ID, TEMP) VALUES (?, ?, ?)",
            [(SENSOR_A, 0, temp_a), (SENSOR_B, 0, temp_b)],
        )
        conn.execute(
            "INSERT INTO DOOR_STATES (ARD_ID, IS_OPEN) VALUES (?, ?)",
            (SENSOR_A, tuer),
        )


def beenden(signum, frame):
    raise KeyboardInterrupt


def main():
    from smbus2 import SMBus

    if not math.isfinite(SOLL_TEMPERATUR):
        raise ValueError("Solltemperatur muss eine endliche Zahl sein")
    if not (0 < HYSTERESE < VOLLE_LEISTUNG_AB and
            0 <= MIN_LUEFTER <= 255 and 0 <= MIN_KLAPPE <= 100):
        raise ValueError("Ungueltige Regelungsparameter")
    regelung = Regelung()
    signal.signal(signal.SIGTERM, beenden)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, beenden)

    bus = None
    client = None
    conn = None
    exit_code = 0
    try:
        bus = SMBus(I2C_BUS)
        stellen_und_pruefen(bus, 0, 0)
        if MQTT_AKTIV:
            client = connect_mqtt()
        if DB_AKTIV:
            conn = datenbank_oeffnen()
        time.sleep(2)  # Sensoren nach einem Neustart anlaufen lassen

        while True:
            start = time.monotonic()
            temp_a, tuer, temp_b, luefter, klappe = zyklus(bus, regelung)
            print(
                f"NTC (nur Anzeige): {temp_a:.1f} C | DHT (Regelung): {temp_b:.1f} C | "
                f"Tuer: {'offen' if tuer else 'geschlossen'} | "
                f"Soll: {SOLL_TEMPERATUR:.1f} C | "
                f"Bestaetigt: Luefter={luefter}, Klappe={klappe}%",
                flush=True,
            )
            if client is not None:
                publish(client, temp_a, tuer, temp_b, luefter, klappe)
            if conn is not None:
                speichern(conn, temp_a, tuer, temp_b)
            time.sleep(max(0, INTERVALL - (time.monotonic() - start)))

    except KeyboardInterrupt:
        print("\nProgramm beendet.")
    except (OSError, ValueError, sqlite3.Error, ImportError) as fehler:
        print(f"Fehler: {fehler}", flush=True)
        exit_code = 1
    finally:
        if bus is not None:
            try:
                stellen_und_pruefen(bus, 0, 0)
                print("Aktor bestaetigt: Luefter aus, Klappe geschlossen.")
            except (OSError, ValueError):
                print("Stopp nicht bestaetigt; Arduino-Timeout greift nach 5 s.")
            finally:
                bus.close()
        if client is not None:
            client.disconnect()
            client.loop_stop()
        if conn is not None:
            conn.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
