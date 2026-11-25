import ast,re,io,os,json,unittest
from pathlib import Path
class ReviewExportComplete(unittest.TestCase):
 def export(self,report):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='review_export');captured={}
  class Office:
   @staticmethod
   def word(data):captured['data']=data;return io.BytesIO(b'docx')
  class Bot:
   @staticmethod
   def tg(*a,**k):return{'ok':True}
  scope={'office_flow':Office,'bot':Bot,'io':io,'os':os};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),scope);scope['review_export'](1,{'report':report},'word');return captured['data']
 def test_all_findings_preserved(self):
  parts=['تقرير فحص النص والمراجع','ملاحظات محددة وخطوات المراجعة']+['finding '+str(i)for i in range(90)]+['مصادر الفحص وحدوده','Final limits']
  d=self.export('\n\n'.join(parts));flat=[x for s in d['sections']for x in s['paragraphs']]
  for p in parts[2:-2]+['Final limits']:self.assertIn(p,flat)
  self.assertLessEqual(len(d['sections']),20);self.assertTrue(all(len(s['paragraphs'])<=12 for s in d['sections']))
 def test_semantic_overhead_compacts_without_loss(self):
  headings=['طبيعة التقرير وحدوده','فحص أوسع داخل النص','خريطة النص','ملخص الملاحظات','ملاحظات محددة وخطوات المراجعة','جرد أرقام للمراجعة','البنية الظاهرة وخطة التحسين','ما يحتاج مصدراً أو قراءة بشرية','فحص وجود المراجع','مطابقة النص مع مصادر أخرى','الخطوة التالية','مصادر الفحص وحدوده']
  parts=[]
  for i,h in enumerate(headings):parts.extend([h]+['value '+str(i)+'-'+str(j)for j in range(13)])
  with self.assertRaises(ValueError):self.export('\n\n'.join(parts)) # 168 pieces exceeds documented160 cap, never truncates.
