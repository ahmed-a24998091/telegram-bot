import ast,io,zipfile,threading,types,unittest
from pathlib import Path
class ScanPackage(unittest.TestCase):
 def convert(self,extra=(),body=b'<document/>'):
  n=next(n for n in ast.parse((Path(__file__).resolve().parents[1]/'conversion_bot.py').read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='convert_scan')
  output=io.BytesIO()
  with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as z:
   z.writestr('word/document.xml',body)
   for name,data in extra:z.writestr(name,data)
  class Response:
   content=output.getvalue()
   def raise_for_status(self):pass
  sent=[]
  def tg(method,**kw):
   if method=='getFile':return {'ok':True,'result':{'file_path':'synthetic'}}
   sent.append(method);return {'ok':True}
  bot=types.SimpleNamespace(send=lambda*x:None,tg=tg,TELEGRAM_TOKEN='synthetic')
  scope={'io':io,'zipfile':zipfile,'MAX_BYTES':15*1024*1024,'LOCK':threading.Lock(),'bot':bot,'SCAN_NOTE':'fixture','MIME':{'docx':'fixture'},'os':types.SimpleNamespace(environ={'CONVERTER_URL':'https://fixture.invalid','CONVERTER_KEY':'synthetic'}),'requests':types.SimpleNamespace(get=lambda*a,**kw:Response(),post=lambda*a,**kw:Response())}
  exec(compile(ast.Module(body=[n],type_ignores=[]),'scan','exec'),scope);scope['convert_scan']({'chat':{'id':1}},{'photo':[{'file_id':'synthetic'}]});self.assertFalse(scope['LOCK'].locked());return sent
 def test_normal_package_delivered(self):self.assertEqual(self.convert(),['sendDocument'])
 def test_expanded_package_refused(self):self.assertEqual(self.convert(body=b'x'*(61*1024*1024)),[])
 def test_macro_package_refused(self):self.assertEqual(self.convert(extra=[('word/vbaProject.bin',b'fixture')]),[])
 def test_excess_entries_refused(self):self.assertEqual(self.convert(extra=[('word/part%s'%i,b'')for i in range(10000)]),[])
