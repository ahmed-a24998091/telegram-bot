import io
import os
import re
import threading
import zipfile
import requests
import bot
import finish_bot

ORIGINAL=bot.handle
MAX_BYTES=15*1024*1024
FORMATS={'doc':('docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),'xls':('xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),'ppt':('pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation')}
LOCK=threading.Lock()


def convert_document(msg):
    doc=msg['document'];chat=msg['chat']['id'];name=doc.get('file_name','document.doc');ext=name.rsplit('.',1)[-1].lower()
    if doc.get('file_size',0)>MAX_BYTES:
        bot.send(chat,'التحويل للملفات القديمة لحد ١٥ ميجابايت. ابعت نسخة أصغر.');return
    url=os.environ.get('CONVERTER_URL','').rstrip('/');key=os.environ.get('CONVERTER_KEY','')
    if not url.startswith('https://') or not key:
        bot.send(chat,'خدمة التحويل مش جاهزة حالياً. جرّب بعدين.');return
    if not LOCK.acquire(False):
        bot.send(chat,'فيه ملف بيتحول دلوقتي. جرّب تاني بعد دقيقة.');return
    try:
        bot.send(chat,'جاري التحويل')
        meta=bot.tg('getFile',data={'file_id':doc['file_id']})
        if not meta.get('ok'):raise ValueError('download')
        r=requests.get('https://api.telegram.org/file/bot'+bot.TELEGRAM_TOKEN+'/'+meta['result']['file_path'],stream=True,timeout=40)
        r.raise_for_status();data=bytearray()
        for chunk in r.iter_content(65536):
            data.extend(chunk)
            if len(data)>MAX_BYTES:raise ValueError('size')
        if not data.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):raise ValueError('format')
        # Free service cold starts may take a minute. No document upload in this health request.
        requests.get(url+'/health',timeout=95).raise_for_status()
        r=requests.post(url+'/convert',data=data,headers={'Authorization':'Bearer '+key,'X-Format':ext},stream=True,timeout=90)
        if r.status_code==429:
            bot.send(chat,'خدمة التحويل مشغولة دلوقتي. جرّب بعد دقيقة.');return
        r.raise_for_status();output=bytearray()
        for chunk in r.iter_content(65536):
            output.extend(chunk)
            if len(output)>15*1024*1024:raise ValueError('output size')
        with zipfile.ZipFile(io.BytesIO(output)) as z:
            if len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>60*1024*1024:raise ValueError('expanded size')
            expected={'doc':'word/document.xml','xls':'xl/workbook.xml','ppt':'ppt/presentation.xml'}[ext]
            if expected not in z.namelist() or any('vbaproject' in n.lower() for n in z.namelist()):raise ValueError('output format')
        modern,mime=FORMATS[ext];stem=re.sub(r'[^\w\u0600-\u06ff .-]','_',name.rsplit('.',1)[0])[:100] or 'document'
        result=bot.tg('sendDocument',data={'chat_id':chat},files={'document':(stem+'.'+modern,io.BytesIO(output),mime)})
        if not result.get('ok'):raise ValueError('delivery')
        print('legacy_conversion_sent',ext,flush=True)
    except Exception:
        print('legacy_conversion_failed',ext,flush=True)
        bot.send(chat,'مقدرتش أحول الملف ده. ممكن يكون محمي أو تالف أو معقد على الخدمة المجانية. جرّب نسخة مفتوحة وأصغر.');return
    finally:LOCK.release()


def handle(msg):
    name=msg.get('document',{}).get('file_name','')
    if name.rsplit('.',1)[-1].lower() in FORMATS:
        if msg['chat'].get('type')!='private':return ORIGINAL(msg)
        return convert_document(msg)
    return ORIGINAL(msg)

bot.handle=handle
if __name__=='__main__':
    finish_bot.EXTRA.init_reminders()
    threading.Thread(target=finish_bot.EXTRA.reminders_loop,daemon=True).start()
    print('legacy_conversion_ready',flush=True)
    bot.main()
