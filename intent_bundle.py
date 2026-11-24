import datetime as dt
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import requests

DAYS=['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']


def local_clock(place=''):
    place=place.strip(' ؟?،.').strip()
    # Country mappings below are only single-zone defaults, never multi-zone countries.
    aliases={'السعودية':'Riyadh','السعوديه':'Riyadh','مصر':'Cairo','القاهرة':'Cairo','القاهره':'Cairo',
             'الجيزة':'Giza','المنوفية':'Shibin El Kom','القليوبية':'Banha','الرياض':'Riyadh','جدة':'Jeddah','جده':'Jeddah','مكة':'Mecca','مكه':'Mecca',
             'الإسكندرية':'Alexandria','الاسكندرية':'Alexandria','اسكندرية':'Alexandria'}
    if not place:
        zone='Africa/Cairo';label='القاهرة'
    elif '/' in place:
        try:ZoneInfo(place)
        except ZoneInfoNotFoundError:raise ValueError('اسم المنطقة الزمنية مش معروف. مثال: /time Asia/Riyadh أو /time London')
        zone=place;label=place
    else:
        if place in ('أمريكا','امريكا','الولايات المتحدة','روسيا','كندا','استراليا','أستراليا','البرازيل','المكسيك','الكونغو','إندونيسيا','اندونيسيا','البرتغال','إسبانيا','اسبانيا'):
            return 'البلد دي فيها أكتر من توقيت. اكتب المدينة أو الإقليم، مثلاً /time New York'
        search=aliases.get(place,place)
        r=requests.get('https://geocoding-api.open-meteo.com/v1/search',params={'name':search,'count':5,'language':'ar','format':'json'},timeout=12)
        r.raise_for_status();rows=r.json().get('results',[])
        if place in ('مصر','القاهرة','القاهره','الإسكندرية','الاسكندرية','اسكندرية','الجيزة','المنوفية','القليوبية'):rows=[x for x in rows if x.get('country_code')=='EG']
        if place in ('السعودية','السعوديه','الرياض','جدة','جده','مكة','مكه'):rows=[x for x in rows if x.get('country_code')=='SA']
        if not rows:return 'مقدرتش أحدد المكان. ابعت اسم المدينة بالإنجليزي أو المنطقة الزمنية، مثلاً /time Asia/Riyadh'
        zones={x.get('timezone') for x in rows}
        # Different cities with the same timezone yield the same time, so are safe for a time-only question.
        if len(zones)>1:
            options='\n'.join(x.get('name','')+'، '+x.get('admin1','')+'، '+x.get('country','')+' ('+x.get('timezone','')+')' for x in rows)
            return 'الاسم طلع بأكتر من توقيت. حدّد المدينة والبلد أو استخدم كود المنطقة:\n'+options
        row=rows[0];zone=row.get('timezone');label=row['name']+'، '+row.get('country','')
        if not zone:raise ValueError('مفيش منطقة زمنية مؤكدة للمكان ده.')
    now=dt.datetime.now(ZoneInfo(zone));suffix='صباحاً' if now.hour<12 else 'مساءً'
    return f'{label}\n{DAYS[now.weekday()]} {now:%Y-%m-%d}\n{now:%I:%M:%S} {suffix}\nالمنطقة الزمنية: {zone}\nمحسوب من ساعة الخادم وقواعد التوقيت الصيفي، مش تخمين من نموذج.'

import datetime as dt
import re
import threading
import bot
import office_bot

ORIGINAL=bot.handle
LAST_PHOTO={}
EDIT=re.compile(r'(?:خلي|خلّي|غير|غيّر|بدل|بدّل|عدل|عدّل|لبس|يلبس|البس|شيل|امسح|ضيف|اضف|أضف|حط|بدلة|بدله|خلفية|خلفيه|رتوش|فوتوشوب|photoshop|edit|remove|replace|wear)',re.I)
OCR=re.compile(r'(?:استخرج|اقرا|اقرأ|حول.*نص|حوّل.*نص|النص|الكلام المكتوب|ocr|extract.*text)',re.I)


def handle(msg):
    text=(msg.get('text') or '').strip()
    chat=msg['chat']['id']
    caption=(msg.get('caption') or '').strip()
    doc=msg.get('document',{})
    image=bool(msg.get('photo') or doc.get('mime_type','').startswith('image/'))
    reply=msg.get('reply_to_message',{})
    replied_image=bool(reply.get('photo') or reply.get('document',{}).get('mime_type','').startswith('image/'))
    recent=LAST_PHOTO.get(chat,0)
    now=__import__('time').monotonic()
    if image:LAST_PHOTO[chat]=now
    request=caption if image else text
    if not replied_image and not image and now-recent<600 and EDIT.search(text) and re.search(r'(?:الشخص|الصورة|الصوره|لبس|يلبس|خلفية|خلفيه|بدلة|بدله)',text):replied_image=True
    if (image or replied_image) and EDIT.search(request) and not OCR.search(request):
        bot.send(chat,'فهمت إنك عايز تعدّل الصورة نفسها، مش تستخرج كلامها. تعديل الصور الموجودة مش متاح عندي دلوقتي، فمش هحوّل طلبك لنص ولا أقول إني عدلتها. أقدر أولّد صورة جديدة من وصف تكتبهولي، لكن مش هضمن نفس الشخص أو ملامحه. لو عايز صورة جديدة اكتب /image وبعده الوصف.');return
    if image and caption and not OCR.search(caption):
        bot.send(chat,'الصورة دي عايز تستخرج النص اللي فيها؟ اكتب في الكابشن اقرأ النص. ولو قصدك تعديل الصورة نفسها، التعديل مش متاح حالياً، لكن أقدر أولّد صورة جديدة من وصف.');return
    is_time=text.startswith('/time') or re.search(r'(?:بتوقيت|توقيت)\s+\S+',text) or re.search(r'(?:الساعة|الساعه|التوقيت|توقيت).*(?:كام|إيه|ايه|الآن|دلوقتي)|(?:كام|ايه|إيه).*(?:الساعة|الساعه)',text)
    if is_time:
        place=''
        if text.startswith('/time'):place=text[5:].strip()
        else:
            match=re.search(r'(?:بتوقيت|توقيت|في|فى)\s+(.+?)(?:\s+(?:الساعة|الساعه|كام|دلوقتي|الآن).*)?[؟?]?$' ,text)
            if match:place=match.group(1).strip(' ؟?')
        try:bot.send(chat,local_clock(place))
        except Exception:bot.send(chat,'مقدرتش أتحقق من توقيت المكان. ابعت اسم المدينة أو كود المنطقة الزمنية، مثلاً /time Asia/Riyadh. مش هخمن.');
        return
    return ORIGINAL(msg)

bot.handle=handle
if __name__=='__main__':
    office_bot.generate_bot.daily_bot.extra_bot.init_reminders()
    threading.Thread(target=office_bot.generate_bot.daily_bot.extra_bot.reminders_loop,daemon=True).start()
    print('photo_intent_world_time_ready',flush=True)
    bot.main()
