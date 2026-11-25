"""Source brackets and formulas must not be confused with generated markers."""
import ast,io,re,unittest
from pathlib import Path
from openpyxl import Workbook
from pptx import Presentation
from pptx.util import Inches

class BracketContent(unittest.TestCase):
 def extract(self,obj,name):
  out=io.BytesIO();obj.save(out)
  path=Path(__file__).resolve().parents[1]/'voice_bot.py'
  node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='study_extract')
  scope={'io':io,'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
  return scope['study_extract'](out.getvalue(),name)
 def test_bracketed_workbook(self):
  w=Workbook();w.active['A1']='[Real bracketed source text with literal number 54.27 for study.]'
  self.assertIn('[Real bracketed source text',self.extract(w,'fixture.xlsx'))
 def test_formula_only_source(self):
  w=Workbook();w.active['A1']='=SUM(123456789,987654321,246813579,135792468)'
  text=self.extract(w,'fixture.xlsx');self.assertIn('=SUM(',text);self.assertIn('لم أحسب',text)
 def test_bracketed_slides(self):
  p=Presentation();slide=p.slides.add_slide(p.slide_layouts[6]);slide.shapes.add_textbox(0,0,Inches(5),Inches(1)).text='[Real bracketed source text with literal number 54.27 for study.]'
  self.assertIn('[Real bracketed source text',self.extract(p,'fixture.pptx'))
