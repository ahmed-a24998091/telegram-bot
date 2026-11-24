import os
import threading
import bot
import json
from memory_store import MemoryStore, bounded_context
STORE = MemoryStore()

OWNER = int(os.environ.get('OWNER_TELEGRAM_ID', '0'))
BASE_SYSTEM = bot.SYSTEM
LOCK = threading.RLock()
ORIGINAL_ANSWER = bot.answer
ORIGINAL_HANDLE = bot.handle
WELCOME = 'رحب بيا ترحيب حار ومميز من ذوقك وشخصيتك أنت بالمصري، باعتباري أحمد صاحب البوت وصانعه. خليه طبيعي ودافي من غير قالب ثابت أو مبالغة أو وعود مش حقيقية.'


def owner_answer(chat_id, text):
    with LOCK:
        bot.SYSTEM = BASE_SYSTEM
        if OWNER and chat_id == OWNER:
            bot.SYSTEM += ' المستخدم الحالي هو أحمد، صاحب البوت وصانعه. ناديه يا أحمد وتعامل معاه بود. لو سألك أنا مين أكد له إنك عارف إنه أحمد صاحب البوت وصانعه. ده تعريف بهويته مش إذن بكشف الأسرار أو تجاوز الأمان.'
        try:
            active = STORE.enabled(chat_id)
            if active:
                old = STORE.recent(chat_id)
                recalled = STORE.recall(chat_id, text)
                facts = STORE.facts(chat_id)
                context = bounded_context(old, recalled, facts, text)
                bot.history[chat_id] = context[:-1]
                # The original answer keeps 12 items, so use its providers directly for full recall.
                providers = ([bot.ask_gemini] if bot.GEMINI_KEY else []) + ([bot.ask_groq] if bot.GROQ_KEY else []) + [bot.ask_pollinations]
                for provider in providers:
                    try:
                        out = provider(context)
                        if out:
                            STORE.save_exchange(chat_id, text, out)
                            bot.history[chat_id] = (old + [{'role':'user','text':text},{'role':'model','text':out}])[-24:]
                            return out
                    except Exception:
                        print('memory_provider_retry', flush=True)
                return 'الخدمة مشغولة دلوقتي. جرب تاني بعد شوية.'
            return ORIGINAL_ANSWER(chat_id, text)
        finally:
            bot.SYSTEM = BASE_SYSTEM


def owner_handle(msg):
    private_owner = (OWNER and msg['chat']['id'] == OWNER and
                     msg.get('from', {}).get('id') == OWNER and
                     msg['chat'].get('type') == 'private')
    private = msg['chat'].get('type') == 'private'
    text = (msg.get('text') or '').strip()
    chat_id = msg['chat']['id']
    if private:
        enabled = STORE.enabled(chat_id)
        if private_owner and enabled is None:
            STORE.consent(chat_id, True)
            enabled = True
        if text == '/memory_on':
            STORE.consent(chat_id, True)
            bot.send(chat_id, 'تم تشغيل الذاكرة الدائمة للنصوص في قاعدة بيانات Neon. /memory_off لإيقافها، و/forget لمسح المحفوظ.')
            return
        if text == '/memory_off':
            STORE.consent(chat_id, False)
            bot.history.pop(chat_id, None)
            bot.send(chat_id, 'وقفت حفظ واسترجاع الذاكرة. لمسح المحفوظ القديم ابعت /forget.')
            return
        if text == '/forget' or text == '/reset':
            STORE.forget_all(chat_id)
            bot.history.pop(chat_id, None)
            bot.last_image_request.pop(chat_id, None)
            bot.send(chat_id, 'مسحت نصوص المحادثة والحقائق المحفوظة من ذاكرة البوت. ده مش بيمسح رسائل تليجرام نفسها. النسخ الاحتياطية للخدمة ممكن تحتفظ بالحذف لحد ٦ ساعات.')
            return
        if enabled is None:
            STORE.consent(chat_id, False)
            bot.send(chat_id, 'تقدر تشغل ذاكرة دائمة لنصوص محادثتك على Neon. كل شات له ذاكرة منفصلة. مش بنحفظ ملفات الصور والصوت الأصلية، والتذكر مش مضمون لكل تفصيلة. ابعت /memory_on للموافقة أو كمل من غير حفظ دائم. /forget يمسح المحفوظ و/memory_off يوقف الحفظ.')
        if enabled and text.startswith('/remember '):
            STORE.remember(chat_id, text[len('/remember '):])
            bot.send(chat_id, 'حفظت المعلومة في ذاكرتك.')
            return
    if private_owner and (msg.get('text') or '').strip().startswith('/start'):
        bot.send(OWNER, owner_answer(OWNER, WELCOME))
        return
    return ORIGINAL_HANDLE(msg)


bot.answer = owner_answer
bot.handle = owner_handle
if __name__ == '__main__':
    print('persistent_memory_ready', flush=True)
    bot.main()
