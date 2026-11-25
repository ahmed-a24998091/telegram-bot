"""Real PPTX grouped-text study extraction tests."""
import ast
import io
from pathlib import Path
import re
import unittest
from pptx import Presentation
from pptx.util import Inches


def extract_function():
    path = Path(__file__).resolve().parents[1] / 'voice_bot.py'
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'study_extract')
    scope = {'io': io, 're': re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope[node.name]


class PPTXGroups(unittest.TestCase):
    def deck(self):
        p = Presentation()
        return p, p.slides.add_slide(p.slide_layouts[6])

    def extract(self, p):
        out = io.BytesIO()
        p.save(out)
        return extract_function()(out.getvalue(), 'fixture.pptx')

    def box(self, shapes, text):
        shapes.add_textbox(0, 0, Inches(5), Inches(1)).text = text

    def test_nested_groups_and_literal_number(self):
        p, slide = self.deck()
        self.box(slide.shapes, 'FIRST ordinary paragraph with enough source text for study.')
        group = slide.shapes.add_group_shape()
        self.box(group.shapes.add_group_shape().shapes, 'GROUPED value 54.27 and Arabic ٥٥١٠٫٨')
        self.box(slide.shapes, 'LAST paragraph')
        text = self.extract(p)
        self.assertLess(text.index('FIRST'), text.index('GROUPED'))
        self.assertLess(text.index('GROUPED'), text.index('LAST'))
        self.assertIn('54.27', text)
        self.assertIn('٥٥١٠٫٨', text)
        self.assertIn('مش ترتيباً بصرياً مضموناً', text)

    def test_empty_slides_cannot_pass_via_markers(self):
        p, slide = self.deck()
        for _ in range(12): p.slides.add_slide(p.slide_layouts[6])
        with self.assertRaises(ValueError): self.extract(p)

    def test_partial_deck_names_missing_text_slides(self):
        p, slide = self.deck()
        self.box(slide.shapes, 'Sufficient literal source text for this extraction fixture.')
        p.slides.add_slide(p.slide_layouts[6])
        text = self.extract(p)
        self.assertIn('شرائح بلا نص مستخرج: 2', text)
        self.assertIn('لم أقرأ الصور أو الرسوم', text)

    def test_merged_table_content_not_repeated(self):
        p, slide = self.deck()
        table = slide.shapes.add_table(1, 2, 0, 0, Inches(5), Inches(1)).table
        table.cell(0, 0).merge(table.cell(0, 1))
        table.cell(0, 0).text = 'MERGED content long enough to pass the source text minimum.'
        self.assertEqual(self.extract(p).count('MERGED'), 1)

    def test_deep_groups_refused(self):
        p, slide = self.deck()
        shapes = slide.shapes
        for _ in range(14): shapes = shapes.add_group_shape().shapes
        self.box(shapes, 'Deep grouped text is refused rather than silently omitted.')
        with self.assertRaises(ValueError): self.extract(p)
