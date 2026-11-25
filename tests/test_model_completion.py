import ast,types,unittest
from pathlib import Path
class ModelCompletion(unittest.TestCase):
 def scope(self,finish):
  p=Path(__file__).resolve().parents[1]/'bot.py';names={'ask_gemini','ask_groq','ask_pollinations','answer'};nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in names]
  class Response:
   status_code=200
   def raise_for_status(self):pass
   def json(self):return {'choices':[{'finish_reason':finish,'message':{'content':'SYNTHETIC RESULT'}}],'candidates':[{'finishReason':'STOP'if finish=='stop'else'MAX_TOKENS','content':{'parts':[{'text':'SYNTHETIC RESULT'}]}}]}
  scope={'requests':types.SimpleNamespace(post=lambda *a,**k:Response()),'GEMINI_KEY':'synthetic','GROQ_KEY':'synthetic','GEMINI_MODEL':'synthetic','GROQ_MODEL':'synthetic','SYSTEM':'synthetic','history':{}}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope);return scope
 def test_complete_providers_return(self):
  s=self.scope('stop')
  for name in ('ask_gemini','ask_groq','ask_pollinations'):self.assertEqual(s[name]([]),'SYNTHETIC RESULT')
 def test_incomplete_providers_raise_for_fallback(self):
  s=self.scope('length')
  for name in ('ask_gemini','ask_groq','ask_pollinations'):
   with self.assertRaises(ValueError):s[name]([])
 def test_missing_completion_rejected(self):
  s=self.scope(None)
  for name in ('ask_gemini','ask_groq','ask_pollinations'):
   with self.assertRaises(ValueError):s[name]([])
 def test_first_incomplete_then_next_success(self):
  s=self.scope('length');s['ask_groq']=lambda m:'COMPLETE FALLBACK';out=s['answer'](1,'synthetic question');self.assertEqual(out,'COMPLETE FALLBACK');self.assertEqual(s['history'][1][-1]['text'],'COMPLETE FALLBACK')
 def test_all_incomplete_not_saved_as_model_answer(self):
  s=self.scope('length');out=s['answer'](1,'synthetic question');self.assertNotEqual(out,'SYNTHETIC RESULT');self.assertEqual(s['history'][1],[])
