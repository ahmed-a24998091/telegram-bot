"""Validate geographic source metadata before displaying current facts."""
import ast
import copy
import datetime as dt
from pathlib import Path
import re
import unittest


def helpers():
    path = Path(__file__).resolve().parents[1] / 'voice_bot.py'
    names = {'weather_source_valid', 'prayer_source_valid'}
    nodes = [n for n in ast.parse(path.read_text()).body
             if isinstance(n, ast.FunctionDef) and n.name in names]
    scope = {'re': re}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope


class GeoSourceTests(unittest.TestCase):
    def setUp(self):
        self.scope = helpers()
        self.place = {'lat': 30.0444, 'lon': 31.2357, 'tz': 'Africa/Cairo'}
        self.now = dt.datetime(2026, 11, 25, 0, 44, tzinfo=dt.timezone.utc)
        self.weather = {'timezone': 'Africa/Cairo', 'latitude': 30.02866,
            'longitude': 31.219194, 'current_units': {'temperature_2m': '°C',
            'relative_humidity_2m': '%', 'wind_speed_10m': 'km/h'},
            'current': {'time': '2026-11-25T02:30', 'temperature_2m': 16.7,
            'relative_humidity_2m': 84, 'wind_speed_10m': 5.4}}
        self.prayer = {'code': 200, 'data': {'date': {'gregorian': {'date': '25-11-2026'}},
            'meta': {'latitude': 30.0444, 'longitude': 31.2357, 'timezone': 'Africa/Cairo',
                'method': {'id': 5}, 'school': 'STANDARD', 'latitudeAdjustmentMethod': 'ANGLE_BASED'},
            'timings': dict(Fajr='04:57', Sunrise='06:28', Dhuhr='11:42', Asr='14:37', Maghrib='16:55', Isha='18:17')}}

    def weather_valid(self, payload):
        return self.scope['weather_source_valid'](payload, self.place, self.now)

    def prayer_valid(self, payload):
        return self.scope['prayer_source_valid'](payload, self.place, '25-11-2026', 5)

    def test_valid_source_shapes(self):
        self.assertTrue(self.weather_valid(self.weather))
        self.assertTrue(self.prayer_valid(self.prayer))

    def test_stale_future_and_wrong_timezone_weather(self):
        for stamp in ('2020-01-01T00:00', '2026-11-25T03:30', 'invalid', None):
            d = copy.deepcopy(self.weather)
            d['current']['time'] = stamp
            self.assertFalse(self.weather_valid(d), stamp)
        d = copy.deepcopy(self.weather)
        d['timezone'] = 'Asia/Tokyo'
        self.assertFalse(self.weather_valid(d))

    def test_weather_units_location_and_values(self):
        for field, value in [('temperature_2m', None), ('temperature_2m', float('nan')),
                             ('relative_humidity_2m', 101), ('wind_speed_10m', -1), ('wind_speed_10m', True)]:
            d = copy.deepcopy(self.weather)
            d['current'][field] = value
            self.assertFalse(self.weather_valid(d))
        d = copy.deepcopy(self.weather)
        d['current_units']['temperature_2m'] = '°F'
        self.assertFalse(self.weather_valid(d))
        d = copy.deepcopy(self.weather)
        d['latitude'] = 35
        self.assertFalse(self.weather_valid(d))

    def test_prayer_date_zone_method_and_coordinates(self):
        for field, value in [('timezone', 'Asia/Tokyo'), ('latitude', 35),
                             ('school', 'HANAFI'), ('latitudeAdjustmentMethod', 'MIDDLE_OF_THE_NIGHT')]:
            d = copy.deepcopy(self.prayer)
            d['data']['meta'][field] = value
            self.assertFalse(self.prayer_valid(d), field)
        d = copy.deepcopy(self.prayer)
        d['data']['meta']['method']['id'] = 4
        self.assertFalse(self.prayer_valid(d))
        d = copy.deepcopy(self.prayer)
        d['data']['date']['gregorian']['date'] = '24-11-2026'
        self.assertFalse(self.prayer_valid(d))

    def test_prayer_missing_or_invalid_times(self):
        for key, value in [('Sunrise', None), ('Fajr', '99:99'), ('Isha', '18:17 BAD')]:
            d = copy.deepcopy(self.prayer)
            d['data']['timings'][key] = value
            self.assertFalse(self.prayer_valid(d))
        self.assertFalse(self.prayer_valid({}))
        self.assertFalse(self.weather_valid({}))
