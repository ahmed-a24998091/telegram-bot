"""Revision pack source spans preserve decimal literals and newline content."""
import ast
from pathlib import Path
import re
import unittest


def spans(text):
 p=Path(__file__).resolve().parents[1]/'voice_bot.py'
 n=next(n for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='pack_source_lines')
 scope={'re':re};exec(compile(ast.Module(body=[n],type_ignores=[]),str(p),'exec'),scope)
 return scope['pack_source_lines'](text)

class PackSpans(unittest.TestCase):
 def test_decimal_and_unpunctuated_newline_preserved(self):
  first='First unpunctuated paragraph contains the literal amount 54.27'
  second='Second sentence preserves a useful definition and clear words.'
  self.assertEqual(spans(first+'\n'+second),[first,second])
 def test_dotted_url_and_multiple_sentences(self):
  a='Research source https://example.org/study/v1.2 includes a literal value 54.27.'
  b='This second sentence includes the literal Arabic number ٥٥١٠٫٨.'
  self.assertEqual(spans(a+' '+b),[a,b])
 def test_crlf_and_line_separators(self):
  lines=['First source paragraph has enough characters for review',
         'Second source paragraph has enough characters for review',
         'Third source paragraph has enough characters for review']
  self.assertEqual(spans('\r\n'.join(lines)),lines)
  self.assertEqual(spans('\u2028'.join(lines)),lines)
 def test_bounds_remain_explicit(self):
  for value in ('X'*6001, '\n'.join('Sentence %s contains enough characters for review.'%i for i in range(41)), 'tiny'):
   with self.assertRaises(ValueError):spans(value)
  line='X'*701
  with self.assertRaises(ValueError):spans(line)
 def test_no_phantom_trailing_fragment(self):
  text='This whole sentence contains a literal numerical quantity 0.000001.'
  self.assertEqual(spans(text),[text])
