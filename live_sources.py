import datetime as dt
import ipaddress
import socket
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, urljoin
from zoneinfo import ZoneInfo
import requests

CAIRO = ZoneInfo('Africa/Cairo')


def safe_url(url):
    p = urlsplit(url)
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password:
        raise ValueError('اللينك لازم يكون HTTP أو HTTPS عادي.')
    if p.port not in (None, 80, 443):
        raise ValueError('اللينك ده مش مدعوم.')
    for item in socket.getaddrinfo(p.hostname, p.port or 443):
        if not ipaddress.ip_address(item[4][0]).is_global:
            raise ValueError('مينفعش أفتح عنوان شبكة داخلية.')
    return url


def article_text(url):
    from bs4 import BeautifulSoup
    for _ in range(4):
        safe_url(url)
        r = requests.get(url, timeout=15, allow_redirects=False, stream=True,
                         headers={'User-Agent': 'AhmedBotArticleReader/1.0'})
        if r.is_redirect:
            url = urljoin(url, r.headers['Location'])
            continue
        r.raise_for_status()
        if 'html' not in r.headers.get('Content-Type', ''):
            raise ValueError('اللينك مش صفحة مقال HTML. ابعت النص أو الملف.')
        buf = bytearray()
        for chunk in r.iter_content(65536):
            buf.extend(chunk)
            if len(buf) > 2_000_000:
                raise ValueError('الصفحة كبيرة. ابعت النص المطلوب مباشرة.')
        soup = BeautifulSoup(bytes(buf), 'html.parser')
        for node in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'form']):
            node.decompose()
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        main = soup.find('article') or soup.find('main') or soup.body or soup
        text = main.get_text(' ', strip=True)
        if len(text) < 200:
            raise ValueError('مقدرتش أوصل لنص كفاية من الصفحة. ممكن تكون مقفولة أو محتاجة تسجيل دخول. ابعت النص هنا.')
        return title, text[:24000], url, len(text) > 24000
    raise ValueError('اللينك بيحوّل كتير. ابعت رابط المقال المباشر.')


def youtube_text(url):
    from youtube_transcript_api import YouTubeTranscriptApi
    p = urlsplit(url)
    if p.hostname in ('youtu.be', 'www.youtu.be'):
        video = p.path.strip('/')
    else:
        from urllib.parse import parse_qs
        video = parse_qs(p.query).get('v', [''])[0]
        if not video:
            video = p.path.split('/')[-1]
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('ابعت رابط فيديو يوتيوب صحيح.')
    try:
        transcript = YouTubeTranscriptApi().fetch(video, languages=['ar', 'en'])
        text = ' '.join(x.text for x in transcript)
        return 'YouTube transcript', text[:24000], url, len(text) > 24000
    except Exception:
        raise ValueError('مقدرتش أجيب تفريغ الفيديو. ممكن مفيش ترجمة متاحة أو يوتيوب مانع الوصول. ابعت التفريغ أو ملف الصوت.')


def fresh_headlines():
    from email.utils import parsedate_to_datetime
    url = 'https://news.google.com/rss/headlines/section/topic/WORLD?hl=ar&gl=EG&ceid=EG:ar'
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    now = dt.datetime.now(CAIRO)
    rows = []
    for item in root.findall('./channel/item'):
        try:
            published = parsedate_to_datetime(item.findtext('pubDate')).astimezone(CAIRO)
        except Exception:
            continue
        if published.date() != now.date() or published > now:
            continue
        title = item.findtext('title') or ''
        link = item.findtext('link') or ''
        rows.append((published, title, link))
    rows.sort(reverse=True)
    if not rows:
        return 'مفيش عناوين بتاريخ النهارده في المصدر اللي قدرت أوصله دلوقتي. مش هقدملك القديم على إنه جديد.'
    lines = ['أحدث عناوين النهارده المتاحة في Google News، مش ملخص قراءة للمقالات كاملة.',
             'تم التحقق: ' + now.strftime('%Y-%m-%d %H:%M') + ' بتوقيت القاهرة. مش بث لحظي وممكن المصدر يتأخر.']
    for published, title, link in rows[:5]:
        lines.append(published.strftime('%H:%M') + ' | ' + title + '\n' + link)
    return '\n\n'.join(lines)


def weather(city):
    if not city.strip():
        return 'طقس أنهي مدينة؟ ابعت /weather وبعده اسم المدينة.'
    r = requests.get('https://geocoding-api.open-meteo.com/v1/search',
                     params={'name': city, 'count': 5, 'language': 'ar', 'format': 'json'}, timeout=15)
    r.raise_for_status()
    places = r.json().get('results', [])
    if not places:
        return 'مقدرتش أحدد المدينة. جرب اسمها بالإنجليزي ومعاه البلد.'
    if city.strip().lower() in ('cairo', 'القاهرة', 'القاهره'):
        places = [p for p in places if p.get('country_code') == 'EG'] or places
    if len(places) > 1 and places[0].get('name') == places[1].get('name'):
        return 'الاسم موجود في أكتر من مكان. ابعت اسم مدينة أوضح. الأماكن: ' + ', '.join(p.get('name','')+' '+p.get('country','') for p in places[:5])
    place = places[0]
    r = requests.get('https://api.open-meteo.com/v1/forecast',
                     params={'latitude': place['latitude'], 'longitude': place['longitude'],
                             'current': 'temperature_2m,relative_humidity_2m,wind_speed_10m',
                             'timezone': 'auto'}, timeout=15)
    r.raise_for_status()
    data = r.json(); c = data['current']
    return (f"طقس {place['name']}، {place.get('country','')}\nوقت بيانات المصدر: {c['time']} {data.get('timezone','')}\n"
            f"الحرارة {c['temperature_2m']}°م، الرطوبة {c['relative_humidity_2m']}٪، الرياح {c['wind_speed_10m']} كم/س.\n"
            'المصدر: https://open-meteo.com/\nدي بيانات طقس من المصدر، مش قياس مباشر من مكانك.')


def geo_place(place):
    # Same converter /clock geocoder the /weather and /prayer commands use, shared
    # here so alert subscriptions can resolve a city without importing the entry module.
    import os
    url = os.environ.get('CONVERTER_URL', '').rstrip('/'); key = os.environ.get('CONVERTER_KEY', '')
    if not place:
        place = 'Cairo, Egypt'
    aliases = {'طوكيو': 'Tokyo, Japan', 'tokyo': 'Tokyo, Japan', 'القاهرة': 'Cairo, Egypt', 'القاهره': 'Cairo, Egypt', 'cairo': 'Cairo, Egypt', 'الرياض': 'Riyadh, Saudi Arabia', 'جدة': 'Jeddah, Saudi Arabia', 'جده': 'Jeddah, Saudi Arabia'}
    place = aliases.get(place.strip().casefold(), place)
    r = requests.get(url + '/clock', params={'place': place, 'geo': '1'}, headers={'Authorization': 'Bearer ' + key}, timeout=95)
    r.raise_for_status()
    d = r.json()
    if d.get('error'):
        return None, d['error']
    if d.get('choices'):
        return None, 'الاسم موجود في أكتر من مكان. حدد المدينة والبلد:\n' + '\n'.join(x['name'] + '، ' + x['cc'] + ' | ' + x['kind'] for x in d['choices'])
    if not all(k in d for k in ('lat', 'lon', 'tz')):
        return None, 'خدمة الإحداثيات لسه مش جاهزة. مش هخمن المكان.'
    note = d.get('note', '').replace('توقيت العاصمة المسجلة، مش بالضرورة كل مناطق البلد.', 'المكان هو العاصمة المسجلة، مش البلد كله.').replace('توقيت المركز المسجّل للإقليم؛ الإقليم الكبير ممكن يكون فيه مناطق بتوقيت مختلف.', 'المكان هو مركز الإقليم المسجّل، مش كل مناطقه.')
    return d, note
