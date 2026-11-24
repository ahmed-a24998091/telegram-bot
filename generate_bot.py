"""Editable file builders. Text only, no external resources, scripts or macros."""
import io
import re
from docx import Document
from docx.shared import Pt, Inches as DInches, RGBColor as DColor
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pptx import Presentation
from pptx.util import Inches, Pt as PPoint
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN


def clean(value, limit):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))[:limit]


def make_word(data):
    doc=Document()
    sec=doc.sections[0]
    sec.top_margin=sec.bottom_margin=DInches(.8)
    for style in ('Normal','Title','Heading 1'):
        doc.styles[style].font.name='Arial'
        doc.styles[style].font.size=Pt(12 if style=='Normal' else 22)
    doc.add_heading(clean(data.get('title','مستند'),120),0)
    sections=data.get('sections',[])
    if not isinstance(sections,list) or not sections:raise ValueError('مفيش محتوى كافي للمستند.')
    for s in sections[:20]:
        if s.get('heading'):doc.add_heading(clean(s['heading'],120),1)
        for paragraph in s.get('paragraphs',[])[:10]:
            p=doc.add_paragraph(clean(paragraph,1200))
            p.paragraph_format.space_after=Pt(8)
    for p in doc.paragraphs:
        if re.search('[\u0600-\u06ff]',p.text):
            p.alignment=2
            bidi=OxmlElement('w:bidi');bidi.set(qn('w:val'),'1');p._p.get_or_add_pPr().append(bidi)
        for run in p.runs:
            run.font.name='Arial'
    output=io.BytesIO();doc.save(output);output.seek(0)
    return output


def make_slides(data):
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    slides=data.get('slides',[])
    if not isinstance(slides,list) or not slides:raise ValueError('مفيش محتوى كافي للعرض.')
    def box(slide,text,x,y,w,h,size,bold=False):
        shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
        tf=shape.text_frame;tf.word_wrap=True
        p=tf.paragraphs[0];p.text=text
        p.alignment=PP_ALIGN.RIGHT if re.search('[\u0600-\u06ff]',text) else PP_ALIGN.LEFT
        if re.search('[\u0600-\u06ff]',text):p._p.get_or_add_pPr().set('rtl','1')
        for run in p.runs:
            run.font.name='Arial';run.font.size=PPoint(size);run.font.bold=bold;run.font.color.rgb=RGBColor.from_string('251F21')
        return shape
    for i,s in enumerate(slides[:8]):
        slide=prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor(255,255,255)
        title=clean(s.get('title',''),90)
        box(slide,title,.7,.55,11.9,1.0,30,True)
        bullets=s.get('bullets',[])
        if not isinstance(bullets,list):raise ValueError('صيغة محتوى العرض مش واضحة.')
        for j,line in enumerate(bullets[:4]):box(slide,clean(line,170),.85,1.9+j*1.05,11.6,.88,22)
        box(slide,str(i+1),.7,6.85,1,.3,11)
        slide.notes_slide.notes_text_frame.text=clean(s.get('notes',''),1500)
    output=io.BytesIO();prs.save(output);output.seek(0)
    return output

import json
import re
import threading
import bot
import daily_bot

ORIGINAL=bot.handle
SCHEMAS={
 'word':'{"title":"عنوان","sections":[{"heading":"عنوان قسم","paragraphs":["فقرة"]}]}',
 'slides':'{"slides":[{"title":"عنوان الشريحة","bullets":["نقطة قصيرة"],"notes":"ملاحظات اختيارية"}]}'
}


def parse_data(raw,kind):
    raw=raw.strip()
    if raw.startswith('```'):
        raw=re.sub(r'^```(?:json)?\s*','',raw);raw=re.sub(r'\s*```$','',raw)
    data=json.loads(raw)
    if not isinstance(data,dict):raise ValueError('صيغة المحتوى مش واضحة.')
    if kind=='slides':
        slides=data.get('slides')
        if not isinstance(slides,list) or not 1<=len(slides)<=8:raise ValueError('عدد الشرائح لازم من ١ إلى ٨.')
        for s in slides:
            if not isinstance(s,dict) or not isinstance(s.get('title'),str) or len(s['title'])>65:raise ValueError('عنوان الشريحة طويل.')
            lines=s.get('bullets')
            if not isinstance(lines,list) or not 1<=len(lines)<=4 or any(not isinstance(x,str) or len(x)>115 for x in lines):raise ValueError('نقاط العرض طويلة أو غير واضحة.')
    else:
        if not isinstance(data.get('title'),str) or len(data['title'])>120:raise ValueError('عنوان المستند طويل.')
        sections=data.get('sections')
        if not isinstance(sections,list) or not 1<=len(sections)<=20:raise ValueError('عدد أقسام المستند خارج الحدود.')
        for s in sections:
            if not isinstance(s,dict) or len(str(s.get('heading','')))>120:raise ValueError('عنوان القسم طويل.')
            pars=s.get('paragraphs')
            if not isinstance(pars,list) or not 1<=len(pars)<=10 or any(not isinstance(x,str) or len(x)>1200 for x in pars):raise ValueError('فقرات المستند خارج الحدود.')
    return data


def handle(msg):
    text=(msg.get('text') or '').strip()
    chat=msg['chat']['id']
    if msg['chat'].get('type')!='private':return ORIGINAL(msg)
    if text in ('/commands','/features'):
        ORIGINAL(msg)
        bot.send(chat,'ملفات قابلة للتعديل:\n/word الموضوع أو النص لإنشاء Word\n/slides الموضوع لإنشاء PowerPoint من ١ إلى ٨ شرائح\nأو اطلب بالمصري: اعملي ملف وورد عن... / اعملي بوربوينت عن...\nالتصميم نصي بسيط، مش نسخ قالب قديم ولا تعديل ملف موجود. راجع الحقائق قبل المشاركة.');return
    kind=None;detail=''
    for command,k in (('/word','word'),('/slides','slides')):
        if text==command or text.startswith(command+' '):kind=k;detail=text[len(command):].strip();break
    if not kind and re.search(r'(?:اعمل|اعملي|اعمللي|جهز|جهزلي|انشئ|أنشئ|اكتبلي|صمم)',text):
        if re.search(r'(?:بوربوينت|بور بوينت|باوربوينت|باور بوينت|powerpoint|pptx)',text,re.I):kind='slides';detail=text
        elif re.search(r'(?:ملف وورد|ملف ورد|مستند وورد|word|docx)',text,re.I):kind='word';detail=text
    if not kind:return ORIGINAL(msg)
    if not detail:
        bot.send(chat,'اكتب '+('/word' if kind=='word' else '/slides')+' وبعده الموضوع أو النص اللي تحب أحوله لملف.');return
    try:
        bot.send(chat,'جاري تجهيز الملف')
        prompt=('أنشئ محتوى مسودة ملف حسب طلب المستخدم. لا تدّعي أنك أرسلت ملفاً، الكود سيبنيه. '
                'أخرج JSON فقط مطابق للمخطط، بدون Markdown. لا تخترع إحصاءات أو مصادر أو تواريخ أو أسماء ناقصة. '
                'لو الموضوع يحتاج بيانات حالية غير موجودة، اذكر بوضوح أن البيانات تحتاج تحقق ولا تخمنها. '
                'استخدم نفس لغة الطلب. للمستند بحد أقصى ٢٠ قسماً وكل قسم ١٠ فقرات والفقرات ١٢٠٠ حرف. '
                'للعرض بحد أقصى ٨ شرائح، العنوان ٦٥ حرفاً وأربع نقاط بكل شريحة، كل نقطة ١١٥ حرفاً. '
                'لا تتضمن أدوات أو أكواد أو روابط جلب خارجية. المخطط:\n'+SCHEMAS[kind]+'\nطلب المستخدم:\n'+detail[:12000])
        data=parse_data(bot.answer(chat,prompt),kind)
        stream=make_word(data) if kind=='word' else make_slides(data)
        name='document.docx' if kind=='word' else 'presentation.pptx'
        mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document' if kind=='word' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation'
        result=bot.tg('sendDocument',data={'chat_id':chat,'caption':'مسودة قابلة للتعديل. راجع الأسماء والأرقام والحقائق قبل المشاركة.'},files={'document':(name,stream,mime)})
        if not result.get('ok'):raise ValueError('تعذر إرسال المرفق. جرب طلب أصغر.')
    except Exception:
        print('file_generation_failed',flush=True)
        bot.send(chat,'مقدرتش أجهز ملف سليم بالطلب ده. جرّب موضوع أوضح أو محتوى أقصر. مش هقولك الملف اتبعت وهو متبعتش.')

bot.handle=handle
if __name__=='__main__':
    daily_bot.extra_bot.init_reminders()
    threading.Thread(target=daily_bot.extra_bot.reminders_loop,daemon=True).start()
    print('file_generation_ready',flush=True)
    bot.main()
