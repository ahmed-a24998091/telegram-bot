"""Actual DOCX extraction fixtures. Requires existing python-docx dependency."""
import ast
import io
from pathlib import Path
import unittest
from docx import Document


def extract_function():
    path = Path(__file__).resolve().parents[1] / 'document_bot.py'
    nodes = [n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name in {'docx_ordered_text', 'extract'}]
    scope = {'io': io, 'zipfile': __import__('zipfile')}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), 'exec'), scope)
    return scope['extract']


class DocxOrderTests(unittest.TestCase):
    def extract(self, document):
        out = io.BytesIO()
        document.save(out)
        return extract_function()(out.getvalue(), 'fixture.docx')

    def test_paragraph_table_paragraph_order(self):
        d = Document()
        d.add_paragraph('FIRST before table')
        table = d.add_table(rows=1, cols=2)
        table.cell(0, 0).text = 'MIDDLE price 54.27'
        table.cell(0, 1).text = 'القيمة ٥٥١٠٫٨'
        d.add_paragraph('LAST after table')
        text = self.extract(d)
        self.assertLess(text.index('FIRST'), text.index('MIDDLE'))
        self.assertLess(text.index('MIDDLE'), text.index('LAST'))
        self.assertIn('54.27', text)
        self.assertIn('٥٥١٠٫٨', text)

    def test_nested_table_and_cell_paragraph_order(self):
        d = Document()
        cell = d.add_table(rows=1, cols=1).cell(0, 0)
        cell.text = 'CELL BEFORE'
        cell.add_table(rows=1, cols=1).cell(0, 0).text = 'NESTED'
        cell.add_paragraph('CELL AFTER')
        d.add_paragraph('DOCUMENT END')
        text = self.extract(d)
        self.assertLess(text.index('CELL BEFORE'), text.index('NESTED'))
        self.assertLess(text.index('NESTED'), text.index('CELL AFTER'))
        self.assertLess(text.index('CELL AFTER'), text.index('DOCUMENT END'))

    def test_horizontal_merged_cell_not_repeated(self):
        d = Document()
        table = d.add_table(rows=1, cols=2)
        table.cell(0, 0).merge(table.cell(0, 1)).text = 'MERGED CONTENT'
        self.assertEqual(self.extract(d).count('MERGED CONTENT'), 1)

    def test_large_text_rejected_not_silently_truncated(self):
        d = Document()
        d.add_paragraph('x' * 300001)
        with self.assertRaises(ValueError):
            self.extract(d)

    def test_deep_nested_table_rejected(self):
        d = Document()
        parent = d
        for _ in range(14):
            parent = parent.add_table(rows=1, cols=1).cell(0, 0)
        parent.text = 'Too deep'
        with self.assertRaises(ValueError):
            self.extract(d)
