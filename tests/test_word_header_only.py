import ast,io,re,types,unittest
from pathlib import Path
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt,Inches,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
class WordHeaderOnly(unittest.TestCase):
 def test_header_only_template_retained(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ['word','rtl','readable_links']];scope=dict(globals());scope['G']=types.SimpleNamespace(clean=lambda value,limit:str(value)[:limit]);exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope)
  out=scope['word']({'title':'Fixture','sections':[{'headers':['Name','Amount'],'rows':[]}]});d=Document(out);self.assertEqual(len(d.tables),1);self.assertEqual([[c.text for c in row.cells]for row in d.tables[0].rows],[['Name','Amount']])
  out=scope['word']({'title':'Fixture','sections':[{'paragraphs':['Text only']}]});self.assertFalse(Document(out).tables)
