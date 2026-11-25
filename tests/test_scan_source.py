import ast,base64,re,unittest
from pathlib import Path
class ScanSourcePreservation(unittest.TestCase):
 def test_no_destructive_preprocessing_in_source_embed(self):
  root=Path(__file__).resolve().parents[1];s=(root/'converter.Dockerfile').read_text();match=re.search(r'RUN echo (\S+) \| base64 -d > /app/scan_worker.py',s);self.assertIsNotNone(match);tree=ast.parse(base64.b64decode(match.group(1)).decode());build=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='build')
  self.assertFalse(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='prepare'for n in ast.walk(build)))
  self.assertTrue(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='image'for n in ast.walk(build)))
