import io
import os
import re
import subprocess
import tempfile
import threading
import requests
import bot
import conversion_bot

ORIGINAL=bot.handle
LOCK=threading.BoundedSemaphore(2)

def voice_request(text):
    if text.startswith('/voice'):
        return text[6:].strip() or 'سلم عليا بجملة قصيرة'
    m=re.match(r'^(?:رد عليا بصوتك|رد علي بصوتك|جاوبني بصوتك|رد بصوت|قول بصوتك|اقرأ بصوتك)\s*[:، ]*(.*)',text)
    return (m.group(1).strip() or 'سلم عليا بجملة قصيرة') if m else None


def say(chat,text):
    import imageio_ffmpeg
    key=os.environ.get('GROQ_API_KEY','')
    if not key:raise ValueError('missing key')
    r=requests.post('https://api.groq.com/openai/v1/audio/speech',headers={'Authorization':'Bearer '+key},json={'model':'canopylabs/orpheus-arabic-saudi','voice':'fahad','input':text,'response_format':'wav'},timeout=40)
    r.raise_for_status()
    if not r.content.startswith(b'RIFF') or len(r.content)>12*1024*1024:raise ValueError('invalid audio')
    with tempfile.TemporaryDirectory(prefix='voice-') as folder:
        wav=os.path.join(folder,'voice.wav');ogg=os.path.join(folder,'voice.ogg')
        with open(wav,'wb') as f:f.write(r.content)
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',wav,'-c:a','libopus','-b:a','32k',ogg],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=True)
        with open(ogg,'rb') as f:result=bot.tg('sendVoice',data={'chat_id':chat},files={'voice':('voice.ogg',f,'audio/ogg')})
        if not result.get('ok'):raise ValueError('delivery')


def handle(msg):
    text=(msg.get('text') or '').strip();prompt=voice_request(text)
    if prompt is None or msg['chat'].get('type')!='private':return ORIGINAL(msg)
    chat=msg['chat']['id']
    if not LOCK.acquire(False):bot.send(chat,'الصوت مشغول دلوقتي. جرّب بعد شوية.');return
    answer=''
    try:
        answer=bot.answer(chat,'جاوب بالمصري في جمل قصيرة مناسبة للسمع، من غير ماركداون، بحد أقصى ٥٠٠ حرف. لو السؤال محتاج بيانات حالية مش عندك قول ده بوضوح ومتخمنش. السؤال: '+prompt)
        if not answer or len(answer)>1200:raise ValueError('length')
        say(chat,answer)
        print('voice_reply_sent',flush=True)
    except Exception:
        print('voice_reply_failed',flush=True)
        bot.send(chat,'الصوت مش متاح دلوقتي.'+('\n'+answer if answer else ' جرّب تاني بعد شوية.'))
    finally:LOCK.release()

bot.handle=handle
if __name__=='__main__':
    conversion_bot.finish_bot.EXTRA.init_reminders()
    threading.Thread(target=conversion_bot.finish_bot.EXTRA.reminders_loop,daemon=True).start()
    print('voice_conversion_ready',flush=True)
    bot.main()
