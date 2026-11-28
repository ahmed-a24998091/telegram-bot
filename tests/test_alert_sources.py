"""Background source checks, synthetic storage and transport only."""
import ast
import copy
import datetime as dt
from pathlib import Path
import re
import sys
import time
import types
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


class AlertSourceTests(unittest.TestCase):
    def setUp(self):
        self.queries, self.inserted, self.sent, self.network = [], [], [], []
        self.prayer_rows, self.price_rows, self.weather_rows = [], [], []
        self.cancel, self.delivered = False, True
        self.generated = None
        self.generated_map = {}
        self.weather_generated = {}
        self.recheck_minutes = 10
        owner = self
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, query, params=()):
                self.query = query
                self.params = params
                owner.queries.append(query)
                if query.startswith('INSERT INTO bot_reminders'): owner.inserted.append(params)
                if query.startswith('UPDATE bot_prayer_alerts SET generated_day'):
                    owner.generated = params[0]
                    owner.generated_map[params[1]] = params[0]
                if query.startswith('UPDATE bot_weather_alerts SET generated_day'):
                    owner.weather_generated[params[1]] = params[0]
                return self
            def fetchall(self):
                if 'bot_weather_alerts' in self.query: return owner.weather_rows
                if 'bot_prayer_alerts' in self.query: return owner.prayer_rows
                return owner.price_rows
            def fetchone(self):
                if owner.cancel: return None
                if self.query.startswith('SELECT minutes'):
                    return (owner.recheck_minutes, owner.generated_map.get(self.params[0]))
                if self.query.startswith('SELECT generated_day'):
                    return (owner.weather_generated.get(self.params[0]),)
                return (1,)
        self.scope = {'dt': dt, 'time': time, 're': re, 'TZ': ZoneInfo('Africa/Cairo'), 'ZoneInfo': ZoneInfo,
            'STORE': types.SimpleNamespace(connect=Connection), 'PRAYER_RETRY': 0,
            'WEATHER_RETRY': 0,
            'PRICE_NEXT_CHECK': 0, 'bot': types.SimpleNamespace(tg=self.send)}
        names = {'prayer_alert_source_valid', 'prayer_alert_place_valid', 'queue_prayer_alerts', 'check_price_alerts', 'queue_weather_alerts', 'weather_alert_valid'}
        nodes = [n for n in ast.parse((ROOT / 'extra_bot.py').read_text()).body
                 if isinstance(n, ast.FunctionDef) and n.name in names]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'extra_bot.py', 'exec'), self.scope)
        price_node = next(n for n in ast.parse((ROOT / 'daily_tools.py').read_text()).body
                         if isinstance(n, ast.FunctionDef) and n.name == 'verified_price_asset')
        price_scope = {'dt': dt, 'TZ': ZoneInfo('Africa/Cairo')}
        exec(compile(ast.Module(body=[price_node], type_ignores=[]), 'daily_tools.py', 'exec'), price_scope)
        self.requests = types.ModuleType('requests')
        self.requests.get = self.get
        self.daily = types.ModuleType('daily_tools')
        self.daily.verified_price_asset = price_scope['verified_price_asset']
        self.context = patch.dict(sys.modules, {'requests': self.requests, 'daily_tools': self.daily})
        self.context.start()
        self.addCleanup(self.context.stop)
        self.payload = {}

    def send(self, method, **kwargs):
        self.sent.append(kwargs)
        return {'ok': self.delivered}

    def get(self, *args, **kwargs):
        self.network.append((args, kwargs))
        return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: self.payload)

    def prayer(self):
        now = dt.datetime.now(ZoneInfo('Africa/Cairo'))
        return {'data': {'date': {'gregorian': {'date': now.strftime('%d-%m-%Y')}},
            'meta': {'latitude': 30.0444, 'longitude': 31.2357, 'timezone': 'Africa/Cairo',
                'method': {'id': 5}, 'school': 'STANDARD', 'latitudeAdjustmentMethod': 'ANGLE_BASED'},
            'timings': dict(Fajr='23:50', Dhuhr='23:51', Asr='23:52', Maghrib='23:53', Isha='23:54')}}

    def prices(self):
        return {'assets': [{'id': 'USD-EGP', 'unit': 'EGP/USD',
            'observedAt': (dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=2)).isoformat(),
            'freshness': {'stale': False, 'state': 'fresh'}, 'confidence': {'level': 'conflicting'},
            'sellers': [{'seller': 'National Bank of Egypt (NBE)', 'buy': 54, 'sell': 55}]}]}

    def test_no_subscribers_no_network(self):
        self.scope['queue_prayer_alerts']()
        self.scope['check_price_alerts']()
        self.assertEqual(self.network, [])
        self.assertEqual(self.sent, [])

    def test_bad_prayer_metadata_creates_no_rows(self):
        self.prayer_rows = [(123, 10, None, None, None, None, None)]
        for key, value in [('timezone', 'Asia/Tokyo'), ('longitude', 130), ('method', {'id': 4})]:
            self.payload = self.prayer()
            self.payload['data']['meta'][key] = value
            self.scope['PRAYER_RETRY'] = 0
            self.scope['queue_prayer_alerts']()
            self.assertEqual(self.inserted, [], key)
            self.assertIsNone(self.generated)

    def test_prayer_optin_recheck_and_daily_duplicate_guard(self):
        self.prayer_rows = [(123, 10, None, None, None, None, None)]
        self.payload = self.prayer()
        self.cancel = True
        self.scope['queue_prayer_alerts']()
        self.assertEqual(self.inserted, [])
        self.cancel = False
        self.scope['queue_prayer_alerts']()
        self.assertIsNotNone(self.generated)
        count = len(self.inserted)
        self.scope['queue_prayer_alerts']()
        self.assertEqual(len(self.inserted), count)
        self.assertTrue(all(row[0] == 123 for row in self.inserted))

    def dubai_prayer(self):
        now = dt.datetime.now(ZoneInfo('Asia/Dubai'))
        return {'data': {'date': {'gregorian': {'date': now.strftime('%d-%m-%Y')}},
            'meta': {'latitude': 25.2048, 'longitude': 55.2708, 'timezone': 'Asia/Dubai',
                'method': {'id': 3}, 'school': 'STANDARD', 'latitudeAdjustmentMethod': 'ANGLE_BASED'},
            'timings': dict(Fajr='23:50', Dhuhr='23:51', Asr='23:52', Maghrib='23:53', Isha='23:54')}}

    def test_global_subscriber_uses_own_city_tz_method(self):
        self.prayer_rows = [(124, 10, 'دبي، AE', 25.2048, 55.2708, 'Asia/Dubai', 3)]
        self.payload = self.dubai_prayer()
        self.scope['queue_prayer_alerts']()
        self.assertEqual(len(self.network), 1)
        params = self.network[0][1]['params']
        self.assertEqual(params['timezonestring'], 'Asia/Dubai')
        self.assertEqual(params['method'], 3)
        self.assertAlmostEqual(params['latitude'], 25.2048)
        self.assertTrue(self.inserted)
        self.assertTrue(all('دبي' in row[1] for row in self.inserted))
        for row in self.inserted:
            self.assertEqual(row[2].utcoffset(), dt.datetime.now(ZoneInfo('Asia/Dubai')).utcoffset())

    def test_grouped_fetch_per_distinct_city(self):
        self.prayer_rows = [(123, 10, None, None, None, None, None),
                            (124, 10, 'دبي، AE', 25.2048, 55.2708, 'Asia/Dubai', 3),
                            (125, 10, 'دبي، AE', 25.2048, 55.2708, 'Asia/Dubai', 3)]
        cairo = self.prayer(); dubai = self.dubai_prayer()
        owner = self
        def routed_get(url, params=None, **kw):
            owner.network.append(((url,), {'params': params}))
            payload = dubai if params['timezonestring'] == 'Asia/Dubai' else cairo
            return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
        self.requests.get = routed_get
        self.scope['queue_prayer_alerts']()
        self.assertEqual(len(self.network), 2)
        chats = {row[0] for row in self.inserted}
        self.assertEqual(chats, {123, 124, 125})

    def weather_payload(self, tzs, target_day, lat, lon):
        return {'timezone': tzs, 'latitude': lat, 'longitude': lon,
            'daily_units': {'temperature_2m_max': '°C', 'temperature_2m_min': '°C', 'precipitation_probability_max': '%'},
            'daily': {'time': [target_day], 'temperature_2m_max': [28.5], 'temperature_2m_min': [17.0], 'precipitation_probability_max': [10]}}

    def expected_target(self, tzs, clock):
        now = dt.datetime.now(ZoneInfo(tzs))
        due = dt.datetime.combine(now.date(), dt.time.fromisoformat(clock), ZoneInfo(tzs))
        return (now.date() if due > now else now.date() + dt.timedelta(days=1)).strftime('%Y-%m-%d')

    def test_weather_alert_queues_daily_briefing(self):
        self.weather_rows = [(123, '23:59', None, None, None, None, None)]
        target = self.expected_target('Africa/Cairo', '23:59')
        self.payload = self.weather_payload('Africa/Cairo', target, 30.0, 31.3)
        self.scope['queue_weather_alerts']()
        self.assertEqual(len(self.inserted), 1)
        chat, body, due = self.inserted[0][0], self.inserted[0][1], self.inserted[0][2]
        self.assertEqual(chat, 123)
        self.assertIn('نشرة طقس القاهرة', body)
        self.assertIn(target, body)
        self.assertEqual(due.utcoffset(), dt.datetime.now(ZoneInfo('Africa/Cairo')).utcoffset())
        self.assertEqual(self.weather_generated.get(123), target)
        self.scope['queue_weather_alerts']()
        self.assertEqual(len(self.inserted), 1)

    def test_weather_alert_global_city(self):
        self.weather_rows = [(124, '23:59', 'دبي، AE', 25.2048, 55.2708, 'Asia/Dubai', None)]
        target = self.expected_target('Asia/Dubai', '23:59')
        self.payload = self.weather_payload('Asia/Dubai', target, 25.2, 55.3)
        self.scope['queue_weather_alerts']()
        params = self.network[0][1]['params']
        self.assertEqual(params['timezone'], 'Asia/Dubai')
        self.assertAlmostEqual(params['latitude'], 25.2048)
        self.assertIn('دبي', self.inserted[0][1])

    def test_weather_clock_passed_schedules_tomorrow(self):
        self.weather_rows = [(123, '00:00', None, None, None, None, None)]
        target = self.expected_target('Africa/Cairo', '00:00')
        self.assertEqual(target, (dt.datetime.now(ZoneInfo('Africa/Cairo')).date() + dt.timedelta(days=1)).strftime('%Y-%m-%d'))
        self.payload = self.weather_payload('Africa/Cairo', target, 30.0, 31.3)
        self.scope['queue_weather_alerts']()
        self.assertEqual(self.inserted[0][2].strftime('%Y-%m-%d'), target)

    def test_bad_weather_metadata_creates_no_rows(self):
        self.weather_rows = [(123, '23:59', None, None, None, None, None)]
        target = self.expected_target('Africa/Cairo', '23:59')
        for mutate in ('timezone', 'units', 'date', 'coords'):
            self.inserted.clear(); self.weather_generated.clear()
            self.payload = self.weather_payload('Africa/Cairo', target, 30.0, 31.3)
            if mutate == 'timezone': self.payload['timezone'] = 'Asia/Tokyo'
            elif mutate == 'units': self.payload['daily_units']['temperature_2m_max'] = '°F'
            elif mutate == 'date': self.payload['daily']['time'] = ['2001-01-01']
            else: self.payload['latitude'] = 10.0
            self.scope['WEATHER_RETRY'] = 0
            self.scope['queue_weather_alerts']()
            self.assertEqual(self.inserted, [], mutate)
            self.assertEqual(self.weather_generated, {}, mutate)

    def test_bad_global_metadata_creates_no_rows(self):
        self.prayer_rows = [(124, 10, 'دبي، AE', 25.2048, 55.2708, 'Asia/Dubai', 3)]
        self.payload = self.dubai_prayer()
        self.payload['data']['meta']['timezone'] = 'Africa/Cairo'
        self.scope['queue_prayer_alerts']()
        self.assertEqual(self.inserted, [])
        self.assertIsNone(self.generated)

    def test_bad_price_metadata_cannot_send(self):
        self.price_rows = [(1, 123, 'usd', 'above', 55)]
        for mode in ('unit', 'stale', 'duplicate', 'seller_duplicate', 'nan'):
            self.payload = self.prices()
            asset = self.payload['assets'][0]
            if mode == 'unit': asset['unit'] = 'BAD'
            elif mode == 'stale': asset['freshness']['stale'] = True
            elif mode == 'duplicate': self.payload['assets'] *= 2
            elif mode == 'seller_duplicate': asset['sellers'] *= 2
            else: asset['sellers'][0]['sell'] = 'NaN'
            self.scope['PRICE_NEXT_CHECK'] = 0
            self.scope['check_price_alerts']()
            self.assertEqual(self.sent, [], mode)

    def test_price_conflict_warning_cancel_and_failed_delivery(self):
        self.price_rows = [(1, 123, 'usd', 'above', 55)]
        self.payload = self.prices()
        self.cancel = True
        self.scope['check_price_alerts']()
        self.assertEqual(self.sent, [])
        self.cancel = False
        for delivered in (False, True):
            self.delivered = delivered
            self.queries.clear()
            self.scope['PRICE_NEXT_CHECK'] = 0
            self.scope['check_price_alerts']()
            self.assertIn('تعارض', self.sent[-1]['data']['text'])
            self.assertEqual(any(q.startswith('DELETE FROM bot_price_alerts') for q in self.queries), delivered)
        count = len(self.sent)
        self.scope['check_price_alerts']()
        self.assertEqual(len(self.sent), count)


class GeoPlaceTests(unittest.TestCase):
    def build(self, payload):
        calls = []
        requests = types.ModuleType('requests')
        def get(url, params=None, headers=None, timeout=None):
            calls.append((url, params))
            return types.SimpleNamespace(raise_for_status=lambda: None, json=lambda: payload)
        requests.get = get
        node = next(n for n in ast.parse((ROOT / 'live_sources.py').read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == 'geo_place')
        scope = {'requests': requests}
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'live_sources.py', 'exec'), scope)
        return scope['geo_place'], calls

    def test_resolved_place(self):
        geo_place, calls = self.build({'lat': 25.2, 'lon': 55.27, 'tz': 'Asia/Dubai', 'name': 'دبي', 'cc': 'AE'})
        place, note = geo_place('Dubai, UAE')
        self.assertEqual(place['tz'], 'Asia/Dubai')
        self.assertEqual(calls[0][1]['place'], 'Dubai, UAE')
        self.assertEqual(calls[0][1]['geo'], '1')

    def test_alias_maps_to_english(self):
        geo_place, calls = self.build({'lat': 30.0, 'lon': 31.2, 'tz': 'Africa/Cairo', 'name': 'القاهرة', 'cc': 'EG'})
        geo_place('القاهرة')
        self.assertEqual(calls[0][1]['place'], 'Cairo, Egypt')

    def test_error_and_choices_refused(self):
        geo_place, _ = self.build({'error': 'مقدرتش أحدد المكان.'})
        place, note = geo_place('Nowhere')
        self.assertIsNone(place)
        self.assertEqual(note, 'مقدرتش أحدد المكان.')
        geo_place, _ = self.build({'choices': [{'name': 'أبوقير', 'cc': 'EG', 'kind': 'مدينة'}]})
        place, note = geo_place('Abu Qir')
        self.assertIsNone(place)
        self.assertIn('أكتر من مكان', note)

    def test_incomplete_payload_not_guessed(self):
        geo_place, _ = self.build({'lat': 30.0})
        place, note = geo_place('Cairo')
        self.assertIsNone(place)
        self.assertIn('مش هخمن المكان', note)


if __name__ == '__main__':
    unittest.main()
