import io,os,re,threading,zipfile,requests
import bot,finish_bot
ORIGINAL=bot.handle
MAX_BYTES=15*1024*1024
FORMATS={'doc':('docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document'),'xls':('xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),'ppt':('pptx','application/vnd.openxmlformats-officedocument.presentationml.presentation')}
MIME={'pdf':'application/pdf','docx':FORMATS['doc'][1],'xlsx':FORMATS['xls'][1],'pptx':FORMATS['ppt'][1],'csv':'text/csv'}
LOCK=threading.Lock()
def target_of(text):
 t=(text or '').lower()
 # Target is normally after the last to/إلى/لـ marker, never the PDF source name.
 words=list(re.finditer(r'pdf|بي\s*دي\s*اف|docx|word|وورد|ورد|xlsx|excel|اكسل|إكسل|pptx|powerpoint|بوربوينت|بور\s*بوينت|csv',t))
 if not words:return ''
 v=words[-1].group();return 'pdf' if re.fullmatch(r'pdf|بي\s*دي\s*اف',v) else 'docx' if v in ('docx','word','وورد','ورد') else 'xlsx' if v in ('xlsx','excel','اكسل','إكسل') else 'csv' if v=='csv' else 'pptx'
def convert_document(msg,target=''):
 doc=msg['document'];chat=msg['chat']['id'];name=doc.get('file_name','document');ext=name.rsplit('.',1)[-1].lower();target=target or FORMATS.get(ext,('',))[0]
 pairs={('pdf','xlsx'),('docx','xlsx'),('xlsx','docx'),('doc','docx'),('xls','xlsx'),('ppt','pptx'),('pdf','docx')}|{(s,'pdf') for s in ('doc','docx','xls','xlsx','ppt','pptx')}|{('xls','csv'),('xlsx','csv')}
 if not target:
  bot.send(chat,'عايز تحوله لإيه؟ رد على الملف واكتب: حوله PDF أو حوله Word.');return
 if (ext,target)not in pairs:
  bot.send(chat,'التحويل المباشر المتاح: Word وExcel وPowerPoint إلى PDF، وPDF نصي إلى Word، والملفات القديمة للصيغ الحديثة، وExcel إلى CSV. واستخراج جداول PDF أوWord إلىExcel، وإعادة بناء جداولExcel فيWord، مش نسخة مطابقة. التحويل لباقي برامج أوفيس محتاج إعادة ترتيب المحتوى مش نسخة مطابقة.');return
 limit=10*1024*1024 if ext=='pdf' else MAX_BYTES
 if doc.get('file_size',0)>limit:
  bot.send(chat,'الحد PDF لحد ١٠ ميجابايت و٢٠ صفحة، وباقي التحويلات ١٥ ميجابايت. ابعت نسخة أصغر.');return
 url=os.environ.get('CONVERTER_URL','').rstrip('/');key=os.environ.get('CONVERTER_KEY','')
 if not url.startswith('https://')or not key:bot.send(chat,'خدمة التحويل مش جاهزة حالياً. جرّب بعدين.');return
 if not LOCK.acquire(False):bot.send(chat,'فيه ملف بيتحول دلوقتي. جرّب تاني بعد دقيقة.');return
 try:
  bot.send(chat,'جاري التحويل');meta=bot.tg('getFile',data={'file_id':doc['file_id']})
  if not meta.get('ok'):raise ValueError('download')
  r=requests.get('https://api.telegram.org/file/bot'+bot.TELEGRAM_TOKEN+'/'+meta['result']['file_path'],stream=True,timeout=40);r.raise_for_status();data=bytearray()
  for chunk in r.iter_content(65536):
   data.extend(chunk)
   if len(data)>limit:raise ValueError('size')
  requests.get(url+'/health',timeout=95).raise_for_status()
  r=requests.post(url+'/convert',data=data,headers={'Authorization':'Bearer '+key,'X-Format':ext,'X-Target':target},stream=True,timeout=90)
  if r.status_code==429:bot.send(chat,'خدمة التحويل مشغولة دلوقتي. جرّب بعد دقيقة.');return
  r.raise_for_status();output=bytearray();mode=r.headers.get('X-Conversion-Mode','')
  for chunk in r.iter_content(65536):
   output.extend(chunk)
   if len(output)>MAX_BYTES:raise ValueError('output size')
  if target in ('docx','xlsx','pptx'):
   with zipfile.ZipFile(io.BytesIO(output))as z:
    expected={'docx':'word/document.xml','xlsx':'xl/workbook.xml','pptx':'ppt/presentation.xml'}[target]
    if expected not in z.namelist()or len(z.infolist())>10000 or sum(i.file_size for i in z.infolist())>60*1024*1024 or any('vbaproject'in n.lower()for n in z.namelist()):raise ValueError('package')
  elif target=='pdf'and not output.startswith(b'%PDF-'):raise ValueError('PDF')
  stem=re.sub(r'[^\w\u0600-\u06ff .-]','_',name.rsplit('.',1)[0])[:100]or'document'
  caption=''
  if mode=='table-extraction':caption='استخراج الجداول فقط، مش تحويل مطابق للملف. النص خارج الجداول والصور وتوزيع الصفحات مش منتقلين. راجع الخلايا المدمجة واتجاه العربي.'
  elif mode=='table-rebuild':caption='إعادة بناء جداول الورق في Word، مش تحويل مطابق. الصيغ مكتوبة كنص مش شغالة، والرسومات والأشكال مش منتقلين. حتى٨أعمدة عشان يفضل مقروء.'
  elif mode=='styled-text-rebuilt':caption='اتعاد تنسيق النص والعناوين عشان يبقى قابل للتعديل. مش نسخة مطابقة من توزيع PDF، والصور والروابط ممكن ما تنتقلش.'
  elif ext=='pdf':caption='تحويل قابل للتعديل مع الحفاظ على التنسيق قدر الإمكان. راجع الجداول والخطوط قبل الاعتماد.'
  elif target=='csv':caption='CSV فيه أول ورقة فقط، من غير تنسيق أو صيغ Excel.'
  info={'chat_id':chat}
  if caption:info['caption']=caption
  result=bot.tg('sendDocument',data=info,files={'document':(stem+'.'+target,io.BytesIO(output),MIME[target])})
  if not result.get('ok'):raise ValueError('delivery')
  print('document_conversion_sent',ext,target,mode,flush=True)
 except Exception:
  print('document_conversion_failed',ext,target,flush=True)
  if (ext,target)in {('pdf','xlsx'),('docx','xlsx'),('xlsx','docx')}:bot.send(chat,'مقدرتش أستخرج الجداول دي. لازم جداول نصية واضحة، مش صورة ممسوحة. الحد٢٠جدول و١٠آلاف خلية و٢٠٠٠صف، وWord حتى٨أعمدة عشان يفضل مقروء. جرّب جدول أصغر أو الملف الأصلي.')
  else:bot.send(chat,'مقدرتش أحول الملف ده. PDF لازم يكون نصي ومش محمي، لحد٢٠صفحة و١٠ميجابايت. الجداول العربية المعقدة أو الصور الممسوحة محتاجة ملف أصلي. وباقي أوفيس لحد١٥ميجابايت.')
 finally:LOCK.release()
SCAN_NOTE='الملف حافظ شكل الصفحة كصورة داخل Word، مش نص أو جدول قابل للتعديل بالكامل. أي تفريغ نصي مضاف غير متحقق منه ولازم تراجعه؛ الكلمات غير الواضحة معلّمة. الشكل والخط محفوظين كصورة، والخط في النص القابل للتعديل تقريبي مش مطابق. التحويل القابل للتعديل بنفس التخطيط لسه غير مكتمل.'
def convert_scan(msg,media):
 chat=msg['chat']['id'];item=max(media['photo'],key=lambda x:x.get('file_size',0))if media.get('photo')else media['document'];ext='scan'if item.get('file_name','').lower().endswith('.pdf')else'image'
 if item.get('file_size',0)>8*1024*1024:bot.send(chat,'الصورة أو المسح لحد٨ميجابايت وخمس صفحات PDF.');return
 if not LOCK.acquire(False):bot.send(chat,'في ملف بيتحول. جرّب بعد دقيقة.');return
 try:
  bot.send(chat,'جاري التحويل');meta=bot.tg('getFile',data={'file_id':item['file_id']});r=requests.get('https://api.telegram.org/file/bot'+bot.TELEGRAM_TOKEN+'/'+meta['result']['file_path'],timeout=40);r.raise_for_status();data=r.content
  if len(data)>8*1024*1024:raise ValueError('size')
  url=os.environ['CONVERTER_URL'].rstrip('/');requests.get(url+'/health',timeout=95).raise_for_status();r=requests.post(url+'/convert',data=data,headers={'Authorization':'Bearer '+os.environ['CONVERTER_KEY'],'X-Format':ext,'X-Target':'docx'},timeout=95);r.raise_for_status()
  if len(r.content)>MAX_BYTES:raise ValueError('output')
  with zipfile.ZipFile(io.BytesIO(r.content))as z:
   if 'word/document.xml'not in z.namelist():raise ValueError('docx')
  result=bot.tg('sendDocument',data={'chat_id':chat,'caption':SCAN_NOTE},files={'document':('scan-preserved.docx',io.BytesIO(r.content),MIME['docx'])})
  if not result.get('ok'):raise ValueError('send')
 except Exception:bot.send(chat,'مقدرتش أحفظ المسح ده بشكل سليم. ابعت صورة أوضح أو PDF لحد٥صفحات و٨ميجابايت. مش هبعت نص مشوّه.')
 finally:LOCK.release()
def handle(msg):
 if msg.get('chat',{}).get('type')!='private':return ORIGINAL(msg)
 text=msg.get('caption')or msg.get('text','');media=msg if msg.get('photo')or msg.get('document',{}).get('mime_type','').startswith('image/')else msg.get('reply_to_message',{})
 if target_of(text)=='docx'and(media.get('photo')or media.get('document',{}).get('mime_type','').startswith('image/')):return convert_scan(msg,media)
 if target_of(text)=='docx'and re.search(r'مسح|ممسوح|سكان|scan',text,re.I)and(msg.get('document')or msg.get('reply_to_message',{}).get('document')):return convert_scan(msg,msg if msg.get('document')else msg['reply_to_message'])
 current=msg.get('document');reply=msg.get('reply_to_message',{}).get('document');text=msg.get('caption')or msg.get('text','')
 document=current or(reply if re.search(r'حول|حوّل|convert|تحويل',text,re.I)else None)
 if document:
  ext=document.get('file_name','').rsplit('.',1)[-1].lower();target=target_of(text)
  if ext in FORMATS or(ext in ('pdf','docx','xlsx','pptx')and(target or re.search(r'حول|convert|تحويل',text,re.I))):
   return convert_document({**msg,'document':document},target)
 return ORIGINAL(msg)
bot.handle=handle
if __name__=='__main__':
 finish_bot.EXTRA.init_reminders();threading.Thread(target=finish_bot.EXTRA.reminders_loop,daemon=True).start();print('document_conversion_ready',flush=True);bot.main()
