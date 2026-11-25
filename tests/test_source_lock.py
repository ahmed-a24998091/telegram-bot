"""Source discovery semaphore must survive outbound transport failures."""
import ast
from pathlib import Path
import re
import threading
import time
import types
import unittest

class SourceLock(unittest.TestCase):
 def scope(self):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py'
  node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='source_request')
  sent=[]
  scope={'re':re,'time':time,'SOURCE_LAST':{},'SOURCE_LOCK':threading.BoundedSemaphore(1),'SOURCE_DOSSIERS':{},'bot':types.SimpleNamespace(send=lambda *a:sent.append(a)),'discovery':lambda *a:'المصادر: fixture','SEARCH_CAPABILITIES':'fixture'}
  exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope)
  return scope,sent
 def message(self,c):return {'chat':{'id':c,'type':'private'},'text':'/wiki fixture'}
 def test_failed_progress_and_error_delivery_release(self):
  s,_=self.scope();s['bot'].send=lambda *a:(_ for _ in ()).throw(RuntimeError('synthetic transport'))
  with self.assertRaises(RuntimeError):s['source_request'](self.message(1))
  self.assertTrue(s['SOURCE_LOCK'].acquire(False));s['SOURCE_LOCK'].release()
  delivered=[];s['bot'].send=lambda *a:delivered.append(a)
  self.assertTrue(s['source_request'](self.message(2)));self.assertIn('fixture',delivered[-1][1])
 def test_discovery_failure_and_success_release(self):
  s,sent=self.scope();s['discovery']=lambda *a:(_ for _ in ()).throw(ValueError('synthetic source'))
  self.assertTrue(s['source_request'](self.message(1)))
  self.assertTrue(s['SOURCE_LOCK'].acquire(False));s['SOURCE_LOCK'].release()
  s['discovery']=lambda *a:'المصادر: fixture'
  self.assertTrue(s['source_request'](self.message(2)));self.assertIn(2,s['SOURCE_DOSSIERS'])
 def test_busy_does_not_release_someone_elses_lock(self):
  s,sent=self.scope();s['SOURCE_LOCK'].acquire()
  self.assertTrue(s['source_request'](self.message(1)))
  self.assertFalse(s['SOURCE_LOCK'].acquire(False));s['SOURCE_LOCK'].release()
