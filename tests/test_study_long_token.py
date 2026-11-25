import ast,unittest
from pathlib import Path
class StudyLongToken(unittest.TestCase):
 def split(self,text):
  p=Path(__file__).resolve().parents[1]/'voice_bot.py';node=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='study_slide_lines');s={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(p),'exec'),s);return s['study_slide_lines'](text)
 def test_unbroken_tokens_preserved(self):
  for size in [145,146,173,290,291,1680,1681]:
   with self.subTest(size=size):
    text='X'*(size-3)+'END';lines=self.split(text);self.assertEqual(''.join(lines),text);self.assertTrue(all(0<len(line)<=145 for line in lines))
 def test_normal_words_and_limit(self):
  text='alpha beta\ngamma delta';self.assertEqual(self.split(text),['alpha beta','gamma delta']);self.assertEqual(len(self.split('x'*1680)),24);self.assertEqual(len(self.split('x'*1681)),25)
