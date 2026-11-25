"""Offline active-chat lock lifecycle tests, no bot startup or network."""
import ast
from pathlib import Path
import threading
import time
import unittest


def registry_class():
    source = Path(__file__).resolve().parents[1] / 'bot.py'
    node = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.ClassDef) and node.name == 'ChatLockRegistry')
    scope = {'threading': threading}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
    return scope['ChatLockRegistry']


class ChatLockTests(unittest.TestCase):
    def test_idle_chat_entries_removed(self):
        registry = registry_class()()
        for chat in range(500):
            entry = registry.enter(chat)
            registry.leave(chat, entry)
        self.assertEqual(registry.entries, {})

    def test_waiter_keeps_same_lock_until_finished(self):
        registry = registry_class()()
        first = registry.enter(1)
        entered, release = threading.Event(), threading.Event()
        def waiter():
            entry = registry.enter(1)
            entered.set()
            try:
                release.wait(3)
            finally:
                registry.leave(1, entry)
        thread = threading.Thread(target=waiter, daemon=True)
        thread.start()
        end = time.monotonic() + 2
        while time.monotonic() < end:
            with registry.guard:
                count = first[1]
            if count == 2:
                break
            time.sleep(0.001)
        try:
            self.assertEqual(count, 2)
        finally:
            registry.leave(1, first)
        try:
            self.assertTrue(entered.wait(2))
            self.assertIs(registry.entries.get(1), first)
        finally:
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertEqual(registry.entries, {})

    def test_parallel_calls_do_not_overlap_within_chat(self):
        registry = registry_class()()
        guard = threading.Lock()
        active, errors = set(), []
        def worker():
            for _ in range(50):
                entry = registry.enter(1)
                try:
                    with guard:
                        if 1 in active:
                            errors.append('overlap')
                        active.add(1)
                    time.sleep(0.0001)
                    with guard:
                        active.remove(1)
                finally:
                    registry.leave(1, entry)
        threads = [threading.Thread(target=worker, daemon=True) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(registry.entries, {})


if __name__ == '__main__':
    unittest.main()
