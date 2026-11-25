import ast,threading,types,unittest
from pathlib import Path
class OfficeInputGuard(unittest.TestCase):
 def scope(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='build');sent=[];scope={'LOCK':threading.BoundedSemaphore(1),'bot':types.SimpleNamespace(send=lambda *a:sent.append(a))};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);return scope,sent
 def test_oversize_refused_before_provider_or_lock(self):
  for kind in ['word','excel','slides']:
   s,sent=self.scope();s['build'](1,kind,'x'*18001,'fixture');self.assertIn('18000',sent[0][1]);self.assertTrue(s['LOCK'].acquire(False))
 def test_exact_limit_reaches_normal_flow(self):
  s,sent=self.scope();s['LOCK'].acquire();s['build'](1,'word','x'*18000,'fixture');self.assertIn('مشغول',sent[0][1])
