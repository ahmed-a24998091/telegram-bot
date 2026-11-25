import ast,unittest
from pathlib import Path
class ExcelPrecision(unittest.TestCase):
 def test_overprecision_refused_before_build(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='excel');s={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),s)
  for v in [12345678901234567,-12345678901234567,1.2345678901234567]:
   with self.subTest(v=v),self.assertRaises(ValueError):s['excel']({'sheets':[{'headers':['value'],'rows':[[v]]}]})
