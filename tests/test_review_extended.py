import ast,re,unittest
from pathlib import Path
class ExtendedReview(unittest.TestCase):
 def run_check(self,text):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py';n=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='review_extended_checks');s={'re':re};exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),s);return '\n'.join(s['review_extended_checks'](text))
 def test_repeat_and_locations(self):
  p='هذه فقرة طويلة نسبياً نكررها حرفياً لكي نختبر التكرار الداخلي وحده دون الحكم على الكاتب.'
  r=self.run_check('  '+p+' \n'+p);self.assertIn('تكرار حرفي داخلي',r);self.assertIn('حروف 3',r)
 def test_literal_decimal_not_sentence_split(self):
  r=self.run_check('كانت قيمة العينة في التقرير المعروض اليوم 54.27 نقطة\nكانت قيمة العينة في التقرير المعروض اليوم -54.27 نقطة');self.assertIn('نفس الصياغة بأرقام مختلفة',r);self.assertIn('54.27',r);self.assertIn('-54.27',r)
 def test_context_is_not_false_contradiction(self):
  r=self.run_check('كانت قيمة العينة في سنة 2025 تساوي 40\nكانت قيمة العينة في سنة 2026 تساوي 50');self.assertIn('ليس تناقضاً مثبتاً',r)
 def test_cited_claim_not_missing(self):
  self.assertNotIn('ادعاء يحتاج إحالة محددة:',self.run_check('تشير الدراسات إلى أمر يحتاج فحصاً (Smith, 2025)'))
 def test_claim_without_marker(self):self.assertIn('ادعاء يحتاج إحالة محددة',self.run_check('تشير الدراسات إلى هذه النتيجة ويجب اختبار مصدرها'))
 def test_quote_and_structure(self):
  r=self.run_check('عنوان النص\nهذا اقتباس «طويل بما يكفي لاختبار غياب الإحالة في الفقرة»');self.assertIn('اقتباس بلا إحالة',r);self.assertIn('عنوان النص',r)
 def test_quote_imbalance(self):self.assertIn('علامات اقتباس غير متوازنة',self.run_check('هذا النص به «اقتباس بلا غلق'))
 def test_budget(self):
  r=self.run_check('\n'.join('تشير الدراسات إلى الادعاء رقم '+str(i)for i in range(300)));self.assertIn('عرض أول 24 ملاحظة',r);self.assertLess(len(r),25000)
 def test_arabic_numbers_and_empty(self):
  self.assertIn('٥٤٫٢٧',self.run_check('بلغت القيمة ٥٤٫٢٧ في هذا النص'));self.assertIn('لم تلتقط',self.run_check(''))
