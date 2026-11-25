import ast,unittest
from pathlib import Path
class SlideNotes(unittest.TestCase):
 def test_invalid_notes_refused_before_builder(self):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='slides');scope={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope)
  for notes in ['x'*1501,None,12,[],{}]:
   with self.subTest(notes_type=type(notes).__name__),self.assertRaises(ValueError):scope['slides']({'slides':[{'title':'fixture','bullets':['fixture'],'notes':notes}]})
