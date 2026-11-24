# -*- coding: utf-8 -*-
"""بوت تليجرام: ردود ذكاء اصطناعي + توليد صور، بخدمات مجانية.
- الردود: Pollinations من غير مفتاح. لو وقف، بيحاول Gemini أو Groq لو فيه مفاتيح (اختياري).
- الصور: Pollinations (من غير مفتاح)، ولو فشل بيحاول Hugging Face (اختياري).
"""
import os, io, time, threading, urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GROQ_KEY = os.environ.get("GROQ_API_KEY", "").strip()      # اختياري
HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()           # اختياري
# اسم موديل جيميني. "gemini-flash-latest" بيشاور على أحدث فلاش تلقائيًا
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")

SYSTEM = ("انت مساعد شخصي ذكي اسمه 'مساعد أحمد'، بتتكلم بالعامية المصرية الطبيعية زي صاحب قريب وفاهم: "
          "دافي وخفيف الدم من غير مبالغة، ومختصر ومباشر. ارد بنفس لغة المستخدم؛ ولو كلمك بالمصري رد بالمصري. "
          "افتكر اللي اتقال في المحادثة وكمّل عليه ومتسألش نفس السؤال مرتين. لو الرسالة قصيرة أو مش واضحة (زي 'اه' أو 'اسمها') اربطها بآخر كلام في المحادثة وكمّل عليه، ولو لسه مش واضح اسأل سؤال واحد بس. "
          "لو مش عارف قول بصراحة. لو حد عايز صورة قوله يكتب: ارسم + الوصف. الفيديو مش متاح.")
API = "https://api.telegram.org/bot%s/" % TELEGRAM_TOKEN
history = {}          # chat_id -> قايمة رسايل
last_image = {}       # chat_id -> وقت آخر صورة (عشان نلتزم بحد Pollinations)
image_lock = threading.Lock()

IMAGE_WORDS = ("هات صور", "هات صوره", "عايز صور", "عايز صوره", "اعمل صور", "اعملي صور", "ارسم", "إرسم", "ارسملي", "صورة", "صوره", "صور لي", "اعملي صورة", "ولد صورة", "generate image", "draw ")


def tg(method, **kw):
    r = requests.post(API + method, timeout=70, **kw)
    try:
        return r.json()
    except Exception:
        return {}


def send(chat_id, text):
    for i in range(0, len(text), 4000):
        tg("sendMessage", data={"chat_id": chat_id, "text": text[i:i + 4000]})


# ---------------- الردود ----------------
def ask_gemini(msgs):
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user" if m["role"] == "user" else "model",
                          "parts": [{"text": m["text"]}]} for m in msgs]}
    last = None
    # لو موديل زحمة (503) أو وصل لحده (429) بنجرب اللي بعده
    for model in [GEMINI_MODEL, "gemini-flash-lite-latest", "gemini-3.6-flash"]:
        url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
        try:
            r = requests.post(url, json=body, headers={"x-goog-api-key": GEMINI_KEY}, timeout=12)
        except Exception as e:
            last = e
            print("gemini timeout", model)
            continue
        if r.status_code == 200:
            try:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                last = e
                continue
        last = RuntimeError("gemini %s %s" % (model, r.status_code))
        print(last)
    raise last


def ask_groq(msgs):
    r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                      headers={"Authorization": "Bearer " + GROQ_KEY},
                      json={"model": GROQ_MODEL, "messages": [{"role": "system", "content": SYSTEM}] +
                            [{"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]} for m in msgs]},
                      timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def ask_pollinations(msgs):
    r = requests.post("https://text.pollinations.ai/openai",
                      json={"model": "openai-fast",
                            "messages": [{"role": "system", "content": SYSTEM}] +
                            [{"role": "user" if m["role"] == "user" else "assistant", "content": m["text"]} for m in msgs]},
                      timeout=90)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()


def answer(chat_id, text):
    h = history.setdefault(chat_id, [])
    h.append({"role": "user", "text": text})
    del h[:-12]
    providers = []
    if GROQ_KEY: providers.append(ask_groq)       # لو فيه مفتاح Groq بيبقى الأساسي (أقوى)
    if GEMINI_KEY: providers.append(ask_gemini)
    providers.append(ask_pollinations)            # احتياطي من غير مفتاح
    for p in providers:
        try:
            out = p(h)
            print("reply by", p.__name__, "|", out[:60].replace("\n", " "), flush=True)
            if out:
                h.append({"role": "model", "text": out})
                return out
        except Exception as e:
            print("provider failed:", p.__name__, e)
    h.pop()
    return "معلش، الخدمة مشغولة دلوقتي. جرب تاني بعد دقيقة."


# ---------------- الصور ----------------
def to_english_prompt(text):
    """بنترجم وصف الصورة لإنجليزي (محاولة سريعة واحدة) عشان النتيجة تبقى أحسن."""
    if GEMINI_KEY:
        try:
            r = requests.post("https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-lite-latest:generateContent",
                              headers={"x-goog-api-key": GEMINI_KEY}, timeout=8,
                              json={"contents": [{"role": "user", "parts": [{"text":
                                    "Rewrite as a short vivid English image prompt. Output only the prompt:\n" + text}]}]})
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print("translate failed", e)
    return text


def img_pollinations(prompt):
    # الحد المجاني: طلب واحد كل 45 ثانية تقريبًا من نفس الشبكة
    with image_lock:
        for attempt in range(3):
            wait = 46 - (time.time() - last_image.get("t", 0))
            if wait > 0:
                time.sleep(wait)
            url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + \
                  "?width=768&height=768&seed=%d" % int(time.time())
            r = requests.get(url, timeout=120)
            last_image["t"] = time.time()
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image"):
                return r.content
    raise RuntimeError("pollinations failed")


def img_hf(prompt):
    r = requests.post("https://router.huggingface.co/hf-inference/models/black-forest-labs/FLUX.1-schnell",
                      headers={"Authorization": "Bearer " + HF_TOKEN}, json={"inputs": prompt}, timeout=120)
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image"):
        raise RuntimeError("hf no image")
    return r.content


def make_image(chat_id, text):
    send(chat_id, "ثواني، برسملك الصورة... (ممكن تاخد لحد دقيقة)")
    prompt = to_english_prompt(text)
    data = None
    # لو في توكن Hugging Face بنجربه الأول لأنه أسرع، وبعدين Pollinations
    order = ([img_hf] if HF_TOKEN else []) + [img_pollinations]
    for fn in order:
        try:
            data = fn(prompt)
            break
        except Exception as e:
            print("image provider failed:", fn.__name__, e)
    if not data:
        send(chat_id, "معلش، مقدرتش أعمل الصورة دلوقتي. جرب تاني بعد شوية.")
        return
    tg("sendPhoto", data={"chat_id": chat_id}, files={"photo": ("image.jpg", io.BytesIO(data))})


def wants_image(text):
    t = text.lower().strip()
    if t.startswith("/image") or t.startswith("/صورة"):
        return True
    if len(t) > 200:
        return False
    pic = any(w in t for w in ("صورة", "صوره", "صور ", "رسمة", "رسم", "ارسم", "إرسم", "draw", "image", "picture"))
    verb = any(w in t for w in ("ارسم", "إرسم", "ولد", "اعمل", "اعملي", "هات", "عايز", "عاوز", "نفسي", "ابعت", "طلع", "draw", "generate", "make", "create"))
    return pic and (verb or t.startswith(("صورة", "صوره", "رسم")))


def clean_image_text(text):
    for w in ("/image", "/صورة"):
        if text.lower().startswith(w):
            return text[len(w):].strip()
    return text


# ---------------- التشغيل ----------------
def handle(msg):
    chat_id = msg["chat"]["id"]
    text = (msg.get("text") or "").strip()
    if not text:
        send(chat_id, "ابعتلي رسالة نصية. ولو عايز صورة اكتب: ارسم قطة في الفضاء")
        return
    if text.startswith("/start") or text.startswith("/help"):
        send(chat_id, "أهلاً! أنا بوت ذكاء اصطناعي.\n- اكتبلي أي سؤال وأنا أرد.\n"
                      "- لصورة اكتب: ارسم ... (مثال: ارسم قطة في الفضاء) أو /image وبعدها الوصف.\n"
                      "- /reset لمسح المحادثة.\nملحوظة: الفيديو مش متاح في النسخة المجانية.")
        return
    if text.startswith("/reset"):
        history.pop(chat_id, None)
        send(chat_id, "تمام، مسحت المحادثة.")
        return
    tg("sendChatAction", data={"chat_id": chat_id, "action": "typing"})
    if wants_image(text):
        make_image(chat_id, clean_image_text(text) or "a beautiful landscape")
    else:
        send(chat_id, answer(chat_id, text))


def safe_handle(msg):
    try:
        handle(msg)
    except Exception as e:
        print("error:", e)


class Ping(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")
    def do_HEAD(self):
        self.send_response(200); self.end_headers()
    def log_message(self, *a):
        pass


def web():
    port = int(os.environ.get("PORT", "10000"))
    HTTPServer(("0.0.0.0", port), Ping).serve_forever()


def main():
    if not TELEGRAM_TOKEN:
        raise SystemExit("ناقص TELEGRAM_TOKEN")
    threading.Thread(target=web, daemon=True).start()
    tg("deleteWebhook")
    offset = None
    print("البوت اشتغل")
    while True:
        try:
            r = tg("getUpdates", data={"timeout": 50, "offset": offset or ""})
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                if "message" in u:
                    print("got message", u["message"]["chat"]["id"], (u["message"].get("text") or "")[:40], flush=True)
                    threading.Thread(target=safe_handle, args=(u["message"],), daemon=True).start()
        except Exception as e:
            print("loop error:", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
