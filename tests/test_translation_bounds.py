import ast,json,types,unittest,sys
from pathlib import Path
from unittest.mock import patch

class TranslationBounds(unittest.TestCase):
 def scope(self,name):
  p=Path(__file__).resolve().parents[1]/'intent_bundle.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name==name);self.sent=[];self.calls=[];owner=self;self.finish='stop'
  class Response:
   def raise_for_status(self):pass
   def json(self):return {'choices':[{'finish_reason':owner.finish,'message':{'content':'SYNTHETIC TRANSLATION'}}]}
   def iter_content(self,*a):return iter([b'synthetic-image'])
  def post(*a,**k):self.calls.append(k['json']);return Response()
  self.requests=types.SimpleNamespace(post=post,get=lambda *a,**k:Response())
  bot=types.SimpleNamespace(GROQ_MODEL='synthetic',TELEGRAM_TOKEN='synthetic',send=lambda c,t:self.sent.append(t),tg=lambda *a,**k:{'ok':True,'result':{'file_path':'synthetic.png'}},extract_image_text=lambda *a:self.source)
  scope={'bot':bot,'requests':self.requests};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);return scope[name]
 def test_reply_over_limit_refused_before_model(self):
  f=self.scope('translate_text');f(1,'translate to Arabic','X'*18000+' END123');self.assertFalse(self.calls);self.assertTrue(self.sent)
 def test_inline_over_limit_refused_before_model(self):
  f=self.scope('translate_text');f(1,'translate to Arabic '+'X'*18000);self.assertFalse(self.calls)
 def test_reply_at_limit_is_whole(self):
  f=self.scope('translate_text');source='X'*17993+' END123';f(1,'translate to Arabic',source);self.assertEqual(json.loads(self.calls[0]['messages'][1]['content'])['replied_source'],source);self.assertEqual(self.sent,['SYNTHETIC TRANSLATION'])
 def image(self,source):
  f=self.scope('translate_image');self.source=source
  with patch.dict(sys.modules,{'requests':self.requests}):f({'chat':{'id':1},'photo':[{'file_id':'fixture','file_size':15}]},'translate to Arabic')
 def test_image_transcription_over_limit_refused_before_model(self):
  self.image('X'*18000+' END123');self.assertFalse(self.calls)
 def test_image_at_limit_is_whole(self):
  source='X'*17993+' END123';self.image(source);self.assertEqual(json.loads(self.calls[0]['messages'][1]['content'])['image_transcription'],source);self.assertEqual(self.sent[-1],'SYNTHETIC TRANSLATION')

 def test_length_stopped_reply_never_sent_as_translation(self):
  f=self.scope('translate_text');self.finish='length';f(1,'translate to Arabic','synthetic source');self.assertNotIn('SYNTHETIC TRANSLATION',self.sent);self.assertTrue(self.sent)
 def test_missing_stop_reason_reply_never_sent_as_translation(self):
  f=self.scope('translate_text');self.finish=None;f(1,'translate to Arabic','synthetic source');self.assertNotIn('SYNTHETIC TRANSLATION',self.sent)
 def test_filtered_reply_never_sent_as_translation(self):
  f=self.scope('translate_text');self.finish='content_filter';f(1,'translate to Arabic','synthetic source');self.assertNotIn('SYNTHETIC TRANSLATION',self.sent)
 def test_length_stopped_image_never_sent_as_translation(self):
  f=self.scope('translate_image');self.source='synthetic source';self.finish='length'
  with patch.dict(sys.modules,{'requests':self.requests}):f({'chat':{'id':1},'photo':[{'file_id':'fixture','file_size':15}]},'translate to Arabic')
  self.assertNotIn('SYNTHETIC TRANSLATION',self.sent);self.assertEqual(len(self.calls),1)
