"""IceTruck: lokale MQTT-Werte an Arduino Cloud weitergeben (keine I2C-Steuerung).

Start: python3 cloud_bridge.py
Zugangsdaten interaktiv oder ARDUINO_DEVICE_ID / ARDUINO_SECRET_KEY.
Nur MQTT pruefen: python3 cloud_bridge.py --dry-run
Diese Live-Bruecke ist KEIN historischer Offline-Puffer.
"""
import argparse
import getpass
import logging
import math
import os
import signal
import ssl
import sys
import threading
import time

TOPICS = {
    "temperature/0x10/room": "temperatur_ntc",
    "temperature/0x11/room": "temperatur_dht",
    "door/0x10/state": "tuer_offen",
    "aktor/0x12/propeller": "luefter_pwm",
    "aktor/0x12/servo": "klappe_prozent",
}
LOG = logging.getLogger("cloud_bridge")


def decode(topic, payload):
    """MQTT-Einheiten in die fuenf Cloud-Variablen umrechnen."""
    name = TOPICS[topic]
    value = float(payload)
    if not math.isfinite(value):
        raise ValueError("Wert ist nicht endlich")
    if name.startswith("temperatur_"):
        if not -3276.8 <= value <= 3276.7:
            raise ValueError("Temperatur ausserhalb des I2C-Datenformats")
        return name, value
    maximum = {"tuer_offen": 1, "luefter_pwm": 255, "klappe_prozent": 180}[name]
    if not value.is_integer() or not 0 <= value <= maximum:
        raise ValueError("Ungueltiger Zustand oder Stellwert")
    if name == "tuer_offen":
        return name, bool(value)
    if name == "klappe_prozent":
        return name, int(value * 100 / 180 + 0.5)
    return name, int(value)


class LatestValues:
    """Thread-sicherer Speicher aktueller Werte, keine dauerhafte Warteschlange."""
    def __init__(self, max_age=15.0):
        self.max_age = max_age
        self.lock = threading.Lock()
        self.values = {}
        self.online = False

    def connection(self, online):
        with self.lock:
            self.online = online
            self.values.clear()

    def receive(self, topic, payload, retained=False, now=None):
        if topic not in TOPICS or retained:
            return
        now = time.monotonic() if now is None else now
        try:
            name, value = decode(topic, payload)
        except (ValueError, TypeError, OverflowError):
            with self.lock:
                self.values.pop(TOPICS[topic], None)
            raise ValueError("Ungueltige MQTT-Nachricht") from None
        with self.lock:
            if self.online:
                self.values[name] = (value, now)

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        with self.lock:
            if not self.online or len(self.values) != len(TOPICS):
                return None
            if any(now - stamp > self.max_age for _, stamp in self.values.values()):
                return None
            return {name: value for name, (value, _) in self.values.items()}


def tls_parameters():
    import certifi
    from arduino_iot_cloud import CADATA
    # Uebernimmt auch bereits in Windows vertraute Schulnetz-/Zscaler-CAs.
    context = ssl.create_default_context()
    pem = "".join(ssl.DER_cert_to_PEM_cert(cert)
                  for cert in context.get_ca_certs(binary_form=True))
    return {"verify_mode": ssl.CERT_REQUIRED,
            "server_hostname": "iot.arduino.cc",
            "cadata": pem + ssl.DER_cert_to_PEM_cert(CADATA),
            "cafile": certifi.where()}


def start_mqtt(args, latest):
    from paho.mqtt import client as mqtt
    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         protocol=mqtt.MQTTv311)
    if os.getenv("LOCAL_MQTT_USER"):
        client.username_pw_set(os.environ["LOCAL_MQTT_USER"],
                               os.getenv("LOCAL_MQTT_PASSWORD"))

    def on_connect(client, userdata, flags, reason_code, properties):
        success = reason_code == 0
        latest.connection(success)
        if success:
            client.subscribe([(topic, 1) for topic in TOPICS])
            LOG.warning("Lokales MQTT verbunden; warte auf alle fuenf aktuellen Werte.")
        else:
            LOG.warning("MQTT-Anmeldung abgelehnt: %s", reason_code)

    def on_message(client, userdata, message):
        try:
            latest.receive(message.topic, message.payload, message.retain)
        except ValueError:
            LOG.warning("Ungueltiger Wert auf %s verworfen.", message.topic)

    def on_disconnect(client, userdata, flags, reason_code, properties):
        latest.connection(False)
        LOG.warning("Lokales MQTT getrennt; automatische Neuverbindung.")

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.connect_async(args.mqtt_host, args.mqtt_port, keepalive=30)
    client.loop_start()
    return client


def make_cloud(device_id, secret, latest, interval):
    from arduino_iot_cloud import ArduinoCloudClient
    cloud = ArduinoCloudClient(device_id=device_id, username=device_id,
                               password=secret, server="iot.arduino.cc", port=8884,
                               sync_mode=True, ssl_params=tls_parameters())
    # on_read wird auch waehrend Neuverbindungsversuchen ausgefuehrt.
    # None verhindert, dass fehlende/veraltete Messwerte als Null gesendet werden.
    for name in TOPICS.values():
        def read_current(client, variable=name):
            values = latest.snapshot()
            return values[variable] if values is not None else None
        cloud.register(name, value=None, on_read=read_current, interval=interval)
    return cloud


def credentials():
    device_id = os.getenv("ARDUINO_DEVICE_ID", "").strip()
    secret = os.getenv("ARDUINO_SECRET_KEY", "").strip()
    if sys.stdin.isatty():
        if not device_id:
            device_id = input("Device-/Client-ID des Arduino-Geraets: ").strip()
        if not secret:
            secret = getpass.getpass("Secret Key (unsichtbar): ").strip()
    if not device_id or not secret:
        raise ValueError("ARDUINO_DEVICE_ID und ARDUINO_SECRET_KEY fehlen.")
    return device_id, secret


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mqtt-host", default="localhost")
    parser.add_argument("--mqtt-port", type=int, default=1883)
    parser.add_argument("--interval", type=float, default=30.0,
                        help="Cloud-Abtastintervall in Sekunden (Standard: 30)")
    parser.add_argument("--max-age", type=float, default=15.0,
                        help="Maximales Alter lokaler MQTT-Werte (Standard: 15 s)")
    parser.add_argument("--dry-run", action="store_true", help="Nur MQTT, keine Cloud")
    args = parser.parse_args()
    if not all(math.isfinite(v) and v > 0 for v in (args.interval, args.max_age)):
        parser.error("Intervall und maximales Alter muessen endlich und positiv sein.")
    if not 1 <= args.mqtt_port <= 65535:
        parser.error("Ungueltiger MQTT-Port")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    latest = LatestValues(args.max_age)
    cloud = None
    if not args.dry_run:
        device_id, secret = credentials()
        cloud = make_cloud(device_id, secret, latest, args.interval)
    mqtt_client = start_mqtt(args, latest)
    try:
        print("Live-Bruecke gestartet. Beenden: Strg+C.", flush=True)
        print("Hinweis: Aktor-Topics enthalten derzeit Befehle UND Rueckmeldungen.", flush=True)
        if cloud:
            print("Verbinde Arduino Cloud; bei Ausfall wird erneut verbunden.", flush=True)
            cloud.start()
            print("Arduino Cloud und Thing verbunden.", flush=True)
        next_report = 0.0
        while True:
            if cloud:
                cloud.update()
            if time.monotonic() >= next_report:
                values = latest.snapshot()
                print("Aktuelle MQTT-Werte: " + str(values) if values else
                      "Warte: MQTT-Werte fehlen oder sind aelter als die erlaubte Frist.",
                      flush=True)
                next_report = time.monotonic() + args.interval
            time.sleep(0.1)
    finally:
        mqtt_client.disconnect()
        mqtt_client.loop_stop()
        # Der offizielle Arduino-Client besitzt in dieser Version kein stop().
        # Beim Prozessende schliesst das Betriebssystem die Cloud-Verbindung.


def terminate(signum, frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, terminate)
    try:
        main()
    except KeyboardInterrupt:
        print("\nCloud-Bruecke beendet. main.py laeuft unabhaengig weiter.")
    except (ValueError, OSError, ImportError) as error:
        print(f"Cloud-Bruecke konnte nicht weiterlaufen: {error}", file=sys.stderr)
        raise SystemExit(1)
