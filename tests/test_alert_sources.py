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
        self.prayer_rows, self.price_rows = [], []
        self.cancel, self.delivered = False, True
        self.generated = None
        owner = self
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def execute(self, query, params=()):
                self.query = query
                owner.queries.append(query)
                if query.startswith('INSERT INTO bot_reminders'): owner.inserted.append(params)
                if query.startswith('UPDATE bot_prayer_alerts SET generated_day'): owner.generated = params[0]
                return self
            def fetchall(self):
                return owner.prayer_rows if self.query.startswith('SELECT chat_id') else owner.price_rows
            def fetchone(self):
                if owner.cancel: return None
                return (10, owner.generated) if self.query.startswith('SELECT minutes') else (1,)
        self.scope = {'dt': dt, 'time': time, 're': re, 'TZ': ZoneInfo('Africa/Cairo'),
            'STORE': types.SimpleNamespace(connect=Connection), 'PRAYER_RETRY': 0,
            'PRICE_NEXT_CHECK': 0, 'bot': types.SimpleNamespace(tg=self.send)}
        names = {'prayer_alert_source_valid', 'queue_prayer_alerts', 'check_price_alerts'}
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
        self.prayer_rows = [(123, 10)]
        for key, value in [('timezone', 'Asia/Tokyo'), ('longitude', 130), ('method', {'id': 4})]:
            self.payload = self.prayer()
            self.payload['data']['meta'][key] = value
            self.scope['PRAYER_RETRY'] = 0
            self.scope['queue_prayer_alerts']()
            self.assertEqual(self.inserted, [], key)
            self.assertIsNone(self.generated)

    def test_prayer_optin_recheck_and_daily_duplicate_guard(self):
        self.prayer_rows = [(123, 10)]
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
