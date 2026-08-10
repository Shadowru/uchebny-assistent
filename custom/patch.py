import os, shutil, json, re

NAME = os.environ.get("WEBUI_NAME", "Учебный ассистент")
IDX = "/app/build/index.html"
BUILD_STATIC = "/app/build/static"
BACKEND_STATIC = "/app/backend/open_webui/static"

snippet = (
    '<script>try{var l=localStorage;'
    'var q=new URLSearchParams(location.search).get("design");'
    'if(q==="a"||q==="b"){l.mesDesign=q;}'
    'var d=l.mesDesign==="b"?"b":"a";'
    'var lk=document.createElement("link");lk.rel="stylesheet";'
    'lk.href="/static/custom/mes-theme-"+d+".css";document.head.appendChild(lk);'
    'if(!l._mesMigrated){'
    'if(l.locale&&l.locale!=="ru-RU"){l.locale="ru-RU";}'
    'if(!l.theme||l.theme==="system"||l.theme==="dark"){l.theme="light";}'
    'l._mesMigrated="1";}'
    '}catch(e){}</script>'
)

TOPBAR_JS = """<script>(function(){function mk(){
if(document.getElementById('mes-topbar'))return;
var b=document.createElement('div');b.id='mes-topbar';
b.innerHTML='<div class="mes-left"><img src="/static/favicon.png" alt="">'+
'<span class="mes-title">Учебный ассистент</span></div>'+
'<nav class="mes-nav">'+
'<button class="mes-item" type="button">Дневник</button>'+
'<button class="mes-item" type="button">Расписание</button>'+
'<button class="mes-item" type="button">Домашние задания</button>'+
'<button class="mes-item" type="button">Библиотека</button>'+
'<button class="mes-item mes-active" type="button">ИИ-ассистент</button>'+
'</nav>'+
'<button id="mes-logout" type="button">Выйти</button>';
document.body.appendChild(b);
var lo=document.getElementById('mes-logout');
lo.addEventListener('click',function(){
fetch('/api/v1/auths/signout',{method:'POST',credentials:'include'})
.catch(function(){}).finally(function(){
try{localStorage.removeItem('token')}catch(e){}
location.href='/auth';});});
function tick(){try{lo.classList.toggle('mes-hidden',!localStorage.token)}catch(e){}}
tick();setInterval(tick,2000);
var heroName=null;
function getName(cb){if(heroName!==null){cb(heroName);return;}
fetch('/api/v1/auths/',{headers:{'Authorization':'Bearer '+(localStorage.token||'')}})
.then(function(r){return r.json()}).then(function(u){heroName=(u&&u.name)||'';cb(heroName);})
.catch(function(){cb('');});}
function greetWord(){var h=new Date().getHours();return h<5?'Доброй ночи':(h<12?'Доброе утро':(h<18?'Добрый день':'Добрый вечер'));}
function dateLine(){var d=new Date();
var days=['Воскресенье','Понедельник','Вторник','Среда','Четверг','Пятница','Суббота'];
var months=['января','февраля','марта','апреля','мая','июня','июля','августа','сентября','октября','ноября','декабря'];
return days[d.getDay()]+', '+d.getDate()+' '+months[d.getMonth()];}
function hero(){
var cands=document.querySelectorAll('div.max-w-xl');var a=null;
for(var i=0;i<cands.length;i++){if(cands[i].className.indexOf('justify-center')>-1&&cands[i].querySelector('img')){a=cands[i];break;}}
if(!a)return;
a.style.display='none';
if(a.parentElement.querySelector('#mes-hero'))return;
var h=document.createElement('div');h.id='mes-hero';
h.innerHTML='<div class="mes-hero-date">'+dateLine()+'</div>'+
'<div class="mes-hero-title">\u00A0</div>'+
'<div class="mes-hero-sub">Помогу подготовить урок: план, объяснения по-разному, рабочий лист. Выберите карточку ниже или опишите задачу своими словами.</div>';
a.parentElement.insertBefore(h,a);
getName(function(n){var t=h.querySelector('.mes-hero-title');if(t)t.textContent=greetWord()+(n?', '+n:'')+'!';});}
var mo=new MutationObserver(function(){hero();});
mo.observe(document.body,{childList:true,subtree:true});
hero();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mk);else mk();
})();</script>"""

try:
    s = open(IDX).read()
    if "mes-theme" not in s:
        s = s.replace("<head>", "<head>" + snippet, 1)
    s = s.replace('<html lang="en">', '<html lang="ru">')
    s = s.replace("Open WebUI", NAME)
    if "mes-topbar" not in s:
        s = s.replace("</body>", TOPBAR_JS + "</body>")
    open(IDX, "w").write(s)

    # темы и шрифты
    for dst in (BUILD_STATIC, BACKEND_STATIC):
        os.makedirs(f"{dst}/custom/fonts", exist_ok=True)
        for css in ("mes-theme-a.css", "mes-theme-b.css"):
            shutil.copy(f"/custom/{css}", f"{dst}/custom/{css}")
        for f in os.listdir("/custom/fonts"):
            shutil.copy(f"/custom/fonts/{f}", f"{dst}/custom/fonts/{f}")

    # фирменные иконки поверх обеих статик
    for f in os.listdir("/custom/assets"):
        for dst in (BUILD_STATIC, BACKEND_STATIC):
            try:
                shutil.copy(f"/custom/assets/{f}", f"{dst}/{f}")
            except Exception:
                pass

    # имя в PWA-манифесте
    for dst in (BUILD_STATIC, BACKEND_STATIC):
        mf = f"{dst}/site.webmanifest"
        if os.path.exists(mf):
            try:
                m = json.load(open(mf))
                m["name"] = NAME
                m["short_name"] = NAME
                json.dump(m, open(mf, "w"), ensure_ascii=False)
            except Exception:
                pass

    # убрать суффикс " (Open WebUI)" из WEBUI_NAME
    envp = "/app/backend/open_webui/env.py"
    e = open(envp).read()
    e2 = re.sub(r"^(\s*)WEBUI_NAME \+= . \(Open WebUI\).$", r"\1pass", e, flags=re.M)
    if e2 != e:
        open(envp, "w").write(e2)

    print("MES patch applied")
except Exception as e:
    print("MES patch FAILED (app will start unthemed):", e)
