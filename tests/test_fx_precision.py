"""Reference FX precision tests with synthetic cached rates only."""
import ast
import datetime as dt
from pathlib import Path
import re
import time
import unittest
from zoneinfo import ZoneInfo


def convert_function():
    path = Path(__file__).resolve().parents[1] / 'finish_bot.py'
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'currency_convert')
    scope = {'dt': dt, 'TZ': ZoneInfo('Africa/Cairo'), 're': re, 'time': time,
             'FX_CACHE': {'USD': (time.monotonic(), {'result': 'success', 'base_code': 'USD',
                 'time_last_update_unix': int(time.time()) - 60, 'rates': {'EGP': '54.225902'}})}}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope


class FXPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.scope = convert_function()
        self.convert = self.scope['currency_convert']

    def test_small_input_not_relabelled_zero(self):
        out = self.convert('0.001', 'USD', 'EGP')
        self.assertTrue(out.startswith('0.001 USD ≈ 0.054226 EGP'), out)
        self.assertIn('حتى6منازل', out)

    def test_supported_input_preserved_and_trailing_zero_equivalence(self):
        for value in ('1.234567', '999999999999.999', '0.000001'):
            out = self.convert(value, 'USD', 'EGP')
            self.assertTrue(out.startswith(value + ' USD'), out)
        self.assertTrue(self.convert('1.234567000000', 'USD', 'EGP').startswith('1.234567 USD'))

    def test_unsupported_precision_and_input_rejected(self):
        for value in ('0.000000001', '54.1234567890123456789', '1e2', 'NaN', 'Infinity', '1,000', '0', '-1', '1' * 121):
            out = self.convert(value, 'USD', 'EGP')
            self.assertNotIn('سعر مرجعي:', out, value)

    def test_tiny_result_label_not_false_zero(self):
        self.scope['FX_CACHE']['USD'][1]['rates']['EGP'] = '0.000001'
        out = self.convert('0.000001', 'USD', 'EGP')
        self.assertIn('أقل من 0.000001 EGP', out)
        self.assertNotIn('≈ 0 EGP', out)

    def test_stale_future_and_invalid_rates(self):
        data = self.scope['FX_CACHE']['USD'][1]
        for stamp in (int(time.time()) - 49 * 3600, int(time.time()) + 3600, True):
            data['time_last_update_unix'] = stamp
            with self.assertRaises(ValueError):
                self.convert('1', 'USD', 'EGP')
        data['time_last_update_unix'] = int(time.time()) - 60
        for rate in (True, '1000000000001', '0.0000000000001'):
            data['rates']['EGP'] = rate
            with self.assertRaises(ValueError):
                self.convert('1', 'USD', 'EGP')
