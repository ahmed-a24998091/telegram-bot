import ast,io,zipfile,threading,types,unittest
from pathlib import Path
class ScanPackage(unittest.TestCase):
 def convert(self,extra=(),body=b'<document/>'):
  nodes=[n for n in ast.parse((Path(__file__).resolve().parents[1]/'conversion_bot.py').read_text()).body if isinstance(n,ast.FunctionDef)and n.name in ('convert_scan','bounded_scan_response')]
  output=io.BytesIO()
  with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED)as z:
   z.writestr('word/document.xml',body)
   for name,data in extra:z.writestr(name,data)
  class Response:
   content=output.getvalue()
   def raise_for_status(self):pass
   def close(self):pass
   def iter_content(self,n):
    for i in range(0,len(self.content),n):yield self.content[i:i+n]
  sent=[]
  def tg(method,**kw):
   if method=='getFile':return {'ok':True,'result':{'file_path':'synthetic'}}
   sent.append(method);return {'ok':True}
  bot=types.SimpleNamespace(send=lambda*x:None,tg=tg,TELEGRAM_TOKEN='synthetic')
  scope={'io':io,'zipfile':zipfile,'MAX_BYTES':15*1024*1024,'LOCK':threading.Lock(),'bot':bot,'SCAN_NOTE':'fixture','MIME':{'docx':'fixture'},'os':types.SimpleNamespace(environ={'CONVERTER_URL':'https://fixture.invalid','CONVERTER_KEY':'synthetic'}),'requests':types.SimpleNamespace(get=lambda*a,**kw:Response(),post=lambda*a,**kw:Response())}
  exec(compile(ast.Module(body=nodes,type_ignores=[]),'scan','exec'),scope);scope['convert_scan']({'chat':{'id':1}},{'photo':[{'file_id':'synthetic'}]});self.assertFalse(scope['LOCK'].locked());return sent
 def test_normal_package_delivered(self):self.assertEqual(self.convert(),['sendDocument'])
 def test_expanded_package_refused(self):self.assertEqual(self.convert(body=b'x'*(61*1024*1024)),[])
 def test_macro_package_refused(self):self.assertEqual(self.convert(extra=[('word/vbaProject.bin',b'fixture')]),[])
 def test_excess_entries_refused(self):self.assertEqual(self.convert(extra=[('word/part%s'%i,b'')for i in range(10000)]),[])

class ScanStream(unittest.TestCase):
 def read(self,response,limit):
  tree=ast.parse((Path(__file__).resolve().parents[1]/'conversion_bot.py').read_text());n=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='bounded_scan_response');scope={};exec(compile(ast.Module(body=[n],type_ignores=[]),'scan','exec'),scope);return scope['bounded_scan_response'](response,limit)
 class Response:
  def __init__(self,chunks,error=False):self.chunks=chunks;self.closed=False;self.reads=0;self.error=error
  @property
  def content(self):raise AssertionError('unbounded read')
  def raise_for_status(self):
   if self.error:raise ValueError('status')
  def close(self):self.closed=True
  def iter_content(self,n):
   for chunk in self.chunks:self.reads+=1;yield chunk
 def test_exact_boundary(self):
  r=self.Response([b'ab',b'cd']);self.assertEqual(self.read(r,4),b'abcd');self.assertTrue(r.closed)
 def test_excess_stops_without_rest(self):
  r=self.Response([b'ab',b'cde',b'never read'])
  with self.assertRaises(ValueError):self.read(r,4)
  self.assertEqual(r.reads,2);self.assertTrue(r.closed)
 def test_error_closes(self):
  r=self.Response([],True)
  with self.assertRaises(ValueError):self.read(r,4)
  self.assertTrue(r.closed);self.assertEqual(r.reads,0)
