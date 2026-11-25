"""PDF text-presence checks use actual PDFs, never count generated page labels."""
import ast
import io
from pathlib import Path
import unittest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


def extract_function():
    path = Path(__file__).resolve().parents[1] / 'document_bot.py'
    node = next(n for n in ast.parse(path.read_text()).body
                if isinstance(n, ast.FunctionDef) and n.name == 'extract')
    scope = {'io': io}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), 'exec'), scope)
    return scope['extract']


def pdf(pages, password=None):
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=595, height=842)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                NameObject('/Subtype'): NameObject('/Type1'), NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):
                DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            stream = DecodedStreamObject()
            stream.set_data(('BT /F1 12 Tf 50 700 Td ('+text+') Tj ET').encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(stream)
    if password: writer.encrypt(password)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PDFContentTests(unittest.TestCase):
    def setUp(self):
        self.extract = extract_function()

    def test_blank_pages_cannot_become_readable_via_page_numbers(self):
        for count in (1, 12, 80):
            with self.assertRaises(ValueError):
                self.extract(pdf([''] * count), 'blank.pdf')

    def test_little_text_not_inflated_by_empty_page_labels(self):
        with self.assertRaises(ValueError):
            self.extract(pdf(['short'] + [''] * 11), 'short.pdf')

    def test_partial_read_is_explicit_and_page_order_preserved(self):
        text = 'This source contains readable text and the exact number 54.27 for testing.'
        out = self.extract(pdf([text, '', text.replace('54.27', '5510.8')]), 'partial.pdf')
        self.assertIn('قراءة نصية جزئية فقط', out)
        self.assertIn('الصفحات 2 ', out)
        self.assertIn('لم أقرأ محتواها البصري', out)
        self.assertLess(out.index('54.27'), out.index('5510.8'))

    def test_text_only_pdf_has_no_partial_warning(self):
        out = self.extract(pdf(['This source contains enough readable text to pass the sixty character threshold.']), 'text.pdf')
        self.assertNotIn('قراءة نصية جزئية', out)
        self.assertIn('[صفحة 1]', out)

    def test_encrypted_and_oversized_page_count_refused(self):
        for data in (pdf(['text'], password='test-only'), pdf([''] * 81)):
            with self.assertRaises(ValueError):
                self.extract(data, 'bad.pdf')

    def test_large_extracted_text_refused_not_clipped(self):
        with self.assertRaises(ValueError):
            self.extract(pdf(['x' * 300001]), 'large.pdf')
