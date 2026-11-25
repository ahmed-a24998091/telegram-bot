"""Offline regression checks. No imports of the running bot or external calls.
Run from repository root: python -m unittest discover -s tests -v
Functions are extracted from the real source rather than copied into fixtures.
"""
import ast
from decimal import Decimal
from pathlib import Path
import re
import threading
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'voice_bot.py'
FUNCTIONS = {
    'feasibility_parse', 'reference_doi_candidate', 'reference_doi_candidates',
    'transient_stores', 'transient_enter', 'transient_leave', 'transient_sweep',
    'transient_handle', 'transient_send',
}


def load_core():
    tree = ast.parse(SOURCE.read_text(encoding='utf-8'))
    functions = [node for node in tree.body
                 if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS]
    if {node.name for node in functions} != FUNCTIONS:
        raise AssertionError('A tested core function is missing or was renamed')
    scope = {'re': re, 'threading': threading, 'time': time}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), scope)
    scope['FEASIBILITY_FIELDS'] = [
        'اسم المشروع', 'العملة', 'سعر الوحدة', 'تكلفة الوحدة المتغيرة',
        'وحدات المبيعات الشهرية', 'التكلفة الثابتة الشهرية', 'الاستثمار الأولي',
    ]
    scope['TRANSIENT_LOCK'] = threading.RLock()
    scope['TRANSIENT_ACTIVE'] = {}
    return scope


class FinancialInputs(unittest.TestCase):
    def setUp(self):
        self.core = load_core()
        self.values = ['fixture', 'EGP', '100', '40', '1000', '20000', '120000']

    def parse(self, price, index=2):
        values = list(self.values)
        values[index] = price
        return self.core['feasibility_parse']('\n'.join(
            key + ':' + value for key, value in zip(self.core['FEASIBILITY_FIELDS'], values)))

    def test_valid_precision_and_arabic_digits(self):
        for raw, value in [('٠٫١٢٣٤٥٦', '0.123456'), ('999999999999.999', '999999999999.999'),
                           ('0.000001', '0.000001'), ('1.234567000000', '1.234567')]:
            with self.subTest(raw=raw):
                self.assertEqual(self.parse(raw)['سعر الوحدة'], Decimal(value))

    def test_unsupported_values_fail_instead_of_rounding(self):
        for raw in ['1e-999', '1.234567890123456789', '0.0000001', 'NaN', 'Infinity',
                    '1,000', '-1', '0', '1' * 121]:
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.parse(raw)

    def test_zero_cost_allowed_and_duplicate_fields_rejected(self):
        self.assertEqual(self.parse('0', 3)['تكلفة الوحدة المتغيرة'], 0)
        text = '\n'.join(key + ':' + value for key, value in
                         zip(self.core['FEASIBILITY_FIELDS'], self.values))
        with self.assertRaises(ValueError):
            self.core['feasibility_parse'](text + '\nسعر الوحدة:1')


class DOICandidates(unittest.TestCase):
    def setUp(self):
        self.core = load_core()

    def test_balanced_suffix_preserved(self):
        for doi in ['10.5555/example(test)', '10.5555/example[abc]',
                    '10.1002/(SICI)1097-0282(199907)50:1<99::AID-BIP9>3.0.CO;2-A']:
            self.assertEqual(self.core['reference_doi_candidate'](doi), doi)

    def test_wrapper_punctuation_and_encoded_url(self):
        parse = self.core['reference_doi_candidate']
        self.assertEqual(parse('10.5555/example(test)).'), '10.5555/example(test)')
        self.assertEqual(parse('https://doi.org/10.5555/example%28test%29'),
                         '10.5555/example(test)')
        self.assertIsNone(parse('https://example.invalid/10.5555/test'))
        self.assertIsNone(parse('10.5555/test extra text'))

    def test_case_insensitive_deduplication(self):
        self.assertEqual(self.core['reference_doi_candidates'](
            '(10.5555/Example(test)). 10.5555/example(test)'), ['10.5555/Example(test)'])


class TransientExpiry(unittest.TestCase):
    def setUp(self):
        self.core = load_core()
        self.state = {}
        # Supply private fixtures, not real bot data or integration modules.
        self.core['transient_stores'] = lambda: [(self.state, 600, lambda value: value['time'])]

    def test_exact_expiry_boundary_and_other_chat(self):
        self.state.update({1: {'time': 400}, 2: {'time': 401}})
        self.assertEqual(self.core['transient_sweep'](1000), 1)
        self.assertEqual(set(self.state), {2})

    def test_nested_activity_preserves_state_until_finished(self):
        self.state[1] = {'time': 0}
        self.core['transient_enter'](1)
        self.core['transient_enter'](1)
        self.assertEqual(self.core['transient_sweep'](1000), 0)
        self.core['transient_leave'](1)
        self.assertEqual(self.core['transient_sweep'](1000), 0)
        self.core['transient_leave'](1)
        self.assertEqual(self.core['transient_sweep'](1000), 1)
        self.assertEqual(self.core['TRANSIENT_ACTIVE'], {})

    def test_exceptions_release_handler_and_send_activity(self):
        def fail(*args):
            raise RuntimeError('synthetic failure')
        self.core['TRANSIENT_INNER'] = fail
        self.core['TRANSIENT_SEND'] = fail
        with self.assertRaises(RuntimeError):
            self.core['transient_handle']({'chat': {'id': 1}})
        with self.assertRaises(RuntimeError):
            self.core['transient_send'](1, 'synthetic text')
        self.assertEqual(self.core['TRANSIENT_ACTIVE'], {})

    def test_concurrent_cleanup_preserves_active_chats(self):
        failures = []
        def writer(chat):
            try:
                for _ in range(200):
                    self.core['transient_enter'](chat)
                    try:
                        self.state[chat] = {'time': 0}
                        self.core['transient_sweep'](1000)
                        self.assertIn(chat, self.state)
                        self.state[chat] = {'time': 1000}
                    finally:
                        self.core['transient_leave'](chat)
            except Exception as error:
                failures.append(type(error).__name__)
        workers = [threading.Thread(target=writer, args=(chat,)) for chat in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(self.core['TRANSIENT_ACTIVE'], {})


if __name__ == '__main__':
    unittest.main()
