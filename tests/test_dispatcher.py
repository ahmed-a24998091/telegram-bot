"""Offline queue tests. Run: python -m unittest discover -s tests -v"""
import ast
from pathlib import Path
import threading
import time
import unittest


def dispatcher_class():
    source = Path(__file__).resolve().parents[1] / 'bot.py'
    node = next(node for node in ast.parse(source.read_text()).body
                if isinstance(node, ast.ClassDef) and node.name == 'MessageDispatcher')
    scope = {'threading': threading}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), 'exec'), scope)
    return scope['MessageDispatcher']


class DispatcherTests(unittest.TestCase):
    def test_fifo_and_other_chat_progress(self):
        gate, started, other, finished = [threading.Event() for _ in range(4)]
        seen = []
        def handle(message):
            chat, number = message['chat']['id'], message['number']
            if (chat, number) == (1, 0):
                started.set()
                if not gate.wait(3):
                    return
            seen.append((chat, number))
            if chat == 2:
                other.set()
            if len(seen) == 3:
                finished.set()
        dispatcher = dispatcher_class()(handle, workers=2, capacity=2)
        dispatcher.submit({'chat': {'id': 1}, 'number': 0})
        try:
            self.assertTrue(started.wait(2))
            dispatcher.submit({'chat': {'id': 1}, 'number': 1})
            dispatcher.submit({'chat': {'id': 2}, 'number': 0})
            self.assertTrue(other.wait(2))
            self.assertNotIn((1, 1), seen)
        finally:
            gate.set()
        self.assertTrue(finished.wait(2))
        self.assertEqual([number for chat, number in seen if chat == 1], [0, 1])
        self.assertEqual(len(dispatcher.workers), 2)

    def test_full_queue_blocks_without_dropping_work(self):
        gate, started, admitted = [threading.Event() for _ in range(3)]
        seen = []
        def handle(message):
            started.set()
            if gate.wait(3):
                seen.append(message['number'])
        dispatcher = dispatcher_class()(handle, workers=1, capacity=1)
        dispatcher.submit({'chat': {'id': 1}, 'number': 0})
        self.assertTrue(started.wait(2))
        dispatcher.submit({'chat': {'id': 1}, 'number': 1})
        def producer():
            dispatcher.submit({'chat': {'id': 1}, 'number': 2})
            admitted.set()
        thread = threading.Thread(target=producer, daemon=True)
        thread.start()
        try:
            self.assertFalse(admitted.wait(0.05))
            self.assertEqual(len(dispatcher.pending), 1)
        finally:
            gate.set()
        self.assertTrue(admitted.wait(2))
        thread.join(2)
        end = time.monotonic() + 2
        while len(seen) < 3 and time.monotonic() < end:
            time.sleep(0.01)
        self.assertEqual(seen, [0, 1, 2])

    def test_handler_failure_releases_chat(self):
        finished = threading.Event()
        seen = []
        def handle(message):
            seen.append(message['number'])
            if message['number'] == 0:
                raise RuntimeError('synthetic failure')
            finished.set()
        dispatcher = dispatcher_class()(handle, workers=1, capacity=2)
        for number in range(2):
            dispatcher.submit({'chat': {'id': 1}, 'number': number})
        self.assertTrue(finished.wait(2))
        self.assertEqual(seen, [0, 1])


if __name__ == '__main__':
    unittest.main()
