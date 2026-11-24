import ast
import datetime as dt
import math
import operator
import requests
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Africa/Cairo')


def calculate(expr):
    if len(expr) > 150:
        raise ValueError('المعادلة طويلة.')
    ops = {ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,
           ast.Div:operator.truediv,ast.Mod:operator.mod,ast.Pow:operator.pow}
    def visit(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):
            if abs(n.value)>1e15:raise ValueError('الرقم كبير جداً.')
            return n.value
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.USub,ast.UAdd)):
            return -visit(n.operand) if isinstance(n.op,ast.USub) else visit(n.operand)
        if isinstance(n,ast.BinOp) and type(n.op) in ops:
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Pow) and (abs(b)>10 or abs(a)>1e8):raise ValueError('الأس كبير جداً.')
            v=ops[type(n.op)](a,b)
            if not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>1e30:raise ValueError('الناتج خارج الحدود.')
            return v
        raise ValueError('استخدم أرقام وعلامات + - * / ** % وأقواس فقط.')
    return visit(ast.parse(expr,mode='eval').body)


def convert(value, source, target):
    units={'m':('length',1),'km':('length',1000),'cm':('length',.01),'mm':('length',.001),
           'mile':('length',1609.344),'ft':('length',.3048),'in':('length',.0254),
           'kg':('mass',1),'g':('mass',.001),'lb':('mass',.45359237),
           'l':('volume',1),'ml':('volume',.001),
           's':('time',1),'min':('time',60),'h':('time',3600)}
    if source in ('c','f') and target in ('c','f'):
        return value if source==target else (value*9/5+32 if source=='c' else (value-32)*5/9)
    if source not in units or target not in units or units[source][0]!=units[target][0]:
        raise ValueError('الوحدات المدعومة: m km cm mm mile ft in، kg g lb، l ml، s min h، c f. لازم نفس نوع القياس.')
    return value*units[source][1]/units[target][1]


def prices():
    url='https://getdaleelak.com/api/v1/feed.json?asset=us-dollar,gold-21k'
    r=requests.get(url,timeout=15);r.raise_for_status();d=r.json()
    lines=['أسعار استرشادية من دليلَك، مش تحديث لحظي ولا عرض بيع مضمون.']
    now=dt.datetime.now(TZ)
    for a in d.get('assets',[]):
        observed=a.get('observedAt')
        when=dt.datetime.fromisoformat(observed.replace('Z','+00:00')).astimezone(TZ) if observed else None
        if not when or when>now or (now-when).total_seconds()>86400:
            lines.append(a.get('id','')+': البيانات قديمة أو وقتها غير متحقق، مش هعرضها كسعر حالي.')
            continue
        sellers=a.get('sellers',[])[:3]
        label='الدولار، جنيه لكل دولار' if a.get('id')=='USD-EGP' else 'ذهب عيار ٢١، جنيه للجرام، بدون مصنعية'
        lines.append(label+'\nوقت بيانات المصدر: '+when.strftime('%Y-%m-%d %H:%M'))
        for s in sellers:
            lines.append(f"{s.get('sellerAr') or s.get('seller')}: يشتري منك {s.get('buy')}، يبيع لك {s.get('sell')}")
    lines.extend(['وقت التحقق: '+now.strftime('%Y-%m-%d %H:%M:%S')+' القاهرة','راجع البنك أو التاجر قبل التعامل.\nالمصدر: https://getdaleelak.com/en/api'])
    return '\n'.join(lines)


def prayers():
    now=dt.datetime.now(TZ)
    url='https://api.aladhan.com/v1/timings/'+now.strftime('%d-%m-%Y')
    r=requests.get(url,params={'latitude':30.0444,'longitude':31.2357,'method':5,'timezonestring':'Africa/Cairo'},timeout=15)
    r.raise_for_status();d=r.json()['data']
    if d['date']['gregorian']['date']!=now.strftime('%d-%m-%Y') or abs(d['meta']['latitude']-30.0444)>.02:
        raise ValueError('المصدر رجع تاريخ أو موقع مختلف، مش هعرض مواعيد غير مؤكدة.')
    names={'Fajr':'الفجر','Sunrise':'الشروق','Dhuhr':'الظهر','Asr':'العصر','Maghrib':'المغرب','Isha':'العشاء'}
    return ('مواقيت القاهرة '+now.strftime('%Y-%m-%d')+' بتوقيت القاهرة\n'+
            '\n'.join(names[k]+': '+d['timings'][k] for k in names)+
            '\nحساب AlAdhan بطريقة الهيئة المصرية العامة للمساحة، مش نشرة رسمية مباشرة. ممكن يختلف دقائق عن المسجد المحلي.\nالمصدر: https://aladhan.com/calculation-methods')
