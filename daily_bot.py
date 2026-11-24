import datetime as dt
import re
import threading
import bot
import extra_bot
from daily_tools import prices, prayers, calculate, convert

ORIGINAL = bot.handle
TZ = extra_bot.TZ


def handle(msg):
    text=(msg.get('text') or '').strip()
    chat=msg['chat']['id']
    if msg['chat'].get('type')!='private':return ORIGINAL(msg)
    try:
        if text=='/time' or re.search(r'(?:النهارده|النهاردة|انهارده|اليوم|الساعة|الساعه|تاريخ).*(?:ايه|إيه|كام)|^(?:النهارده|النهاردة|الساعة|الساعه|التاريخ)$',text):
            now=dt.datetime.now(TZ)
            days=['الاثنين','الثلاثاء','الأربعاء','الخميس','الجمعة','السبت','الأحد']
            suffix='صباحاً' if now.hour<12 else 'مساءً'
            bot.send(chat,f'{days[now.weekday()]} {now:%Y-%m-%d}\nالوقت دلوقتي {now:%I:%M:%S} {suffix} بتوقيت القاهرة.')
            return
        if text in ('/prices','/gold','/usd') or re.search(r'(?:سعر|أسعار|اسعار).*(?:الذهب|الدهب|الدولار)',text):
            bot.send(chat,prices());return
        if text=='/prayer' or re.search(r'(?:مواقيت|مواعيد).*(?:الصلاة|الصلاه)',text):
            if chat!=extra_bot.memory_bot.OWNER and text!='/prayer':
                bot.send(chat,'الأمر /prayer يعرض مواعيد القاهرة فقط حالياً.');return
            bot.send(chat,prayers());return
        if text.startswith('/calc '):
            bot.send(chat,'الناتج: '+str(calculate(text[6:].strip())));return
        if text.startswith('/convert '):
            parts=text.split()
            if len(parts)!=4:raise ValueError('مثال: /convert 10 km m أو /convert 32 f c')
            value=float(parts[1])
            if not __import__('math').isfinite(value) or abs(value)>1e15:raise ValueError('استخدم رقم محدود.')
            result=convert(value,parts[2].lower(),parts[3].lower())
            bot.send(chat,f'{value:g} {parts[2]} = {result:g} {parts[3]}');return
        for command,prompt in (
            ('/recipe','اقترح وصفة بالمكونات التالية. اسأل عن الحساسية لو مش معروفة، واذكر وقت وخطوات وتسوية آمنة. لا تفترض المكونات الناقصة موجودة: '),
            ('/letter','اكتب مسودة رسالة رسمية حسب الطلب. لا تخترع أسماء أو تواريخ أو وقائع ناقصة، استخدم خانات واضحة عند الحاجة. لا ترسلها لأحد: '),
            ('/quiz','العب مع المستخدم مسابقة في الموضوع التالي، سؤال واحد في كل مرة، انتظر الإجابة ولا تكشف الحل مباشرة: ')):
            if text==command or text.startswith(command+' '):
                detail=text[len(command):].strip()
                if not detail:bot.send(chat,'اكتب '+command+' وبعده '+('المكونات اللي عندك' if command=='/recipe' else 'طلبك أو الموضوع'))
                else:bot.send(chat,bot.answer(chat,prompt+detail))
                return
        if text in ('/commands','/features'):
            ORIGINAL(msg)
            bot.send(chat,'إضافات:\n/prices الدولار وذهب ٢١ بأسعار استرشادية من المصدر\n/prayer مواقيت القاهرة\n/calc (12+3)*4\n/convert 10 km m\n/recipe المكونات\n/letter المطلوب\n/quiz الموضوع\nوقت الساعة بنظام ١٢ ساعة. إدخال موعد التذكير ما زال بنظام ٢٤ ساعة في /remind لتجنب اللبس.');return
    except Exception as e:
        if isinstance(e,ValueError):bot.send(chat,str(e))
        else:bot.send(chat,'المصدر مش متاح دلوقتي، مش هخمن السعر أو الميعاد. جرب تاني بعد شوية.')
        return
    return ORIGINAL(msg)

bot.handle=handle
if __name__=='__main__':
    extra_bot.init_reminders()
    threading.Thread(target=extra_bot.reminders_loop,daemon=True).start()
    print('daily_tools_ready',flush=True)
    bot.main()
