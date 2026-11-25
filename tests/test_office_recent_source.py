import ast,time,threading,types,unittest
from pathlib import Path
class OfficeRecentSource(unittest.TestCase):
 def scope(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ['remember_send','source_text','build']];sent=[];scope={'time':time,'LAST':{},'SEND':lambda *a:None,'LOCK':threading.BoundedSemaphore(1),'bot':types.SimpleNamespace(send=lambda *a:sent.append(a))};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope);return scope,sent
 def test_valid_recent_text_preserved(self):
  for size in [16001,17003,18000]:
   with self.subTest(size=size):
    s,_=self.scope();text='x'*(size-3)+'END';s['remember_send'](1,text);self.assertEqual(s['source_text'](1,{}),text)
 def test_oversize_recent_text_refused(self):
  for size in [18001,30000]:
   with self.subTest(size=size):
    s,sent=self.scope();s['remember_send'](1,'x'*size);source=s['source_text'](1,{});self.assertEqual(len(source),18001);s['build'](1,'word',source,'fixture');self.assertIn('18000',sent[0][1]);self.assertTrue(s['LOCK'].acquire(False))
 def test_reply_remains_authoritative(self):
  s,_=self.scope();s['remember_send'](1,'cached '*100);self.assertEqual(s['source_text'](1,{'reply_to_message':{'text':'explicit reply'}}),'explicit reply')
