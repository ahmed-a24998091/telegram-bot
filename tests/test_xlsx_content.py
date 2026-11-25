"""Actual XLSX content presence, budgets, formulas and dimension metadata."""
import ast
import io
from pathlib import Path
import re
import unittest
import zipfile
from openpyxl import Workbook


def extract_function():
    path=Path(__file__).resolve().parents[1]/'voice_bot.py'
    node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='study_extract')
    scope={'io':io,'re':re}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope)
    return scope[node.name]


class XLSXContent(unittest.TestCase):
    def raw(self,w):
        out=io.BytesIO();w.save(out);return out.getvalue()
    def extract(self,w):return extract_function()(self.raw(w),'fixture.xlsx')
    def test_coordinates_and_sheet_names_not_content(self):
        w=Workbook();w.active.title='Very long sheet name';
        for i in range(1,30):w.active.cell(i,1,'x')
        with self.assertRaises(ValueError):self.extract(w)
    def test_formula_error_and_hidden_sheet_explicit(self):
        w=Workbook();s=w.active;s['A1']='Literal Arabic ٥٥١٠٫٨ and decimal 54.27 remain source values.';s['A2']='=1+2';s['A3']='#DIV/0!'
        w.create_sheet('Hidden').sheet_state='hidden'
        text=self.extract(w)
        for needle in ('54.27','٥٥١٠٫٨','=1+2','معادلة غير محسوبة','خطأ في الخلية','لم أحسب','مخفية'):
            self.assertIn(needle,text)
    def test_blank_workbook_refused(self):
        with self.assertRaises(ValueError):self.extract(Workbook())
    def test_text_budget_refuses_not_truncates(self):
        w=Workbook()
        for i in range(1,12):w.active.cell(i,1,'X'*30000)
        with self.assertRaises(ValueError):self.extract(w)
    def test_sheet_row_and_column_limits(self):
        for coord in ('A2001','AO1'):
            w=Workbook();w.active[coord]='Source text enough for an ordinary extraction fixture.'
            with self.assertRaises(ValueError):self.extract(w)
        w=Workbook()
        for i in range(40):w.create_sheet(str(i))
        with self.assertRaises(ValueError):self.extract(w)
    def test_lying_small_dimensions_cannot_hide_cells(self):
        w=Workbook();s=w.active;s['A1']='Actual source text with sufficient content for study extraction.';s['B2']='HIDDENBYMETADATA 54.27'
        out=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.raw(w)))as zin,zipfile.ZipFile(out,'w')as zout:
            for item in zin.infolist():
                data=zin.read(item.filename)
                if item.filename=='xl/worksheets/sheet1.xml':data=data.replace(b'ref="A1:B2"',b'ref="A1:A1"')
                zout.writestr(item,data)
        text=extract_function()(out.getvalue(),'fixture.xlsx')
        self.assertIn('HIDDENBYMETADATA 54.27',text)
