import os
import threading
import bot

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
            return ORIGINAL_ANSWER(chat_id, text)
        finally:
            bot.SYSTEM = BASE_SYSTEM


def owner_handle(msg):
    private_owner = (OWNER and msg['chat']['id'] == OWNER and
                     msg.get('from', {}).get('id') == OWNER and
                     msg['chat'].get('type') == 'private')
    if private_owner and (msg.get('text') or '').strip().startswith('/start'):
        bot.send(OWNER, owner_answer(OWNER, WELCOME))
        return
    return ORIGINAL_HANDLE(msg)


bot.answer = owner_answer
bot.handle = owner_handle
if __name__ == '__main__':
    bot.main()
