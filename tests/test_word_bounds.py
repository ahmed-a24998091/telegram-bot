import ast,unittest
from pathlib import Path
class WordBounds(unittest.TestCase):
 def run_word(self,data):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='word');scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);return scope['word'](data)
 def invalid(self,section):
  with self.assertRaises(ValueError):self.run_word({'title':'fixture','sections':[section]})
 def test_paragraph_count_and_length(self):
  self.invalid({'paragraphs':['x']*13});self.invalid({'paragraphs':['x'*1601]});self.invalid({'paragraphs':'not a list'})
 def test_section_and_title_bounds(self):
  for d in [{'title':'x'*121,'sections':[]},{'title':'x','sections':[{}]*21},{'title':'x','sections':[]}]:
   with self.assertRaises(ValueError):self.run_word(d)
  self.invalid({'heading':'x'*121})
 def test_table_row_column_cell_bounds(self):
  for s in [{'rows':[['x']]*51},{'rows':[['x']*7]},{'headers':['a'],'rows':[['x','lost']]},{'rows':[['x'*501]]},{'headers':['x'*501],'rows':[['a']]},{'rows':['invalid']}]:self.invalid(s)
