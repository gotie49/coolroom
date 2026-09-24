import importlib.util
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('coolroom', Path(__file__).with_name('main.py'))
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)


class Message(list):
    @staticmethod
    def read(addr, n):
        msg = Message([0] * n)
        msg.addr, msg.reading = addr, True
        return msg

    @staticmethod
    def write(addr, data):
        msg = Message(data)
        msg.addr, msg.reading = addr, False
        return msg


class Bus:
    def __init__(self):
        self.data = {0x10: [234, 0, 1, 0], 0x11: [204, 255, 0], 0x12: [0, 0, 1]}
        self.writes = []
        self.pending = None
        self.closed = False

    def i2c_rdwr(self, msg):
        if msg.reading:
            msg[:] = self.data[msg.addr]
            if self.pending is not None:
                self.data[0x12] = self.pending + [0]
                self.pending = None
        else:
            self.writes.append((msg.addr, list(msg)))
            self.pending = list(msg)

    def close(self):
        self.closed = True


class Tests(unittest.TestCase):
    def setUp(self):
        self.bus = Bus()
        self.mock = patch.dict(sys.modules, smbus2=types.SimpleNamespace(i2c_msg=Message, SMBus=lambda n: self.bus))
        self.mock.start()

    def tearDown(self):
        self.mock.stop()

    def test_signed_temperature_and_door(self):
        self.assertEqual(app.sensor_lesen(self.bus, 0x10), (23.4, 1))
        self.assertEqual(app.sensor_lesen(self.bus, 0x11), (-5.2, None))

    def test_bad_sensor_status_and_door(self):
        for status in (1, 2, 255):
            self.bus.data[0x11][-1] = status
            with self.assertRaises(ValueError):
                app.sensor_lesen(self.bus, 0x11)
        self.bus.data[0x10][2] = 2
        with self.assertRaises(ValueError):
            app.sensor_lesen(self.bus, 0x10)

    def test_command_raw_bytes_and_delayed_confirmation(self):
        app.stellen_und_pruefen(self.bus, 128, 50)
        self.assertEqual(self.bus.writes, [(0x12, [128, 50])])
        for fan, valve in ((256, 0), (0, 101), (-1, 0)):
            with self.assertRaises(ValueError):
                app.stellen(self.bus, fan, valve)

    def test_bad_sensor_stops_and_closes(self):
        self.bus.data[0x11][-1] = 1
        with patch.object(app, 'MQTT_AKTIV', False), patch.object(app, 'DB_AKTIV', False), patch.object(app.time, 'sleep'), patch.object(app.signal, 'signal'):
            self.assertEqual(app.main(), 1)
        self.assertTrue(self.bus.closed)
        self.assertTrue(all(data == [0, 0] for addr, data in self.bus.writes))

    def test_hysteresis_door_and_room_temperature(self):
        r = app.Regelung()
        self.assertEqual(r.berechnen(26, 0), (0, 0))
        self.assertEqual(r.berechnen(27, 0), (0, 0))
        self.assertGreater(r.berechnen(28, 0)[0], 0)
        self.assertGreater(r.berechnen(27, 0)[0], 0)
        self.assertEqual(r.berechnen(26, 0), (0, 0))
        self.assertEqual(r.berechnen(32, 0), (255, 100))
        self.assertEqual(r.berechnen(32, 1), (0, 0))

    def test_inaccurate_ntc_does_not_trigger_cooling(self):
        self.bus.data[0x10] = [211, 1, 0, 0]  # 46.7 C, Tuer zu
        self.bus.data[0x11] = [4, 1, 0]       # 26.0 C
        values = app.zyklus(self.bus, app.Regelung())
        self.assertEqual(values, (46.7, 0, 26.0, 0, 0))
        self.assertEqual(self.bus.writes[-1], (0x12, [0, 0]))

    def test_feedback_timeout(self):
        self.bus.data[0x12] = [0, 0, 2]
        with patch.object(app, 'stellen'):
            with self.assertRaises(OSError):
                app.stellen_und_pruefen(self.bus, 128, 50)

    def test_cycle_and_mqtt_values(self):
        self.bus.data[0x10] = [250, 0, 0, 0]
        self.bus.data[0x11] = [64, 1, 0]
        values = app.zyklus(self.bus, app.Regelung())
        self.assertEqual(values, (25, 0, 32, 255, 100))
        from unittest.mock import Mock
        client = Mock()
        client.publish.return_value.rc = 0
        app.publish(client, *values)
        client.publish.assert_any_call('door/0x10/state', '0')
        client.publish.assert_any_call('aktor/0x12/propeller', '255')

    def test_database_values(self):
        with patch.object(app, 'DB_DATEI', ':memory:'):
            conn = app.datenbank_oeffnen()
        app.speichern(conn, 23.4, 1, -5.2)
        self.assertEqual(conn.execute('SELECT * FROM MEASUREMENTS').fetchall(), [(16, 0, 23.4), (17, 0, -5.2)])
        self.assertEqual(conn.execute('SELECT ARD_ID, IS_OPEN FROM DOOR_STATES').fetchall(), [(16, 1)])
        conn.close()


if __name__ == '__main__':
    unittest.main()
