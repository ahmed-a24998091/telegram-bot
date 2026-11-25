"""Price-source metadata and quote validation without network or bot startup."""
import ast
import copy
import datetime as dt
from pathlib import Path
from zoneinfo import ZoneInfo
import unittest


def validator():
    path = Path(__file__).resolve().parents[1] / 'daily_tools.py'
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'verified_price_asset')
    scope = {'dt': dt, 'TZ': ZoneInfo('Africa/Cairo')}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[node.name]


class PriceSourceTests(unittest.TestCase):
    def setUp(self):
        self.check = validator()
        self.now = dt.datetime(2026, 11, 25, 0, 0, tzinfo=dt.timezone.utc)
        self.asset = {'id': 'USD-EGP', 'unit': 'EGP/USD',
            'observedAt': '2026-11-24T19:00:00Z',
            'freshness': {'stale': False, 'state': 'fresh'},
            'confidence': {'level': 'conflicting'},
            'sellers': [{'seller': 'NBE', 'buy': 54.17, 'sell': 54.27}]}

    def test_valid_quote_and_conflict_flag(self):
        stamp, rows, conflict = self.check(self.asset, 'USD-EGP', self.now)
        self.assertTrue(conflict)
        self.assertEqual(str(rows[0][1]), '54.17')
        self.assertEqual(stamp.tzinfo, ZoneInfo('Africa/Cairo'))

    def test_wrong_unit_identity_freshness_and_stamp(self):
        for field, value in [('id', 'OTHER'), ('unit', 'USD/EGP'),
                             ('observedAt', '2020-01-01T00:00:00Z'),
                             ('observedAt', '2026-11-26T00:00:00Z'),
                             ('observedAt', '2026-11-24T19:00:00'),
                             ('freshness', {'stale': True, 'state': 'fresh'}),
                             ('freshness', {'stale': False, 'state': 'stale'})]:
            d = copy.deepcopy(self.asset)
            d[field] = value
            self.assertIsNone(self.check(d, 'USD-EGP', self.now), field)

    def test_invalid_quotes_not_rendered(self):
        for value in (None, 'NaN', 'Infinity', -1, 0, True, 10**9, '54.1234567', '54.12345678901234'):
            d = copy.deepcopy(self.asset)
            d['sellers'][0]['sell'] = value
            self.assertIsNone(self.check(d, 'USD-EGP', self.now), str(value))
        d = copy.deepcopy(self.asset)
        d['sellers'][0]['buy'] = 55
        self.assertIsNone(self.check(d, 'USD-EGP', self.now))

    def test_valid_seller_survives_bad_seller(self):
        d = copy.deepcopy(self.asset)
        d['sellers'].insert(0, {'seller': 'Bad', 'buy': 1, 'sell': 'NaN'})
        result = self.check(d, 'USD-EGP', self.now)
        self.assertEqual(len(result[1]), 1)
        self.assertEqual(result[1][0][0], 'NBE')

    def test_missing_metadata_refused(self):
        for key in ('observedAt', 'freshness', 'unit', 'sellers'):
            d = copy.deepcopy(self.asset)
            del d[key]
            self.assertIsNone(self.check(d, 'USD-EGP', self.now), key)
