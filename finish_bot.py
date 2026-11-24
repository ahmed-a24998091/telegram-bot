import datetime as dt
import re
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
import requests
import urllib.parse
import bot
import intent_bundle
"""Small conservative rules for news intent and numbered task boundaries."""
import re
NEWS=re.compile(r'(?:الأخبار|الاخبار|أخبار|اخبار|\bnews\b)',re.I)

def strip_label(text):
    return re.sub(r'^\s*(?:سؤال\s+(?:ذكاء|فهم)|المهمة\s+[\w]+)\s*[:：]\s*','',text).strip().strip('"“”«»')

def split_tasks(text):
    parts=re.split(r'(?:^|\n)\s*[0-9٠-٩]+\s*[.)،:-]\s*',text)
    if len(parts)<3:return [text]
    return [strip_label(p) for p in parts[1:] if p.strip()]

def news_topic(text):
    text=strip_label(text).strip()
    if text.startswith('/news') and (len(text)==5 or text[5].isspace()):return text[5:].strip()
    # Mentions, complaints, negation and quoted examples are not news requests.
    if re.search(r'مش عايز|مش عاوز|لا (?:تبحث|تجيب|اريد|أريد)|ليه|لماذا|قلت|قال|رد[هك]?|اختبار|مثال|معنى|كلمة',text,re.I):return None
    pattern=r'^(?:(?:ممكن|لو سمحت|من فضلك)\s+)?(?:(?:ابعت(?:لي|لى)?|هات(?:لي|لى)?|اعرض(?:لي|لى)?|عايز|عاوز|أريد|اريد|أعطني|اعطني|جيب(?:لي)?|قول(?:لي)?|ما هي|ايه|إيه)\s+)?(?:(?:آخر|اخر|أحدث|احدث)\s+)?(?:الأخبار|الاخبار|أخبار|اخبار|news)\b\s*(.*)$'
    m=re.match(pattern,text,re.I)
    if not m:return None
    topic=m.group(1).strip(' ؟?،.');topic=re.sub(r'^(?:عن|في|فى)\s+','',topic)
    topic=re.sub(r'\s*(?:النهارده|النهاردة|اليوم|دلوقتي)\s*$','',topic).strip()
    if len(topic)>160:return None
    return topic

def chain_parts(text):
    return re.split(r'\s*(?:وبعدين|و\s*بعدين|ثم|وبعدها|وبعد كده|\bthen\b)\s*',text,maxsplit=1,flags=re.I)


ORIGINAL=bot.handle
EXTRA=intent_bundle.office_bot.generate_bot.daily_bot.extra_bot
DAILY=intent_bundle.office_bot.generate_bot.daily_bot
TZ=EXTRA.TZ
CACHE={}
BASE_SEND=bot.send
OLD_GEMINI=bot.ask_gemini

def fast_chat(msgs):
    # Preserve all existing context and fallbacks, but avoid slow first-provider retries.
    if bot.GROQ_KEY:
        try:return bot.ask_groq(msgs)
        except Exception:pass
    return OLD_GEMINI(msgs)

bot.ask_gemini=fast_chat


def exact_calculate(expr):
    import ast
    from fractions import Fraction
    expr=expr.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩٫×÷−','0123456789.* /-'.replace(' ',''))).replace('^','**').strip()
    if not expr or len(expr)>180:raise ValueError('اكتب عملية حسابية واضحة، مثلاً احسب 12.5 * 4')
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):
            raw=ast.get_source_segment(expr,n)
            if not re.fullmatch(r'\d+(?:\.\d+)?',raw or ''):raise ValueError('استخدم أرقام عشرية عادية.')
            value=Fraction(raw)
        elif isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            value=visit(n.operand)*(-1 if isinstance(n.op,ast.USub) else 1)
        elif isinstance(n,ast.BinOp):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Add):value=a+b
            elif isinstance(n.op,ast.Sub):value=a-b
            elif isinstance(n.op,ast.Mult):value=a*b
            elif isinstance(n.op,ast.Div):value=a/b
            elif isinstance(n.op,ast.Mod):value=a%b
            elif isinstance(n.op,ast.Pow) and b.denominator==1 and abs(b)<=10:value=a**int(b)
            else:raise ValueError('العملية دي مش مدعومة. استخدم + - * / ** % وأقواس.')
        else:raise ValueError('اكتب العملية بالأرقام والعلامات، مثلاً احسب (12+3)*4')
        if abs(value)>10**30 or value.denominator>10**30:raise ValueError('النتيجة أكبر من الحد الآمن للحاسبة.')
        return value
    try:value=visit(ast.parse(expr,mode='eval').body)
    except ZeroDivisionError:raise ValueError('القسمة على صفر غير معرفة.')
    except (SyntaxError,TypeError):raise ValueError('اكتب عملية صحيحة، مثلاً احسب 12 + 3')
    d=value.denominator
    for p in (2,5):
        while d%p==0:d//=p
    if d!=1:return str(value.numerator)+'/'+str(value.denominator)+' (كسر دقيق، تمثيله العشري دوري)'
    from decimal import Decimal,localcontext
    with localcontext() as c:
        c.prec=100
        out=format(Decimal(value.numerator)/Decimal(value.denominator),'f')
    return out.rstrip('0').rstrip('.') if '.' in out else out


def price_request(text):
    norm=re.sub(r'[ًٌٍَُِّْـ]','',text)
    asset=bool(re.search(r'ذهب|دهب|دولار|gold|dollar|usd',norm,re.I))
    question=bool(re.search(r'بكام|بكم|كام|سعر|اسعار|أسعار|price|rate|كم سعر',norm,re.I))
    return text in ('/prices','/gold','/usd') or (asset and question)


def news_send(chat,text):
    # Each story is kept intact and uses native Telegram links, including non-Google sources.
    for block in re.split(r'\n\n',text):
        parts=[];entities=[];pos=0
        for m in re.finditer(r'https?://[^\s]+',block):
            parts.append(block[pos:m.start()]);prefix=''.join(parts)
            entities.append({'type':'text_link','offset':len(prefix.encode('utf-16-le'))//2,'length':len('اقرأ الخبر'),'url':m.group()})
            parts.append('اقرأ الخبر');pos=m.end()
        parts.append(block[pos:]);out=''.join(parts)
        if not entities:bot.send(chat,out);continue
        result=bot.tg('sendMessage',data={'chat_id':chat,'text':out,'entities':__import__('json').dumps(entities),'disable_web_page_preview':True})
        if not result.get('ok'):bot.send(chat,block)


def send_chunks(chat,text):
    chunk=''
    for line in str(text).splitlines(keepends=True):
        if len(chunk)+len(line)>3800 and chunk:
            BASE_SEND(chat,chunk.rstrip());chunk=''
        while len(line)>3800:
            BASE_SEND(chat,line[:3800]);line=line[3800:]
        chunk+=line
    if chunk:BASE_SEND(chat,chunk.rstrip())


bot.send=send_chunks


def clock12(value):
    t=dt.datetime.strptime(value[:5],'%H:%M')
    return t.strftime('%I:%M')+(' صباحاً' if t.hour<12 else ' مساءً')


OLD_PRAYERS=DAILY.prayers
OLD_PRICES=DAILY.prices


def prayers():
    return re.sub(r'(?<=: )\d{2}:\d{2}',lambda m:clock12(m.group()),OLD_PRAYERS())


def prices():
    return re.sub(r'(?<=\d{4}-\d{2}-\d{2} )\d{2}:\d{2}(?::\d{2})?',lambda m:clock12(m.group()),OLD_PRICES())


def headlines(topic=""):
    now=dt.datetime.now(TZ)
    cache_key='news:'+topic
    if cache_key in CACHE and time.monotonic()-CACHE[cache_key][0]<300:return CACHE[cache_key][1]
    categories=[('WORLD','العالم'),('BUSINESS','اقتصاد'),('TECHNOLOGY','تكنولوجيا'),('SCIENCE','علوم'),('HEALTH','صحة'),('SPORTS','رياضة'),('ENTERTAINMENT','ثقافة وفن')]
    if topic:categories=[('SEARCH',topic)]
    def read(cat):
        code,label=cat
        try:
            url='https://news.google.com/rss/headlines/section/topic/'+code+'?hl=ar&gl=EG&ceid=EG:ar'
            if topic:url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':topic+' when:1d','hl':'ar','gl':'EG','ceid':'EG:ar'})
            r=requests.get(url,timeout=7);r.raise_for_status();rows=[]
            for item in ET.fromstring(r.content).findall('./channel/item'):
                pub=parsedate_to_datetime(item.findtext('pubDate')).astimezone(TZ)
                if pub.date()==now.date() and pub<=now:rows.append((pub,item.findtext('title') or '',item.findtext('link') or ''))
            rows.sort(reverse=True)
            if rows:
                pub,title,url=rows[0]
                return label+' | '+clock12(pub.strftime('%H:%M'))+'\n'+title+'\n'+url
        except Exception:pass
        return label+': لا يوجد عنوان بتاريخ اليوم قدرت أتحقق منه دلوقتي.'
    with ThreadPoolExecutor(max_workers=4) as pool:parts=list(pool.map(read,categories))
    out=('عناوين عن '+topic if topic else 'عناوين عالمية متنوعة')+' من Google News عند الطلب، مش قراءة للمقالات كاملة.\nتم التحقق: '+now.strftime('%Y-%m-%d')+' '+clock12(now.strftime('%H:%M'))+' القاهرة. مش بث لحظي.\n\n'+'\n\n'.join(parts)
    CACHE[cache_key]=(time.monotonic(),out)
    return out


DAILY.prayers=prayers
DAILY.prices=prices
EXTRA.fresh_headlines=headlines


def summary_news(topic=''):
    from bs4 import BeautifulSoup
    now=dt.datetime.now(TZ);key='summaries:'+topic
    if key in CACHE and time.monotonic()-CACHE[key][0]<300:return CACHE[key][1]
    feeds=[('متنوع','https://www.aljazeera.net/rss'),('متنوع','https://feeds.bbci.co.uk/arabic/rss.xml')]
    feeds += [(label,'https://arabic.rt.com/rss/'+slug+'/') for slug,label in [('world','العالم'),('business','اقتصاد'),('technology','علوم وتكنولوجيا'),('health','صحة'),('sport','رياضة'),('culture','ثقافة وفن')]]
    norm=lambda s:re.sub(r'[أإآ]','ا',re.sub(r'[ًٌٍَُِّْـ]','',s)).lower()
    query=norm(topic);terms=[w for w in re.findall(r'\w+',query) if w not in {'عن','في','اهم','اخر','اخبار','النهارده','العالم','العالمية','اليوم'}]
    if re.search(r'ذكاء.*اصطناعي|artificial intelligence|\bai\b',query):terms=['ذكاء','اصطناعي']
    def read(feed):
        label,url=feed;rows=[]
        try:
            r=requests.get(url,timeout=8);r.raise_for_status()
            if len(r.content)>2_000_000:return []
            for item in ET.fromstring(r.content).findall('./channel/item')[:60]:
                try:pub=parsedate_to_datetime(item.findtext('pubDate')).astimezone(TZ)
                except Exception:continue
                if pub.date()!=now.date() or pub>now:continue
                title=BeautifulSoup(item.findtext('title',''),'html.parser').get_text(' ',strip=True)
                desc=BeautifulSoup(item.findtext('description',''),'html.parser').get_text(' ',strip=True)
                link=item.findtext('link','').strip()
                if len(desc)<60 or not link.startswith('https://'):continue
                hay=norm(title+' '+desc+' '+label)
                if terms and not all(t in hay for t in terms):continue
                desc=re.sub(r'\s+',' ',desc)
                if len(desc)>650:desc=desc[:650].rsplit(' ',1)[0]+'…'
                rows.append((pub,title,desc,link,label))
        except Exception:pass
        return rows
    with ThreadPoolExecutor(max_workers=4) as pool:groups=list(pool.map(read,feeds))
    selected=[];seen=set()
    if terms:
        candidates=sorted([x for group in groups for x in group],reverse=True)
    else:
        # One from each field before extra general headlines.
        candidates=[]
        for group in groups[2:]+groups[:2]:
            if group:candidates.append(sorted(group,reverse=True)[0])
    for row in candidates:
        if row[1] in seen:continue
        selected.append(row);seen.add(row[1])
        if len(selected)>= (3 if terms else 7):break
    stamp=now.strftime('%Y-%m-%d')+' '+clock12(now.strftime('%H:%M'))+' القاهرة'
    if not selected:return 'مقدرتش أتحقق من أخبار بتاريخ اليوم فيها ملخص نصي عن '+(topic or 'الموضوع')+'. مش هحوّل عناوين بس لملخصات مخمّنة.\nتم التحقق: '+stamp
    out=['أخبار '+(topic if topic else 'متنوعة')+'\nملخصات الناشرين المنشورة في RSS، مش قراءة للمقالات كاملة.\nتم التحقق: '+stamp+'، مش بث لحظي.']
    for pub,title,desc,link,label in selected:out.append(label+' | '+clock12(pub.strftime('%H:%M'))+'\n'+title+'\n'+desc+'\nالمصدر: '+link)
    text='\n\n'.join(out);CACHE[key]=(time.monotonic(),text);return text

headlines=summary_news
EXTRA.fresh_headlines=summary_news

def adhkar(evening=False):
    lead='مختارات من أذكار المساء، عند الطلب، مش قائمة كاملة.' if evening else 'مختارات من أذكار الصباح، عند الطلب، مش قائمة كاملة.'
    dua=('اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير' if evening else
         'اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور')
    return (lead+'\n\n'+dua+'\nالمصدر: https://sunnah.com/hisn:78\n\nسبحان الله وبحمده، مائة مرة.\nالمصدر: https://sunnah.com/riyadussalihin:1451\n\nمفيش إرسال تلقائي مفعّل.')


def handle(msg):
    text=(msg.get('text') or '').strip();chat=msg['chat']['id']
    if text.startswith('/football') or re.search(r'(?:مواعيد|نتايج|نتائج|ماتشات|مباريات).*(?:ماتش|مبار|كوره|كورة|كره|كرة)|^(?:ماتشات|مباريات)(?: النهارده| اليوم)?$',text):
        try:bot.send(chat,football(text))
        except Exception:bot.send(chat,'مصدر الماتشات مش متاح دلوقتي، مش هخمن نتايج.')
        return
    if text.startswith('/egx') or re.search(r'بورصه|بورصة|سهم.*(?:بكام|سعر)|(?:سعر|بكام).*سهم',text):
        bot.send(chat,'أسعار البورصة المصرية مش مفعّلة لسه: مصدر مجاني موثوق بوقت بيانات حديث واضح مش متحقق حالياً. مش هخمن أسعار ولا أعرض أرقام قديمة كسعر دلوقتي. المصدر الرسمي: https://www.egx.com.eg/');return
    calc=re.match(r'^(?:/calc|احسب(?:لي|لى)?|إحسب(?:لي|لى)?|احسبي|calculate)\s*(.*)$',text,re.I)
    if calc:
        try:bot.send(chat,'الناتج الدقيق: '+exact_calculate(calc.group(1)))
        except ValueError as e:bot.send(chat,str(e))
        return
    if msg['chat'].get('type')=='private' and price_request(text):
        started=time.monotonic()
        try:bot.send(chat,prices())
        except Exception:bot.send(chat,'مصدر الأسعار مش متاح دلوقتي. مش هخمن رقم. جرّب تاني بعد شوية.')
        print('prices_seconds',round(time.monotonic()-started,2),flush=True)
        return
    topic=news_topic(text)
    if topic is not None:
        news_send(chat,headlines(topic));return
    if NEWS.search(text):
        # Do not let old nested handlers interpret quoted news or complaints as a search.
        bot.send(chat,bot.answer(chat,text));return
    if text.startswith('/adhkar') or re.search(r'أذكار|اذكار',text):
        if not re.search(r'مساء|صباح|evening|morning',text,re.I):
            bot.send(chat,'عايز أذكار الصباح ولا المساء؟ ابعت /adhkar صباح أو /adhkar مساء.');return
        bot.send(chat,adhkar(bool(re.search(r'مساء|evening',text,re.I))));return
    if text in ('/commands','/features'):
        ORIGINAL(msg)
        bot.send(chat,'/time اسم المدينة أو المنطقة الزمنية\n/adhkar صباح أو /adhkar مساء\n/news عناوين متنوعة: عالم واقتصاد وعلوم وتكنولوجيا وصحة ورياضة وثقافة، عند الطلب فقط.');return
    return ORIGINAL(msg)

bot.handle=handle
if __name__=='__main__':
    EXTRA.init_reminders()
    threading.Thread(target=EXTRA.reminders_loop,daemon=True).start()
    print('news_adhkar_display_ready',flush=True)
    bot.main()

# Source-first religious explanations. Never generate or grade a narration from memory.
def scripture_norm(text):
    import unicodedata
    text=''.join(c for c in unicodedata.normalize('NFKD',text) if not unicodedata.combining(c))
    return text.translate(str.maketrans('أإآىة٠١٢٣٤٥٦٧٨٩','ااايه0123456789')).replace('ـ','').strip()

def scripture_reply(text):
    from bs4 import BeautifulSoup
    def clean(value):return BeautifulSoup(str(value),'html.parser').get_text(' ',strip=True)
    norm=scripture_norm(text)
    is_quran=bool(re.search(r'^/tafsir\b|(?:فسر|تفسير|اشرح|شرح|معني).*(?:ايه|سوره|قران)|^(?:ايه|سوره)\s',norm))
    is_hadith=bool(re.search(r'^/hadith\b|(?:اشرح|شرح|معني|صحه|صحيح|تفسير).*(?:حديث)|hadeethenc\.com',norm))
    if not (is_quran or is_hadith):return None
    try:
        if is_quran:
            match=re.search(r'(?<!\d)(\d{1,3})\s*[:：]\s*(\d{1,3})(?!\d)',norm)
            if match:surah,ayah=map(int,match.groups())
            else:
                r=requests.get('https://api.quran.com/api/v4/chapters',timeout=12);r.raise_for_status()
                chapters=r.json()['chapters'];hits=[c for c in chapters if re.search(r'(?<!\w)'+re.escape(scripture_norm(c['name_arabic']))+r'(?!\w)',norm)]
                nums=re.findall(r'\d+',norm)
                if len(hits)!=1 or len(nums)!=1:return 'ابعت رقم السورة والآية، مثلاً /tafsir 2:255 أو اشرح آية ٢٥٥ من سورة البقرة. هجيب النص والتفسير من المصدر.'
                surah,ayah=int(hits[0]['id']),int(nums[0])
            if not 1<=surah<=114 or not 1<=ayah<=286:return 'رقم السورة أو الآية مش صحيح. مثال: /tafsir 2:255'
            key=str(surah)+':'+str(ayah)
            verse_url='https://api.quran.com/api/v4/quran/verses/uthmani?verse_key='+key
            tafsir_url='https://api.quran.com/api/v4/tafsirs/16/by_ayah/'+key
            r=requests.get(verse_url,timeout=12);r.raise_for_status();verses=r.json().get('verses',[])
            if len(verses)!=1 or verses[0].get('verse_key')!=key:return 'ملقيتش الآية بالرقم ده. راجع رقم السورة والآية.'
            r=requests.get(tafsir_url,timeout=12);r.raise_for_status();tafsir=r.json().get('tafsir',{})
            if key not in tafsir.get('verses',{}) or not tafsir.get('text'):raise ValueError('source mismatch')
            body=clean(tafsir['text'])
            if len(body)>9000:return 'التفسير طويل على الرسالة. تقدر تقرأه من المصدر:\n'+tafsir_url
            return ('الآية '+key+'\n'+verses[0]['text_uthmani']+'\n\nالتفسير الميسر، نص المصدر:\n'+body+'\n\nمصدر النص: '+verse_url+'\nمصدر التفسير: '+tafsir_url)
        match=re.search(r'hadeethenc\.com/(?:ar/)?browse/hadith/(\d+)',text)
        if not match:match=re.match(r'^/hadith\s+(\d+)\s*$',norm)
        if not match:return 'ابعت رابط الحديث من موسوعة الأحاديث النبوية HadeethEnc أو رقمه في الموسوعة، مثلاً /hadith 5913. مش هخمن نص الحديث أو صحته من الذاكرة.'
        hid=match.group(1)
        if len(hid)>9:return 'رقم الحديث مش صحيح.'
        url='https://hadeethenc.com/api/v1/hadeeths/one/?language=ar&id='+hid
        r=requests.get(url,timeout=12)
        if r.status_code==404:return 'ملقيتش الحديث بالرقم ده في الموسوعة. ابعت رابطه أو راجع الرقم.'
        r.raise_for_status();item=r.json()
        if str(item.get('id'))!=hid or not item.get('hadeeth') or not item.get('explanation'):raise ValueError('missing source')
        return ('نص الحديث من الموسوعة:\n'+clean(item['hadeeth'])+'\n\nالتخريج: '+clean(item.get('attribution','غير مذكور'))+'\nالحكم كما ورد بالمصدر: '+clean(item.get('grade','غير مذكور'))+'\n\nشرح الموسوعة:\n'+clean(item['explanation'])+'\n\nالمصدر: '+url)
    except Exception:
        return 'مش قادر أوصل للمصدر الديني دلوقتي. جرّب تاني بعد شوية، مش هخمن نص آية أو حديث أو حكم عليه.'

JOKES=(
'واحد اشترى كرسي للمكتب، أول ما قعد عليه قال: كده أنا أخدت منصب.',
'واحد سمّى الواي فاي عنده «نام بدري». كل ما يفتحه يفتكر النصيحة ويقفل الموبايل.',
'واحد قال للمنبّه: إنت الوحيد اللي بيصرّ يسمعني صوته وأنا مش طايقه.',
'الكمبيوتر راح للدكتور، قاله: كل ما أرتاح شوية حد يعملي Restart.',
'واحد كتب في قائمة المهام: أعمل قائمة مهام. وشطبها وقال: يوم منتج الحمد لله.',
'الكتاب قال للموبايل: الناس بتقلب في صفحاتي. قاله: وأنا بيقلبوا عليّ المواجع في التعليقات.',
'واحد سأل الآلة الحاسبة: إنتي ليه هادية؟ قالتله: بحل مشاكلي بالأرقام.',
'واحد خلّص ترتيب الديسكتوب، حس إنه نقل عفش الشقة كلها.'
)
def joke_reply(text):
    norm=scripture_norm(text)
    if not re.fullmatch(r'/joke|(?:(?:قول|قولي|قوللي|هات|هاتلي|احكي|احكيلي|عايز|عاوز|ابعت|ابعتلي)\s+)?(?:نكته|نكت|قفشه|قفشات)(?:\s+(?:جديده|تضحك|حلوه|مصريه))?[؟?!. ]*',norm):return None
    import secrets
    return secrets.choice(JOKES)


def football(text=''):
    now=dt.datetime.now(TZ)
    leagues={'uefa.champions':('أبطال أوروبا',r'ابطال|أبطال|champions'),'eng.1':('الدوري الإنجليزي',r'انجليزي|إنجليزي|premier'),'esp.1':('الدوري الإسباني',r'اسباني|إسباني|la liga'),'ita.1':('الدوري الإيطالي',r'ايطالي|إيطالي|serie'),'ger.1':('الدوري الألماني',r'الماني|ألماني|bundes'),'fra.1':('الدوري الفرنسي',r'فرنسي|ligue'),'sau.1':('الدوري السعودي',r'سعودي|saudi')}
    if re.search(r'مصري|اهلي|أهلي|زمالك',text,re.I):return 'الدوري المصري مش متاح من مصدر الماتشات الحالي. أقدر أجيب أبطال أوروبا والإنجليزي والإسباني والإيطالي والألماني والفرنسي والسعودي.'
    selected=[k for k,(_,pattern) in leagues.items() if re.search(pattern,text,re.I)]or['uefa.champions','eng.1','esp.1']
    target=now.date()+dt.timedelta(days=1 if re.search(r'بكره|بكرة|غدا|غداً|tomorrow',text,re.I) else -1 if re.search(r'امبارح|أمس|امس|yesterday',text,re.I) else 0)
    key='football:'+str(target)+':'+','.join(selected)
    if key in CACHE and time.monotonic()-CACHE[key][0]<120:return CACHE[key][1]
    rows=['ماتشات '+target.isoformat()+' | توقيت القاهرة','بيانات ESPN عند الطلب، ممكن تتأخر. وقت التحقق '+now.strftime('%Y-%m-%d %H:%M')]
    for league in selected:
        url='https://site.api.espn.com/apis/site/v2/sports/soccer/'+league+'/scoreboard'
        try:
            r=requests.get(url,params={'dates':target.strftime('%Y%m%d'),'limit':100},timeout=10);r.raise_for_status();events=r.json().get('events',[]);found=[]
            for e in events:
                comp=e['competitions'][0];when=dt.datetime.fromisoformat(comp['date'].replace('Z','+00:00')).astimezone(TZ)
                if when.date()!=target:continue
                teams=comp['competitors'];home=next(x for x in teams if x['homeAway']=='home');away=next(x for x in teams if x['homeAway']=='away');status=comp.get('status',e.get('status',{}));state=status.get('type',{}).get('state');detail=status.get('type',{}).get('detail','') if state in ('in','post') else 'لم تبدأ'
                pair=home['team']['displayName']+' × '+away['team']['displayName']
                result=home.get('score','?')+' - '+away.get('score','?') if state in ('in','post') else when.strftime('%H:%M')
                found.append(pair+' | '+result+' | '+detail)
            rows.append(leagues[league][0]+'\n'+('\n'.join(found[:12])or'لا توجد مباريات في التاريخ المطلوب حسب المصدر.'))
        except Exception:rows.append(leagues[league][0]+': المصدر غير متاح دلوقتي.')
    rows.append('المصدر: https://www.espn.com/soccer/scoreboard')
    out='\n\n'.join(rows);CACHE[key]=(time.monotonic(),out);return out
