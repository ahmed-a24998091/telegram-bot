import ast,re,unittest
from pathlib import Path
class OfficeFormatBoundaries(unittest.TestCase):
 def classify(self,text):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';n=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='kind_of');s={'re':re};exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),s);return s['kind_of'](text)
 def test_substrings_remain_conversation(self):
  for text in ['That was an excellent explanation, thanks','Tell me about docxtract library','powerpointless','someword','xlsxwriter','باوربوينتات']:
   with self.subTest(text=text):self.assertIsNone(self.classify(text))
 def test_real_format_requests(self):
  for kind,texts in {'word':['اعمل وورد','ملف ورد','/word fixture','output.docx','WORD'],'excel':['اكسل','إكسيل','/excel fixture','output.xlsx','EXCEL'],'slides':['اعمل باور بوينت','بوربوينت','/slides fixture','output.pptx','POWERPOINT']}.items():
   for text in texts:
    with self.subTest(text=text):self.assertEqual(self.classify(text),kind)
