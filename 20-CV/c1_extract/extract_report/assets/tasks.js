/* extract_report/assets/tasks.js — 任务列表（task 表投影）+ 详情抽屉 + 处理中轮询 */
var items=[], curTask=null, pollTimer=null;
var rows=document.getElementById('rows'),empty=document.getElementById('empty');
var detail=document.getElementById('detail');

function tplLabel(t){
  t=t||{};
  return escHtml((t.name||'原始透传')+' v'+(t.version||1));
}
function filtered(){
  var q=document.getElementById('q').value.trim().toLowerCase();
  var st=document.getElementById('fstate').value;
  var md=document.getElementById('fmode').value;
  return items.filter(function(r){
    if(st&&r.state!==st) return false;
    if(md&&r.mode!==md) return false;
    if(q){
      var hay=(r.task_id+' '+(r.files||[]).map(function(f){return f.name;}).join(' ')).toLowerCase();
      if(hay.indexOf(q)<0) return false;
    }
    return true;
  });
}
function render(){
  var list=filtered();
  rows.innerHTML=list.map(function(r){
    return '<tr>'+
      '<td class="mono">#'+r.task_id+'</td>'+
      '<td class="num">'+(r.files||[]).length+'</td>'+
      '<td>'+tplLabel(r.template)+'</td>'+
      '<td>'+(r.mode==='load'?'入库':'预览')+'</td>'+
      '<td>'+stateBadge(r.state)+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td><button type="button" class="linkbtn" data-task="'+r.task_id+'">详情</button></td>'+
      '</tr>';
  }).join('');
  empty.hidden=list.length>0;
}
function load(){
  fetch('/api/tasks').then(function(r){return r.json();}).then(function(j){
    items=j.items||[]; render();
  }).catch(function(){ items=[]; render(); });
}
document.getElementById('q').addEventListener('input',render);
document.getElementById('fstate').onchange=render;
document.getElementById('fmode').onchange=render;
rows.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-task]'):null;
  if(b) openDetail(Number(b.getAttribute('data-task')));
});

/* ---- 详情抽屉 ---- */
function fileRow(f,taskId){
  var links='';
  if(f.task_file_id){
    links='<a class="linkbtn" target="_blank" href="/staging?task='+taskId+
      '&file='+f.task_file_id+'">预览数据</a>'+
      '<a class="linkbtn" target="_blank" href="'+fileUrl(f.task_file_id,'对照报告.html')+'">对照报告</a>';
  }
  return '<tr>'+
    '<td><span class="nm" title="'+escHtml(f.name)+'">'+escHtml(shortName(f.name))+'</span></td>'+
    '<td>'+stateBadge(f.state)+'</td>'+
    '<td class="num">'+(f.records_n==null?'—':f.records_n+' 条')+'</td>'+
    '<td style="white-space:nowrap">'+links+'</td></tr>';
}
function renderDetail(j){
  var r=j.task||{}, live=j.live;
  document.getElementById('dtitle').textContent='任务 #'+r.task_id;
  document.getElementById('dbadge').innerHTML=stateBadge(r.state);
  var html='';
  if(live&&live.running){
    html+='<div class="banner info">处理中 · '+escHtml(live.stage||'')+
      ' · '+(live.progress||0)+'%（自动刷新）</div>';
  }
  if(r.error) html+='<div class="banner err">出错：'+escHtml(r.error)+'</div>';
  html+='<div class="msg" style="margin-bottom:10px">模板 '+tplLabel(r.template)+
    ' · 模式 '+(r.mode==='load'?'入库':'预览')+
    ' · 发起 '+fmtTime(r.created_at)+'</div>';
  html+='<table class="list"><thead><tr><th>文件</th><th>状态</th><th>暂存记录</th><th>产物</th></tr></thead><tbody>'+
    (r.files||[]).map(function(f){return fileRow(f,r.task_id);}).join('')+'</tbody></table>';
  var ps=Object.keys(r.params||{});
  if(ps.length){
    html+='<details style="margin-top:12px"><summary class="msg" style="cursor:pointer">生效参数（'+ps.length+' 项）</summary>'+
      '<div class="mono" style="margin-top:6px;color:#5a6a85">'+
      ps.map(function(k){return escHtml(k)+'='+escHtml(r.params[k]);}).join('<br>')+
      '</div></details>';
  }
  document.getElementById('dbody').innerHTML=html;
  var n=(r.files||[]).reduce(function(s,f){return s+(f.records_n||0);},0);
  document.getElementById('dfoot').innerHTML=
    '<span>共 '+(r.files||[]).length+' 个文件 · 暂存记录 '+n+' 条</span><span class="spacer" style="flex:1"></span>'+
    '<span>校验编辑 P1 开放 · 入库 P2 开放</span>';
  clearTimeout(pollTimer);
  if(live&&live.running) pollTimer=setTimeout(function(){refreshDetail(r.task_id);},1500);
}
function refreshDetail(taskId){
  fetch('/api/tasks/'+taskId).then(function(r){
    if(!r.ok) throw new Error();
    return r.json();
  }).then(function(j){
    if(curTask!==taskId) return;
    renderDetail(j);
    var it=items.find(function(x){return x.task_id===taskId;});
    if(it&&j.task){ it.state=j.task.state; it.files=j.task.files; render(); }
  }).catch(function(){});
}
function openDetail(taskId){
  curTask=taskId; detail.hidden=false;
  document.getElementById('dbody').innerHTML='<div class="empty">加载中…</div>';
  refreshDetail(taskId);
}
function closeDetail(){
  curTask=null; detail.hidden=true; clearTimeout(pollTimer);
}
document.getElementById('dclose').onclick=closeDetail;
detail.addEventListener('click',function(e){ if(e.target===detail) closeDetail(); });
document.addEventListener('keydown',function(e){
  if(!detail.hidden&&e.key==='Escape') closeDetail();
});

load();
var focus=new URLSearchParams(location.search).get('task');
if(focus) openDetail(Number(focus));