import ast,re,unittest
from pathlib import Path
FUNCS=('study_plain','study_pack_split','study_pack_excerpt','study_pack_word')
def build_ns():
 p=Path(__file__).resolve().parents[1]/'voice_bot.py'
 nodes=[n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name in FUNCS]
 class Office:
  @staticmethod
  def word(data):return data
 s={'re':re,'office_flow':Office,'STUDY_PACK_MARK':'مفتاح الإجابات'}
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),s)
 return s
class StudyPackSplit(unittest.TestCase):
 def setUp(self):self.ns=build_ns()
 def test_marker_split_separates(self):
  q,a=self.ns['study_pack_split']('س1: ما العاصمة؟\nس2: ما اللون؟\nمفتاح الإجابات\nج1: القاهرة\nج2: أزرق')
  self.assertEqual(q,'س1: ما العاصمة؟\nس2: ما اللون؟')
  self.assertEqual(a,'ج1: القاهرة\nج2: أزرق')
 def test_markdown_marker_still_splits(self):
  q,a=self.ns['study_pack_split']('س1؟\n**مفتاح الإجابات**\nج1')
  self.assertEqual(q,'س1؟');self.assertEqual(a,'ج1')
 def test_missing_marker_refused(self):
  with self.assertRaises(ValueError):self.ns['study_pack_split']('س1؟\nج1 مدمجة')
 def test_empty_answers_refused(self):
  with self.assertRaises(ValueError):self.ns['study_pack_split']('س1؟\nمفتاح الإجابات')
class StudyPackExcerpt(unittest.TestCase):
 def setUp(self):self.ns=build_ns()
 def test_short_source_whole(self):
  cut,note=self.ns['study_pack_excerpt']('نص قصير')
  self.assertEqual(cut,'نص قصير');self.assertIn('كاملاً',note)
 def test_long_source_labeled_not_silent(self):
  text='كلمة '*2000
  cut,note=self.ns['study_pack_excerpt'](text)
  self.assertLessEqual(len(cut),4000);self.assertIn('من أصل',note);self.assertIn(str(len(text.strip())),note)
 def test_exact_limit_whole(self):
  text='س'*4000
  cut,note=self.ns['study_pack_excerpt'](text)
  self.assertEqual(cut,text);self.assertIn('كاملاً',note)
class StudyPackWord(unittest.TestCase):
 def setUp(self):self.ns=build_ns()
 def pack(self,summary='ملخص الفقرة',questions='س1؟',answers='ج1',excerpt='مقطع حرفي',note='المصدر كاملاً (7 حرف).',source='المصدر الأصلي'):
  return self.ns['study_pack_word'](summary,questions,answers,excerpt,note,source,'حزمة مذاكرة')
 def test_section_order_and_separate_key(self):
  d=self.pack();heads=[s['heading']for s in d['sections']]
  self.assertEqual(heads[0],'المصدر وحدود القراءة')
  self.assertEqual(heads[1:],['الملخص','الأسئلة','مفتاح الإجابات - منفصل عن الأسئلة','مقتطفات حرفية من المصدر'])
  qsec=d['sections'][2];asec=d['sections'][3]
  self.assertEqual(qsec['paragraphs'],['س1؟']);self.assertEqual(asec['paragraphs'],['ج1'])
  self.assertEqual(d['sections'][0]['paragraphs'][0],'المصدر الأصلي')
 def test_excerpt_note_included(self):
  d=self.pack();self.assertEqual(d['sections'][4]['paragraphs'][0],'المصدر كاملاً (7 حرف).')
 def test_all_paragraphs_preserved(self):
  parts=['فقرة '+str(i)for i in range(40)]
  d=self.pack(summary='\n'.join(parts))
  got=[p for s in d['sections']if s['heading'].startswith('الملخص')or s['heading'].startswith('تابع الملخص')for p in s['paragraphs']]
  self.assertEqual(got,parts)
 def test_over_200_paragraphs_refused(self):
  with self.assertRaises(ValueError):self.pack(summary='\n'.join('فقرة '+str(i)for i in range(201)))
 def test_over_20_sections_refused(self):
  many='\n'.join('فقرة '+str(i)for i in range(49))
  with self.assertRaises(ValueError):self.pack(summary=many,questions=many,answers=many,excerpt=many)
 def test_long_line_split_preserved(self):
  d=self.pack(answers='a'*2801)
  joined=''.join(p for s in d['sections']if'مفتاح'in s['heading']for p in s['paragraphs'])
  self.assertEqual(joined,'a'*2801)
if __name__=='__main__':unittest.main()
