import ast,unittest
from pathlib import Path
class CancelFocus(unittest.TestCase):
 def scope(self):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='focused_intake_handle');sent=[];calls=[]
  class Bot:
   @staticmethod
   def send(c,t):sent.append((c,t))
  s={'bot':Bot,'PROOF_STATE':{},'REVIEW_STATE':{},'STUDY_STATE':{},'FEASIBILITY_STATE':{},'INTAKE_COMMANDS':{},'INTAKE_INNER':lambda msg:calls.append(msg)};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),s);return s,sent,calls
 def test_each_unfinished_form_wins_over_completed_reports(self):
  for active in ('PROOF_STATE','REVIEW_STATE','STUDY_STATE'):
   s,sent,calls=self.scope()
   for key in ('PROOF_STATE','REVIEW_STATE','STUDY_STATE'):s[key][1]={'awaiting':key==active,'text':'retained completed content'};s[key][2]={'awaiting':True}
   s['focused_intake_handle']({'chat':{'id':1,'type':'private'},'text':'/cancel'})
   self.assertNotIn(1,s[active]);self.assertFalse(calls);self.assertEqual(len(sent),1)
   for key in ('PROOF_STATE','REVIEW_STATE','STUDY_STATE'):
    self.assertIn(2,s[key])
    if key!=active:self.assertEqual(s[key][1]['text'],'retained completed content')
 def test_financial_form_wins_over_completed_reports(self):
  s,sent,calls=self.scope();s['FEASIBILITY_STATE'][1]=100;s['PROOF_STATE'][1]={'text':'keep'};s['focused_intake_handle']({'chat':{'id':1,'type':'private'},'text':'/cancel'});self.assertNotIn(1,s['FEASIBILITY_STATE']);self.assertEqual(s['PROOF_STATE'][1]['text'],'keep');self.assertFalse(calls)
 def test_no_unfinished_form_delegates(self):
  s,_,calls=self.scope();s['focused_intake_handle']({'chat':{'id':1,'type':'private'},'text':'/cancel'});self.assertEqual(len(calls),1)
 def test_group_never_changes_private_state(self):
  s,_,calls=self.scope();s['PROOF_STATE'][1]={'awaiting':True};s['focused_intake_handle']({'chat':{'id':1,'type':'group'},'text':'/cancel'});self.assertIn(1,s['PROOF_STATE']);self.assertEqual(len(calls),1)
