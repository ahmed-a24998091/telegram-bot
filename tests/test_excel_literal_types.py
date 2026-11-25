import ast,io,re,types,unittest
from pathlib import Path
from openpyxl import Workbook,load_workbook
from openpyxl.styles import Font,PatternFill,Alignment,Border,Side
from openpyxl.utils import get_column_letter
class ExcelLiteralTypes(unittest.TestCase):
 def test_text_does_not_become_excel_error(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ['excel','excel_number_format']];scope=dict(globals());scope['G']=types.SimpleNamespace(clean=lambda value,limit:str(value)[:limit]);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope)
  literals=['#N/A','#VALUE!','#REF!','#DIV/0!','#NAME?','#NUM!','#NULL!','ordinary','=1+1','+SUM(A1)','-literal','@field']
  out=scope['excel']({'sheets':[{'headers':['#N/A'],'rows':[[v]for v in literals]+[[54.27]]}]});ws=load_workbook(out).active;self.assertEqual(ws['A1'].data_type,'s')
  for row,value in enumerate(literals,2):
   cell=ws.cell(row,1);self.assertEqual(cell.data_type,'s');self.assertEqual(cell.value,("'"+value)if value.startswith(('=','+','-','@'))else value)
  self.assertEqual(ws.cell(len(literals)+2,1).data_type,'n');self.assertEqual(ws.cell(len(literals)+2,1).value,54.27)
