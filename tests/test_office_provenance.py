import ast,io,json,re,threading,types,unittest
from pathlib import Path
from unittest.mock import patch
class OfficeProvenance(unittest.TestCase):
 def run_build(self,nsections,nlinks,metadata=0):
  p=Path(__file__).resolve().parents[1]/'office_flow.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='build');out=[];sent=[];data={'title':'fixture','sections':[{'heading':'body','paragraphs':['text']}for i in range(nsections)]};bot=types.SimpleNamespace(send=lambda *a:sent.append(a),tg=lambda *a,**k:(out.append(k)or{'ok':True}),GROQ_MODEL='fixture')
  scope={'LOCK':threading.BoundedSemaphore(1),'bot':bot,'json':json,'re':re,'word':lambda d:(out.append(d)or io.BytesIO(b'docx'))};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope)
  source='\n'.join(['تم التحقق: fixture'+str(i)for i in range(metadata)]+['https://example.org/source-'+str(i)for i in range(nlinks)])
  response=types.SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'choices':[{'message':{'content':json.dumps(data)}}]})
  with patch('requests.post',return_value=response):scope['build'](1,'word',source,'fixture')
  self.assertTrue(scope['LOCK'].acquire(False));return out,sent
 def test_20_links_and12_metadata_preserved(self):
  out,_=self.run_build(1,20,12);data=out[0];pars=[p for s in data['sections'][1:]for p in s['paragraphs']];self.assertEqual(len(pars),32);self.assertEqual(pars[-1],'https://example.org/source-19');self.assertTrue(all(len(s['paragraphs'])<=12 for s in data['sections']))
 def test_section_overflow_no_file_not_silent_loss(self):
  out,sent=self.run_build(20,1);self.assertEqual(out,[]);self.assertTrue(sent)
 def test_exact_section_limit_succeeds(self):
  out,_=self.run_build(18,20);self.assertEqual(len(out[0]['sections']),20)
