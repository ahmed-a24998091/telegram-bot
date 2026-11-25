import ast,re,types,unittest
from pathlib import Path
class OfficeSourceIntent(unittest.TestCase):
 def run_handle(self,text,reply=False):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ['handle','kind_of']];built=[];scope={'re':re,'source_text':lambda *a:'prior source','build':lambda *a:built.append(a),'bot':types.SimpleNamespace(send=lambda *a:None)};exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),scope);msg={'chat':{'id':1,'type':'private'},'text':text}
  if reply:msg['reply_to_message']={'text':'prior source'}
  scope['handle'](msg);self.assertTrue(built);return built[0][2]
 def test_new_requests_not_substring_references(self):
  for text in ['write a word document about solar energy','اعمل ملف وورد جديد عن الطاقة الشمسية','make a word document about identity verification','write a word document about thisyear and identity']:
   with self.subTest(text=text):self.assertEqual(self.run_handle(text),text)
 def test_explicit_references_keep_prior_source(self):
  for text in ['اعمل الكلام ده وورد','اعمل دي وورد','make this a word document','put it in a word document','اعملها وورد']:
   with self.subTest(text=text):self.assertEqual(self.run_handle(text),'prior source')
  self.assertEqual(self.run_handle('اعمل ملف وورد جديد',reply=True),'prior source')
