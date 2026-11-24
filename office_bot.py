import io
import zipfile
import bot
import document_bot
import generate_bot

OLD_EXTRACT=document_bot.extract
ORIGINAL=bot.handle


def extract(data,name):
    low=name.lower()
    if low.endswith(('.xlsx','.pptx')):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>60*1024*1024:
                raise ValueError('المحتوى كبير بعد فك الملف. قسّمه لأجزاء.')
    if low.endswith('.xlsx'):
        from openpyxl import load_workbook
        wb=load_workbook(io.BytesIO(data),read_only=True,data_only=True,keep_links=False)
        parts=[];cells=0
        try:
            if len(wb.sheetnames)>30:raise ValueError('الملف أكثر من ٣٠ ورقة. ابعت الأوراق المطلوبة فقط.')
            for sheet in wb:
                parts.append('[ورقة: '+sheet.title+']')
                for row in sheet.iter_rows():
                    cells+=len(row)
                    if cells>60000:raise ValueError('الجدول كبير. ابعت جزء أصغر، بحد ٦٠ ألف خلية.')
                    vals=[str(c.value) if c.value is not None else '' for c in row]
                    if any(vals):parts.append(' | '.join(vals))
                    if sum(map(len,parts))>35000:return '\n'.join(parts)+'\n[تم اقتطاع باقي الجدول لطوله]'
            return '\n'.join(parts)+'\n[قراءة قيم محفوظة فقط. المعادلات لا تُحسب هنا، والقيم غير المحفوظة قد تظهر فارغة. لا تشمل الرسوم أو الصور.]'
        finally:wb.close()
    if low.endswith('.pptx'):
        from pptx import Presentation
        prs=Presentation(io.BytesIO(data))
        if len(prs.slides)>80:raise ValueError('العرض أكثر من ٨٠ شريحة. ابعت جزء أصغر.')
        parts=[]
        for i,slide in enumerate(prs.slides):
            parts.append('[شريحة '+str(i+1)+']')
            for shape in slide.shapes:
                if shape.has_text_frame:parts.append(shape.text_frame.text)
                if shape.has_table:
                    parts.extend(' | '.join(c.text for c in row.cells) for row in shape.table.rows)
            if sum(map(len,parts))>35000:return '\n'.join(parts)+'\n[تم اقتطاع باقي العرض لطوله]'
        return '\n'.join(parts)+'\n[القراءة نصوص وجداول فقط، لا تشمل صور الشرائح أو الصوت أو الفيديو أو التنسيق البصري.]'
    return OLD_EXTRACT(data,name)


document_bot.extract=extract


def handle(msg):
    name=msg.get('document',{}).get('file_name','').lower()
    if name.endswith(('.xlsx','.pptx')):
        return document_bot.handle_document(msg)
    if name.endswith(('.xls','.ppt','.xlsm','.pptm','.docm','.accdb','.mdb','.pub','.ost','.pst','.odt','.ods','.odp')):
        bot.send(msg['chat']['id'],'الصيغة دي مش مدعومة حالياً. المدعوم: DOCX وXLSX وPPTX وPDF النصي، أقل من ١٩ ميجابايت. احفظ نسخة بإحدى الصيغ دي. الماكروز والصور الممسوحة والملفات المحمية محتاجة معالجة منفصلة.');return
    if (msg.get('text') or '').strip() in ('/commands','/features'):
        ORIGINAL(msg)
        bot.send(msg['chat']['id'],'قراءة الملفات: PDF نصي وDOCX وXLSX وPPTX، أقل من ١٩ ميجابايت. نصوص وجداول فقط، مش تشغيل Office. المعادلات والماكروز مش بتتنفذ. إنشاء الملفات حالياً Word وPowerPoint بتصميم نصي قابل للتعديل.');return
    return ORIGINAL(msg)

bot.handle=handle
if __name__=='__main__':
    import threading
    generate_bot.daily_bot.extra_bot.init_reminders()
    threading.Thread(target=generate_bot.daily_bot.extra_bot.reminders_loop,daemon=True).start()
    print('office_features_ready',flush=True)
    bot.main()
