import ast,unittest
from pathlib import Path
class ExcelBounds(unittest.TestCase):
 def run_excel(self,data):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='excel');scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);return scope['excel'](data)
 def sheet(self,**kw):return {'name':'fixture','headers':['one'],'rows':[['value']],**kw}
 def invalid(self,info):
  with self.assertRaises(ValueError):self.run_excel({'sheets':[info]})
 def test_sheet_count(self):
  for sheets in [[],[self.sheet()]*9]:
   with self.assertRaises(ValueError):self.run_excel({'sheets':sheets})
 def test_extra_cells_refused(self):self.invalid(self.sheet(rows=[['first','lost']]))
 def test_cell_length_and_nonfinite(self):
  for value in ['x'*1501,float('nan'),float('inf'),-float('inf')]:self.invalid(self.sheet(rows=[[value]]))
 def test_headers_rows_shape_and_counts(self):
  for info in [None,self.sheet(headers=[]),self.sheet(headers=['x']*13),self.sheet(rows=[['x']]*301),self.sheet(rows=['not a row'])]:self.invalid(info)
