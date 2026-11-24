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


def price_request(text):
    norm=re.sub(r'[ًٌٍَُِّْـ]','',text)
    asset=bool(re.search(r'ذهب|دهب|دولار|gold|dollar|usd',norm,re.I))
    question=bool(re.search(r'بكام|بكم|كام|سعر|اسعار|أسعار|price|rate|كم سعر',norm,re.I))
    return text in ('/prices','/gold','/usd') or (asset and question)


def news_send(chat,text):
    # Use text-link entities, not raw encoded Google News story URLs.
    entities=[];parts=[];pos=0
    for m in re.finditer(r'https://news\.google\.com/[^\s]+',text):
        parts.append(text[pos:m.start()]);parts.append('اقرأ الخبر')
        prefix=''.join(parts[:-1]);entities.append({'type':'text_link','offset':len(prefix.encode('utf-16-le'))//2,'length':len('اقرأ الخبر'),'url':m.group()})
        pos=m.end()
    if not entities:return bot.send(chat,text)
    parts.append(text[pos:]);out=''.join(parts)
    if len(out)>3900:out=out[:3900];entities=[e for e in entities if e['offset']+e['length']<=len(out.encode('utf-16-le'))//2]
    result=bot.tg('sendMessage',data={'chat_id':chat,'text':out,'entities':__import__('json').dumps(entities),'disable_web_page_preview':True})
    if not result.get('ok'):bot.send(chat,re.sub(r'https://news\.google\.com/[^\s]+','المصدر: Google News',text))



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


def adhkar(evening=False):
    lead='مختارات من أذكار المساء، عند الطلب، مش قائمة كاملة.' if evening else 'مختارات من أذكار الصباح، عند الطلب، مش قائمة كاملة.'
    dua=('اللهم بك أمسينا وبك أصبحنا وبك نحيا وبك نموت وإليك المصير' if evening else
         'اللهم بك أصبحنا وبك أمسينا وبك نحيا وبك نموت وإليك النشور')
    return (lead+'\n\n'+dua+'\nالمصدر: https://sunnah.com/hisn:78\n\nسبحان الله وبحمده، مائة مرة.\nالمصدر: https://sunnah.com/riyadussalihin:1451\n\nمفيش إرسال تلقائي مفعّل.')


def handle(msg):
    text=(msg.get('text') or '').strip();chat=msg['chat']['id']
    if msg['chat'].get('type')=='private' and price_request(text):
        started=time.monotonic()
        try:bot.send(chat,prices())
        except Exception:bot.send(chat,'مصدر الأسعار مش متاح دلوقتي. مش هخمن رقم. جرّب تاني بعد شوية.')
        print('prices_seconds',round(time.monotonic()-started,2),flush=True)
        return
    if text.startswith('/news') or re.search(r'أخبار|اخبار|الاخبار|الأخبار',text):
        topic=re.sub(r'^/news\s*','',text).strip() if text.startswith('/news') else text
        topic=re.sub(r'(?:ممكن|هات|عايز|عاوز|احدث|أحدث|اخر|آخر|النهارده|النهاردة|اليوم|أخبار|اخبار|الأخبار|الاخبار)',' ',topic)
        topic=re.sub(r'\s+',' ',topic).strip(' ؟?،.')
        news_send(chat,headlines(topic))
        return
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
