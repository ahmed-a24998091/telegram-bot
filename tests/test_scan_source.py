import ast,base64,re,unittest
from pathlib import Path
class ScanSourcePreservation(unittest.TestCase):
 def test_no_destructive_preprocessing_in_source_embed(self):
  root=Path(__file__).resolve().parents[1];s=(root/'converter.Dockerfile').read_text();matches=re.findall(r'RUN echo (\S+) \| base64 -d > /app/scan_worker.py',s);self.assertTrue(matches);tree=ast.parse(base64.b64decode(matches[-1]).decode());build=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='build')
  self.assertFalse(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='prepare'for n in ast.walk(build)))
  self.assertTrue(any(isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='image'for n in ast.walk(build)))
 def test_pixel_preflight_before_rasterization(self):
  tree=ast.parse(base64.b64decode(re.findall(r'RUN echo (\S+) \| base64 -d > /app/scan_worker.py',(Path(__file__).resolve().parents[1]/'converter.Dockerfile').read_text())[-1]).decode());build=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='build');source=ast.unparse(build)
  self.assertLess(source.index('width * height > 12000000'),source.index('page.get_pixmap'))
  self.assertLess(source.index('source.size'),source.index('pages = [cv2.imdecode'))
 def test_multiframe_refused_before_decode(self):
  tree=ast.parse(base64.b64decode(re.findall(r'RUN echo (\S+) \| base64 -d > /app/scan_worker.py',(Path(__file__).resolve().parents[1]/'converter.Dockerfile').read_text())[-1]).decode());source=ast.unparse(next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='build'));self.assertLess(source.index("getattr(source, 'n_frames', 1)"),source.index('pages = [cv2.imdecode'))

class TableDimensionMetadata(unittest.TestCase):
 def test_reset_before_streaming_and_column_guard(self):
  source=base64.b64decode(re.findall(r'RUN echo (\S+) \| base64 -d > /app/table_worker.py',(Path(__file__).resolve().parents[1]/'converter.Dockerfile').read_text())[-1]).decode();ast.parse(source);self.assertIn('sh.reset_dimensions()',source);self.assertLess(source.index('sh.reset_dimensions()'),source.index('add(sh.title,sh.iter_rows'));self.assertIn("if len(values)>50:raise ValueError('table columns')",source)
