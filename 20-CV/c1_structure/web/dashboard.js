/* web/dashboard.js — 数据看板：分页查询业务表 + 点行在右侧查看血缘（复用预览查看器） */
var qs=new URLSearchParams(location.search);
var ds=qs.get('ds')||'', table=qs.get('table')||'';
var page=1, perPage=100, lastData=null;
var TRACE=['file_id','record_id'];
var selRid=null;

function showErr(t){
  var e=document.getElementById('err');
  e.hidden=false; e.textContent=t;
}
function cellVal(v){ return v==null?'':String(v); }
function isTrace(c){ return TRACE.indexOf(c)>=0; }

function render(){
  if(!lastData) return;
  var allCols=lastData.columns||[], items=lastData.items||[];
  var cols=allCols.filter(function(c){return !isTrace(c);});
  document.getElementById('rowhead').innerHTML=
    '<th class="seq">序号</th>'+cols.map(function(c){
      return '<th>'+escHtml(c)+'</th>';
    }).join('');
  document.getElementById('rowbody').innerHTML=items.map(function(r,i){
    var rid=r.record_id;
    var attrs=rid!=null?(' data-rid="'+escHtml(rid)+'"'):'';
    var cls=(selRid!=null&&rid!=null&&String(rid)===String(selRid))?' class="sel"':'';
    return '<tr'+attrs+cls+'>'+
      '<td class="seq">'+((lastData.page-1)*lastData.per_page+i+1)+'</td>'+
      cols.map(function(c){ return '<td>'+escHtml(cellVal(r[c]))+'</td>'; }).join('')+
      '</tr>';
  }).join('');
  document.getElementById('rows').hidden=!items.length;
  document.getElementById('empty').hidden=!!items.length;
  var total=lastData.total||0;
  var pages=Math.max(1,Math.ceil(total/lastData.per_page));
  document.getElementById('total').textContent='共 '+total+' 行 · 第 '+page+' / '+pages+' 页';
  document.getElementById('pager').hidden=total<=lastData.per_page;
  document.getElementById('pginfo').textContent=page+' / '+pages;
  document.getElementById('pgprev').disabled=page<=1;
  document.getElementById('pgnext').disabled=page>=pages;
}

function load(){
  if(!ds||!table){ showErr('缺少业务库或表名参数，请从入库规则页的「目标表」链接进入'); return; }
  document.getElementById('err').hidden=true;
  closeLineage();
  var url='/api/load/datasources/'+encodeURIComponent(ds)+
    '/rows?table='+encodeURIComponent(table)+
    '&page='+page+'&per_page='+perPage;
  fetch(url).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(o){
    if(!o.ok||!o.j.ok){ showErr((o.j&&o.j.error)||'查询失败'); return; }
    lastData=o.j; render();
  }).catch(function(e){ showErr('查询失败：'+e); });
}

function closeLineage(){
  var panel=document.getElementById('lineagepanel');
  var frame=document.getElementById('linframe');
  panel.hidden=true; panel.classList.remove('collapsed');
  frame.hidden=true; frame.removeAttribute('src');
  selRid=null;
  document.querySelectorAll('#rowbody tr.sel').forEach(function(tr){tr.classList.remove('sel');});
}

function showLineage(rid,tr){
  var panel=document.getElementById('lineagepanel');
  var frame=document.getElementById('linframe');
  var msg=document.getElementById('linemsg');
  panel.hidden=false; msg.hidden=true; frame.hidden=true;
  panel.classList.remove('collapsed');
  selRid=String(rid);
  document.querySelectorAll('#rowbody tr.sel').forEach(function(x){x.classList.remove('sel');});
  if(tr) tr.classList.add('sel');
  fetch('/api/staging/locate/'+encodeURIComponent(rid)).then(function(r){
    return r.json().then(function(j){return {ok:r.ok,j:j};});
  }).then(function(o){
    if(!o.ok){
      msg.hidden=false;
      msg.textContent='该行无匹配暂存记录，无法溯源（可能非本平台入库、已被清理，或来自其他系统）。';
      return;
    }
    frame.src='/preview?embed=1&file='+encodeURIComponent(o.j.file_id)+
      '&index='+encodeURIComponent(o.j.record_index);
    frame.hidden=false;
  }).catch(function(e){
    msg.hidden=false; msg.textContent='溯源查询失败：'+e;
  });
}

document.getElementById('rowbody').addEventListener('click',function(e){
  var tr=e.target.closest?e.target.closest('tr[data-rid]'):null;
  if(tr) showLineage(tr.getAttribute('data-rid'),tr);
});
window.addEventListener('message',function(e){
  if(!e.data||typeof e.data.c1LineageCollapsed!=='boolean') return;
  var panel=document.getElementById('lineagepanel');
  if(panel.hidden) return;
  panel.classList.toggle('collapsed',e.data.c1LineageCollapsed);
});
document.getElementById('perpage').onchange=function(){
  perPage=Number(this.value)||100; page=1; load();
};
document.getElementById('pgprev').onclick=function(){
  if(page>1){ page--; load(); }
};
document.getElementById('pgnext').onclick=function(){
  if(!lastData) return;
  var pages=Math.ceil((lastData.total||0)/lastData.per_page);
  if(page<pages){ page++; load(); }
};
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){
    if(!document.getElementById('lineagepanel').hidden) closeLineage();
    else document.getElementById('err').hidden=true;
  }
});

document.getElementById('tabletag').textContent=table||'—';
if(ds) document.getElementById('backlink').href='/rules';
load();
