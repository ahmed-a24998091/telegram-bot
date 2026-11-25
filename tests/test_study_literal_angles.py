import ast,re,unittest
from pathlib import Path
class StudyLiteralAngles(unittest.TestCase):
 def clean(self,text):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='study_plain');s={'re':re};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),s);return s['study_plain'](text)
 def test_inequalities_preserve_words_numbers(self):
  text='القيمة x < 5 والحد y > 2، يجب حفظهما.';self.assertEqual(self.clean(text),text)
 def test_xml_like_source_is_not_deleted(self):
  text='Literal <sample>name</sample> and <br> source text';self.assertEqual(self.clean(text),text)
 def test_tag_named_variable_survives(self):self.assertEqual(self.clean('المتغير <b> ليس تنسيقاً مؤكداً'),'المتغير <b> ليس تنسيقاً مؤكداً')
 def test_existing_markdown_cleanup_remains(self):self.assertEqual(self.clean('## عنوان\n**محتوى**'),'عنوان\nمحتوى')
