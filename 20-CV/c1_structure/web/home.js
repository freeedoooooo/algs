/* web/home.js — 工作台首页：快速解析条 + 四张状态卡 + 待办列表。
   计数纯前端拼装
   （/api/tasks ＋ /api/staging/ledger），无新端点、无状态落库。 */
var hpicked=[], tplId=null;
var hdrop=document.getElementById('hdrop'), hpick=document.getElementById('hpick');
var hlist=document.getElementById('hlist'), hgo=document.getElementById('hgo');
var hmsg=document.getElementById('hmsg'), htpl=document.getElementById('htpl');
var TKEY='c1.home_tpl';
var items=[], led=[], tplCount=0;
var pollT=null, loopT=null, lastTaskId=null;
var todoPage=1, todoSize=getListPer();
var pgTodo=bindPager(document.getElementById('todopg'),
  function(d){ todoPage+=d; render(); },
  function(n){ todoSize=n; todoPage=1; render(); });

function say(t,cls){ hmsg.textContent=t; hmsg.className='qmsg'+(cls?' '+cls:''); }
function sayHtml(html,cls){ hmsg.innerHTML=html; hmsg.className='qmsg'+(cls?' '+cls:''); }

/* ---- 抽取规则下拉：与解析页同源；记住上次选择（H3） ---- */
fetch('/api/extract-rules').then(function(r){return r.json();}).then(function(j){
  var its=j.items||[]; tplCount=its.length; renderCards();
  if(!its.length){ htpl.innerHTML='<option value="">原始透传 v1</option>'; return; }
  htpl.innerHTML=its.map(function(t){
    return '<option value="'+(t.current_version_id||'')+'" data-tid="'+t.id+'">'+
      escHtml((t.name||'原始透传')+' v'+(t.current_version||1))+'</option>';
  }).join('');
  var saved=Number(localStorage.getItem(TKEY));
  if(saved) for(var i=0;i<htpl.options.length;i++)
    if(htpl.options[i].value===String(saved)){ htpl.selectedIndex=i; break; }
}).catch(function(){ htpl.innerHTML='<option value="">原始透传 v1</option>'; });
htpl.addEventListener('change',function(){
  try{ localStorage.setItem(TKEY,htpl.value); }catch(e){}
});

/* ---- 快速解析：选文件 → 就地提交（复用 /api/upload 通道） ---- */
var ALLOWED=['png','jpg','jpeg','bmp','webp','tif','tiff','pdf','csv','txt','md'];
hdrop.onclick=function(){ hpick.click(); };
hdrop.ondragover=function(e){e.preventDefault();hdrop.classList.add('on');};
hdrop.ondragleave=function(){hdrop.classList.remove('on');};
hdrop.ondrop=function(e){
  e.preventDefault();hdrop.classList.remove('on');addFiles(e.dataTransfer.files);
};
hpick.onchange=function(){ addFiles(hpick.files); hpick.value=''; };
function addFiles(fs){
  var rejected=[];
  for(var i=0;i<fs.length;i++){
    var f=fs[i];
    var e=(f.name.split('.').pop()||'').toLowerCase();
    if(ALLOWED.indexOf(e)<0){ rejected.push(f.name); continue; }
    if(f.size>20*1024*1024){ rejected.push(f.name+'（超过 20MB）'); continue; }
    if(hpicked.some(function(p){return p.name===f.name&&p.size===f.size;})) continue;
    hpicked.push(f);
  }
  if(rejected.length) say('以下文件不支持或超过 20MB，已忽略：'+rejected.join('、'),'err');
  else if(hpicked.length) say('已选 '+hpicked.length+' 个文件，点击「开始解析」');
  renderPicked();
}
function renderPicked(){
  hlist.hidden=hpicked.length===0;
  hlist.innerHTML=hpicked.map(function(f,i){
    return '<li><span title="'+escHtml(f.name)+'">'+escHtml(f.name)+'</span>'+
      '<span>'+ (f.size/1024).toFixed(0)+' KB</span>'+
      '<button type="button" class="fdel" data-i="'+i+'" title="移除">×</button></li>';
  }).join('');
  hgo.disabled=hpicked.length===0;
}
hlist.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('.fdel'):null;
  if(!b) return;
  hpicked.splice(Number(b.getAttribute('data-i')),1);
  renderPicked();
  if(!hpicked.length) say('未选择文件');
});

hgo.onclick=function(){
  hgo.disabled=true; say('正在读取文件…','run');
  Promise.all(hpicked.map(function(f){
    return b64(f).then(function(d){ return {name:f.name,data:d}; });
  })).then(function(files){
    return fetch('/api/upload',{method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({files:files,
        rule_version_id:htpl.value?Number(htpl.value):null})
    }).then(function(r){return r.json();});
  }).then(function(j){
    if(!j.ok) throw new Error(j.error||'提交失败');
    sayHtml('已提交，正在解析…　<a class="linkbtn" href="/parse">查看进度</a>','run');
    pollStatus();
  }).catch(function(e){
    say('提交失败：'+e.message,'err'); hgo.disabled=hpicked.length===0;
  });
};
function pollStatus(){
  fetch('/api/status').then(function(r){return r.json();}).then(function(s){
    if(s.running){ pollT=setTimeout(pollStatus,800); return; }
    clearTimeout(pollT); pollT=null;
    if(s.error){
      sayHtml('解析失败，未生成暂存：'+escHtml(s.error)+
        '　<a class="linkbtn" href="/tasks">查看详情</a>','err'); refresh(); return; }
    if(s.ready&&s.task_id){
      lastTaskId=s.task_id;
      sayHtml('解析完成，任务 #'+s.task_id+
        '　<a class="linkbtn" href="/review?task='+s.task_id+'">前往校验</a>','ok');
      hpicked=[]; renderPicked(); refresh();
    }
  }).catch(function(){ pollT=setTimeout(pollStatus,1500); });
}

/* ---- 状态卡数字口径 ---- */
function nums(){
  var busy=items.filter(function(t){
    return t.state==='parsing'||t.state==='pending';
  });
  var toExtract=items.filter(function(t){return t.state==='to_extract';});
  var reviewFiles=0, reviewTasks={}, loadTasks=[];
  led.forEach(function(t){
    if(t.task_state==='to_load'){ loadTasks.push(t); return; }
    if(t.task_state!=='to_review') return;
    (t.files||[]).forEach(function(f){
      if(f.pending_n+f.edited_n>0){ reviewFiles++; reviewTasks[t.task_id]=1; }
    });
  });
  var failed=items.filter(function(t){return t.state==='failed';});
  return {busy:busy, toExtract:toExtract, reviewFiles:reviewFiles,
    reviewTasks:Object.keys(reviewTasks).length,
    loadTasks:loadTasks, failed:failed};
}
function setCard(id,n,sub,zero){
  document.getElementById('n'+id).textContent=n;
  document.getElementById('s'+id).textContent=sub;
  document.getElementById('card'+id).classList.toggle('zero',!!zero);
}
function renderCards(){
  var v=nums();
  setCard(1, v.busy.length,
    v.busy.length?('任务 '+v.busy.map(function(t){return '#'+t.task_id;}).join('、')):'暂无进行中的解析任务',
    !v.busy.length);
  setCard(2, v.toExtract.length,
    v.toExtract.length? '解析完成，等待执行抽取（规则 '+tplCount+' 条）'
      : (tplCount? '暂无待抽取 · 已配置 '+tplCount+' 条抽取规则'
                 : '暂无待抽取 · 未配置规则，默认原始透传'),
    !v.toExtract.length);
  setCard(3, v.reviewTasks,
    v.reviewFiles? '共 '+v.reviewFiles+' 个资料待逐条核对':'暂无待校验记录', !v.reviewFiles);
  setCard(4, v.loadTasks.length,
    v.loadTasks.length? '校验完成，等待入库':'暂无待入库任务',
    !v.loadTasks.length);
  /* H1：只有 1 个待入库 → 点卡直接弹向导 */
  var l4=document.getElementById('l4');
  if(v.loadTasks.length===1){
    l4.textContent='立即入库 #'+v.loadTasks[0].task_id+' →';
    l4.onclick=function(e){ e.preventDefault(); startLoad(v.loadTasks[0].task_id); };
  }else{ l4.textContent='前往入库 →'; l4.onclick=null; }
  return v;
}

/* ---- 待办列表：需要你动手的，新在前，共用分页组件 ---- */
function fileNames(t){
  return (t.files||[]).map(function(f){return f.name;}).join('、');
}
function todoRow(seq,taskId,name,what,act,href,warn){
  return '<tr><td class="seq">'+seq+'</td>'+
    '<td class="mono">#'+taskId+'</td>'+
    '<td><span class="desc" title="'+escHtml(name)+'">'+escHtml(name||'—')+'</span></td>'+
    '<td class="'+(warn?'warn':'')+'">'+escHtml(what)+'</td>'+
    '<td style="white-space:nowrap">'+act+'</td></tr>';
}
function renderTodo(v){
  var rows=[];
  v.toExtract.forEach(function(t){
    rows.push({id:t.task_id,name:fileNames(t),
      what:'② 解析完成，待抽取',
      act:'<a class="linkbtn" href="/extract">前往抽取</a>',t:t.created_at});
  });
  led.forEach(function(t){
    if(t.task_state!=='to_review') return;
    var pend=0;
    (t.files||[]).forEach(function(f){ pend+=f.pending_n+f.edited_n; });
    if(pend>0) rows.push({id:t.task_id,name:fileNames(t),
      what:'③ 尚有 '+pend+' 条记录待校验',act:'<a class="linkbtn" href="/review?task='+
        t.task_id+'">前往校验</a>',t:t.created_at});
  });
  v.loadTasks.forEach(function(t){
    rows.push({id:t.task_id,name:fileNames(t),
      what:'④ 校验完成，待入库',
      act:'<button type="button" class="linkbtn" data-load="'+t.task_id+'">前往入库</button>',
      t:t.created_at});
  });
  v.busy.forEach(function(t){
    rows.push({id:t.task_id,name:fileNames(t),what:'① 解析中…',
      act:'<a class="linkbtn" href="/parse">查看进度</a>',t:t.created_at});
  });
  v.failed.forEach(function(t){
    rows.push({id:t.task_id,name:fileNames(t),
      what:'① 解析失败',
      act:'<a class="linkbtn" href="/tasks">查看详情</a>',t:t.created_at});
  });
  rows.sort(function(a,b){ return (a.t<b.t?1:(a.t>b.t?-1:0)); });
  var info=pageSlice(rows,todoPage,todoSize); todoPage=info.page;
  var tb=document.getElementById('todorows'), table=document.getElementById('todotable');
  var empty=document.getElementById('todoempty');
  empty.hidden=rows.length>0; table.hidden=rows.length===0;
  tb.innerHTML=info.rows.map(function(r,i){
    return todoRow(seqNo(info,i),r.id,r.name,r.what,r.act);
  }).join('');
  pgTodo.render(info);
}
document.getElementById('todorows').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-load]'):null;
  if(b) startLoad(Number(b.getAttribute('data-load')));
});

/* ---- 去入库＝四步向导（wizard.js 全站挂载，红线：④前不落库） ---- */
function startLoad(taskId){
  var t=items.filter(function(x){return x.task_id===taskId;})[0];
  openLoadWizard({taskId:taskId,
    ruleId:(t&&t.rule)?t.rule.rule_id:null,
    onDone:function(){ refresh(); }});
}

/* ---- 拉数 + 轮询（仅页面可见时，5s） ---- */
function render(){
  var v=renderCards();
  renderTodo(v);
}
function refresh(){
  Promise.all([
    fetch('/api/tasks').then(function(r){return r.json();}),
    fetch('/api/staging/ledger').then(function(r){return r.json();})
  ]).then(function(res){
    items=res[0].items||[]; led=res[1].items||[];
    render();
  }).catch(function(e){
    items=[]; led=[];
    render();
    say('平台库不可用：'+e.message,'err');
  });
}

refresh();
document.addEventListener('visibilitychange',function(){
  if(document.hidden){ clearTimeout(pollT); pollT=null; return; }
  loop();
});
function loop(){
  clearInterval(loopT);
  loopT=setInterval(function(){
    if(!document.hidden&&!hpicked.length) refresh();
  },5000);
}
loop();
