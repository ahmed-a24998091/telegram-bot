import ast,unittest
from pathlib import Path
class ExcelDisplay(unittest.TestCase):
 def test_numeric_formats(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='excel_number_format');scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);fmt=scope['excel_number_format']
  for value in [1e-11,-1e-11,1e20,-1e20,1e15,-1e15]:
   with self.subTest(value=value):self.assertEqual(fmt(value),'0.##############E+00')
  for value in [0,54.27,-54.27,0.123456789012345,-0.123456789012345,1e-4,123456789012345]:
   with self.subTest(value=value):self.assertEqual(fmt(value),'#,##0.###############')
