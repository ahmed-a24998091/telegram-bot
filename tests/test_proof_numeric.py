"""Proofreading must preserve signs, numeric separators and percentages."""
import ast,json,re,unittest
from pathlib import Path

class ProofNumeric(unittest.TestCase):
 def proposal(self,before,after):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py'
  n=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='proof_proposals')
  scope={'re':re,'json':json,'public_model':lambda *a:json.dumps({'edits':[{'before':before,'after':after,'reason':'fixture'}]})}
  exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),scope)
  return scope['proof_proposals']('هذا نص أصلي كاف للاختبار مع العبارة التالية: '+before+' في هذه العينة.')
 def test_numeric_changes_refused(self):
  for before,after in [('القيمة 54.27','القيمة -54.27'),('القيمة -54.27','القيمة 54.27'),('النسبة 10%','النسبة 10'),('النسبة 10','النسبة 10٪'),('القيمة 54.27','القيمة 54,27'),('القيمة ٥٤٫٢٧','القيمة ٥٤٬٢٧'),('الموعد 10:30','الموعد 10/30'),('القيمة 1,000','القيمة 1.000')]:
   with self.subTest(before=before,after=after):self.assertEqual(self.proposal(before,after),([],1))
 def test_unchanged_numbers_allow_local_text_edits(self):
  for value in ('-54.27','٥٤٫٢٧','10٪','10:30','2026-11-25','1,000'):
   with self.subTest(value=value):self.assertEqual(len(self.proposal('القيمه '+value,'القيمة '+value)[0]),1)
 def test_urls_remain_exact(self):
  self.assertEqual(self.proposal('الرابط https://example.org/v1.2','الرابط https://example.org/v1.3'),([],1))
