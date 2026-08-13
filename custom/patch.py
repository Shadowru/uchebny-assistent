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
'<div class="mes-hero-sub">Помогу подготовить урок: план, объяснения по-разному, рабочий лист. Соберите материал по шагам, выберите карточку ниже или опишите задачу своими словами.</div>'+
'<div class="mes-hero-actions"><span class="mes-ha-label">Собрать по шагам:</span>'+
'<button class="mes-wiz-btn" data-wiz="plan" type="button">План урока</button>'+
'<button class="mes-wiz-btn" data-wiz="explain" type="button">Объяснить по-разному</button>'+
'<button class="mes-wiz-btn" data-wiz="task" type="button">Рабочий лист</button></div>';
a.parentElement.insertBefore(h,a);
getName(function(n){var t=h.querySelector('.mes-hero-title');if(t)t.textContent=greetWord()+(n?', '+n:'')+'!';});}
var mo=new MutationObserver(function(){hero();});
mo.observe(document.body,{childList:true,subtree:true});
hero();}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mk);else mk();
})();</script>"""

# опросы-конструкторы в стиле МЭШ: пошаговая форма -> готовый запрос в чат
WIZARD_JS = r"""<script id="mes-wizard">(function(){
var SUBJ=['Русский язык','Математика','Литература','Окружающий мир','Английский язык','История','Обществознание','География','Биология','Физика','Химия','Информатика'];
var CLS=['1','2','3','4','5','6','7','8','9','10','11'];
var CFG={
plan:{title:'План урока',command:'/план-урока',
intro:'Несколько вопросов — и ассистент соберёт план урока с готовым материалом по ФГОС.',
fallback:'Составь подробный план урока по ФГОС с готовым конкретным материалом: все задания, слова и примеры выписаны целиком, без ссылок на учебники и номера упражнений. Формат: тема и тип урока; цель и планируемые результаты; оборудование; ход урока таблицей (Этап | Время | Деятельность учителя | Деятельность учеников); домашнее задание; рефлексия.',
steps:[
{key:'Класс',type:'pills',required:true,options:CLS},
{key:'Предмет',type:'pills',required:true,custom:'Свой предмет…',options:SUBJ},
{key:'Тема урока',type:'text',required:true,ph:'Например: квадратные уравнения, акцент на графическом методе'},
{key:'Тип урока',type:'pills',options:['Определи по теме','Изучение нового','Закрепление','Повторение','Контроль'],def:0},
{key:'Длительность',type:'pills',options:['45 минут','20 минут','2 урока (90 минут)'],def:0},
{key:'Задания двух уровней сложности',type:'toggle',desc:'Добавить к этапам урока варианты базового и повышенного уровня',on:'да — добавь к заданиям варианты базового и повышенного уровня',off:''},
{key:'Пожелания',type:'textarea',opt:true,ph:'Например: добавь этап работы в парах и рефлексию в конце'}
]},
explain:{title:'Объяснить по-разному',command:'/объяснить-по-разному',
intro:'Несколько принципиально разных объяснений одного понятия — на случай, если основное не сработало.',
fallback:'Дай несколько принципиально разных объяснений одного понятия (аналогия, разбор на примере, визуальный образ, пошаговый разбор, история, противопоставление) таблицей: Тип | Объяснение (обращено к ученику, готово к произнесению) | Где ломается. Уровень языка — строго под класс.',
steps:[
{key:'Класс',type:'pills',required:true,options:CLS},
{key:'Предмет',type:'pills',required:true,custom:'Свой предмет…',options:SUBJ},
{key:'Понятие',type:'text',required:true,ph:'Одно понятие, не раздел. Например: дробь, подлежащее, фотосинтез'},
{key:'Сколько объяснений',type:'pills',options:['3','4','5'],def:1},
{key:'Что уже пробовали',type:'textarea',opt:true,ph:'Объяснение, которое не сработало, — чтобы его не повторять'}
]},
task:{title:'Учебное задание',command:'/учебное-задание',
intro:'Готовый раздаточный материал: разминка, основной блок, термины, вопросы — или целый рабочий лист.',
fallback:'Составь готовое к выдаче в классе учебное задание: весь материал выписан целиком, без ссылок на учебники; к каждому заданию с правильным ответом дай ключ и краткое основание в одну строку.',
steps:[
{key:'Класс',type:'pills',required:true,options:CLS},
{key:'Предмет',type:'pills',required:true,custom:'Свой предмет…',options:SUBJ},
{key:'Тема',type:'text',required:true,ph:'Например: причастный оборот'},
{key:'Тип задания',type:'pills',options:['Полный рабочий лист','Разминка','Основной блок','Термины','Вопросы'],def:0},
{key:'Уровень',type:'pills',options:['Базовый','Повышенный'],def:0},
{key:'Пожелания',type:'textarea',opt:true,ph:'Например: сделай упор на типичные ошибки'}
]}};
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
function ctrl(s,i){
if(s.type==='pills'){var h='<div class="mes-pills" data-i="'+i+'">';
for(var j=0;j<s.options.length;j++){h+='<button type="button" class="mes-pill'+(s.def===j?' mes-pill-on':'')+'">'+esc(s.options[j])+'</button>';}
if(s.custom)h+='<input class="mes-pill-custom" placeholder="'+esc(s.custom)+'">';
return h+'</div>';}
if(s.type==='text')return '<input class="mes-wiz-input" data-i="'+i+'" placeholder="'+esc(s.ph||'')+'">';
if(s.type==='textarea')return '<textarea class="mes-wiz-ta" data-i="'+i+'" rows="2" placeholder="'+esc(s.ph||'')+'"></textarea>';
return '';}
function closeW(){var o=document.getElementById('mes-wiz-overlay');if(o)o.remove();document.removeEventListener('keydown',onKey);}
function onKey(e){if(e.key==='Escape')closeW();}
function openW(id){var c=CFG[id];if(!c)return;closeW();
var sh='',n=0;
for(var i=0;i<c.steps.length;i++){var s=c.steps[i];var badge='';
if(s.type!=='textarea'){n++;badge='<span class="mes-wiz-badge">Шаг '+n+'</span>';}
sh+='<div class="mes-wiz-step" data-step="'+i+'"><div class="mes-wiz-step-head">'+badge+
'<span class="mes-wiz-step-title">'+esc(s.key)+(s.opt?' <em>— необязательно</em>':'')+'</span>'+
(s.type==='toggle'?'<button type="button" class="mes-switch" data-i="'+i+'" aria-checked="false"><span></span></button>':'')+
'</div>'+(s.desc?'<div class="mes-wiz-step-desc">'+esc(s.desc)+'</div>':'')+ctrl(s,i)+'</div>';}
var ov=document.createElement('div');ov.id='mes-wiz-overlay';
ov.innerHTML='<div class="mes-wiz-panel" role="dialog" aria-modal="true">'+
'<div class="mes-wiz-head"><div><div class="mes-wiz-title">'+esc(c.title)+'</div>'+
'<div class="mes-wiz-intro">'+esc(c.intro)+'</div></div>'+
'<button type="button" class="mes-wiz-close" aria-label="Закрыть">&times;</button></div>'+
'<div class="mes-wiz-body">'+sh+'</div>'+
'<div class="mes-wiz-foot"><span class="mes-wiz-note">Ответ — черновик: проверьте материал перед уроком</span>'+
'<button type="button" class="mes-wiz-go">&#10024; Сгенерировать материалы</button></div></div>';
document.body.appendChild(ov);
document.addEventListener('keydown',onKey);
ov.addEventListener('click',function(e){
if(e.target===ov||e.target.closest('.mes-wiz-close')){closeW();return;}
var st=e.target.closest('.mes-wiz-step');if(st)st.classList.remove('mes-wiz-error');
var p=e.target.closest('.mes-pill');
if(p){var g=p.parentElement;
var on=g.querySelectorAll('.mes-pill-on');for(var k=0;k<on.length;k++)on[k].classList.remove('mes-pill-on');
p.classList.add('mes-pill-on');
var ci=g.querySelector('.mes-pill-custom');if(ci)ci.value='';return;}
var sw=e.target.closest('.mes-switch');
if(sw){sw.setAttribute('aria-checked',sw.getAttribute('aria-checked')==='true'?'false':'true');return;}
if(e.target.closest('.mes-wiz-go'))generate(c,ov);});
ov.addEventListener('input',function(e){
var st=e.target.closest('.mes-wiz-step');if(st)st.classList.remove('mes-wiz-error');
if(e.target.classList.contains('mes-pill-custom')&&e.target.value){
var on=e.target.parentElement.querySelectorAll('.mes-pill-on');
for(var k=0;k<on.length;k++)on[k].classList.remove('mes-pill-on');}});}
function collect(c,ov){var lines=[];
for(var i=0;i<c.steps.length;i++){var s=c.steps[i],v='';
var card=ov.querySelector('.mes-wiz-step[data-step="'+i+'"]');
if(s.type==='pills'){var g=ov.querySelector('.mes-pills[data-i="'+i+'"]');
var ci=g.querySelector('.mes-pill-custom');
if(ci&&ci.value.trim())v=ci.value.trim();
else{var on=g.querySelector('.mes-pill-on');v=on?on.textContent.trim():'';}}
else if(s.type==='toggle'){var sw=ov.querySelector('.mes-switch[data-i="'+i+'"]');
v=(sw&&sw.getAttribute('aria-checked')==='true')?s.on:s.off;}
else{var el=ov.querySelector('[data-i="'+i+'"]');v=el?el.value.trim():'';}
if(s.required&&!v){if(card){card.classList.add('mes-wiz-error');card.scrollIntoView({behavior:'smooth',block:'center'});}return null;}
if(v)lines.push('- '+s.key+': '+v);}
return lines;}
function getTpl(cmd,cb){
fetch('/api/v1/prompts/list',{headers:{'Authorization':'Bearer '+(localStorage.token||'')}})
.then(function(r){return r.json()}).then(function(d){
var arr=(d&&d.items)||(Array.isArray(d)?d:[]);
for(var i=0;i<arr.length;i++){if(arr[i].command===cmd){cb(arr[i].content||null);return;}}
cb(null);}).catch(function(){cb(null);});}
function sendToChat(text){
var el=document.getElementById('chat-input');
if(!el){location.href='/?q='+encodeURIComponent(text);return;}
el.focus();
try{var sel=window.getSelection();sel.selectAllChildren(el);document.execCommand('delete');}catch(e){}
try{var dt=new DataTransfer();dt.setData('text/plain',text);
el.dispatchEvent(new ClipboardEvent('paste',{clipboardData:dt,bubbles:true,cancelable:true}));}catch(e){}
setTimeout(function(){
var got=(el.tagName==='TEXTAREA'?el.value:el.innerText)||'';
if(!got.trim()){location.href='/?q='+encodeURIComponent(text);return;}
var btn=document.getElementById('send-message-button');
if(btn&&!btn.disabled)btn.click();},450);}
function generate(c,ov){
var lines=collect(c,ov);if(!lines)return;
var go=ov.querySelector('.mes-wiz-go');go.disabled=true;go.textContent='Готовлю запрос…';
getTpl(c.command,function(tpl){
var msg=(tpl||c.fallback)+'\n\nДАННЫЕ УЧИТЕЛЯ (используй как входные данные):\n'+lines.join('\n');
closeW();sendToChat(msg);});}
document.addEventListener('click',function(e){
var b=e.target.closest?e.target.closest('.mes-wiz-btn'):null;
if(b)openW(b.getAttribute('data-wiz'));});
})();</script>"""

try:
    s = open(IDX).read()
    if "mes-theme" not in s:
        s = s.replace("<head>", "<head>" + snippet, 1)
    s = s.replace('<html lang="en">', '<html lang="ru">')
    s = s.replace("Open WebUI", NAME)
    if "mes-topbar" not in s:
        s = s.replace("</body>", TOPBAR_JS + "</body>")
    if "mes-wizard" not in s:
        s = s.replace("</body>", WIZARD_JS + "</body>")
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
