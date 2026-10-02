"""Simulierte IceTruck-Werte fuer Arduino Cloud. Keine Hardwareansteuerung."""
import argparse
import getpass
import json
import logging
import math
import ssl
import time

NAMES = ("temperatur_ntc", "temperatur_dht", "tuer_offen", "luefter_pwm", "klappe_prozent")


def sample(step):
    temperature = round(26 + 3 * math.sin(step * math.pi / 6), 1)
    door = step % 12 in (5, 6)
    # Nur anschauliche Testwerte, nicht die Regelung aus main.py.
    fan = 160 if temperature >= 28 and not door else 0
    valve = 50 if fan else 0
    return dict(zip(NAMES, (round(temperature + 0.3, 1), temperature, door, fan, valve)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true", help="Testwerte lokal anzeigen, ohne Cloud")
    args = parser.parse_args()
    if args.preview:
        for step in range(12):
            print(json.dumps(sample(step), ensure_ascii=False))
        return

    import certifi
    from arduino_iot_cloud import ArduinoCloudClient, CADATA

    print("SIMULATION: Schreibt Testwerte in das zugeordnete Thing.")
    print("Nur diesen Client mit der Device-ID betreiben. Beenden: Strg+C.")
    device_id = input("Device-ID (nicht Thing-ID): ").strip()
    secret = getpass.getpass("Secret Key (Eingabe bleibt unsichtbar): ").strip()
    if not device_id or not secret:
        raise SystemExit("Device-ID und Secret Key duerfen nicht leer sein.")

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    # Der Arduino-Client laedt unter Windows nicht selbst den Windows-Truststore.
    # Nur bereits vom Betriebssystem vertraute CAs uebernehmen (z.B. Schulnetz).
    system_context = ssl.create_default_context()
    trusted_pem = "".join(
        ssl.DER_cert_to_PEM_cert(cert)
        for cert in system_context.get_ca_certs(binary_form=True)
    ) + ssl.DER_cert_to_PEM_cert(CADATA)
    client = ArduinoCloudClient(
        device_id=device_id, username=device_id, password=secret,
        server="iot.arduino.cc", port=8884, sync_mode=True,
        ssl_params={
            "verify_mode": ssl.CERT_REQUIRED,
            "server_hostname": "iot.arduino.cc",
            "cadata": trusted_pem,
            "cafile": certifi.where(),
        },
    )
    for name, value in sample(0).items():
        client.register(name, value=value)

    print("Verbinde mit Arduino Cloud ...")
    client.start()
    print("Verbindung und Thing-Zuordnung hergestellt. Dashboard jetzt oeffnen.")
    start = time.monotonic()
    next_sample = 0.0
    step = 0
    # Begrenzt auf zehn Minuten, damit der Simulator nicht dauerhaft Daten sendet.
    while time.monotonic() - start < 600:
        client.update()
        now = time.monotonic()
        if now >= next_sample:
            values = sample(step)
            for name, value in values.items():
                client[name] = value
            print("SIMULATION bereitgestellt: " + json.dumps(values), flush=True)
            print("Empfang bitte im Dashboard kontrollieren.", flush=True)
            step += 1
            next_sample = now + 10
        time.sleep(0.1)
    print("Simulation nach zehn Minuten beendet.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulation beendet.")


