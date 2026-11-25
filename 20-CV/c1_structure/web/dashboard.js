/* web/dashboard.js — 数据看板：按资料文件筛选 + 分页查询业务表 + 点行看血缘 */
var qs=new URLSearchParams(location.search);
var ds=qs.get('ds')||'', table=qs.get('table')||'',
    fileId=qs.get('file')||'', lt=qs.get('lt')||'';
var page=1, perPage=getListPer(), lastData=null, selRid=null, pg=null;

function showErr(t){
  var e=document.getElementById('err');
  e.hidden=false; e.textContent=t;
}
function cellVal(v){ return v==null?'':String(v); }

function render(){
  if(!lastData) return;
  var allCols=lastData.columns||[], items=lastData.items||[];
  var cols=allCols.filter(function(c){return c!=='file_id'&&c!=='record_id';});
  var display=cols.slice();
  var at=display.indexOf('id');
  display.splice(at>=0?at+1:0,0,'__file_id__');
  var th=function(c){
    return c==='__file_id__'?'<th>资料ID</th>':'<th>'+escHtml(c)+'</th>';
  };
  document.getElementById('rowhead').innerHTML=
    '<th class="seq">序号</th>'+display.map(th).join('');
  document.getElementById('rowbody').innerHTML=items.map(function(r,i){
    var rid=r.record_id;
    var attrs=rid!=null?(' data-rid="'+escHtml(rid)+'"'):'';
    var cls=(selRid!=null&&rid!=null&&String(rid)===String(selRid))?' class="sel"':'';
    var td=function(c){
      if(c==='__file_id__') return '<td class="num">'+
        (r.file_id==null?'-':escHtml(String(r.file_id)))+'</td>';
      return '<td>'+escHtml(cellVal(r[c]))+'</td>';
    };
    return '<tr'+attrs+cls+'>'+
      '<td class="seq">'+((lastData.page-1)*lastData.per_page+i+1)+'</td>'+
      display.map(td).join('')+'</tr>';
  }).join('');
  document.getElementById('rows').hidden=!items.length;
  document.getElementById('empty').hidden=!!items.length;
  page=lastData.page;
  var total=lastData.total||0;
  var pages=Math.max(1,Math.ceil(total/lastData.per_page));
  document.getElementById('total').textContent=
    '共 '+total+' 行 · 第 '+page+' / '+pages+' 页';
  pg.render({page:page,pages:pages,total:total,per:lastData.per_page});
}

function load(){
  if(!ds||!table){ showErr('缺少业务库或表名参数，请从资料详情的「查看数据看板」进入'); return; }
  document.getElementById('err').hidden=true;
  closeLineage();
  var url='/api/load/datasources/'+encodeURIComponent(ds)+
    '/rows?table='+encodeURIComponent(table)+
    '&page='+page+'&per_page='+perPage;
  if(fileId) url+='&file_id='+encodeURIComponent(fileId);
  fetch(url).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(o){
    if(!o.ok||!o.j.ok){ showErr((o.j&&o.j.error)||'查询失败'); return; }
    lastData=o.j; render();
  }).catch(function(e){ showErr('查询失败：'+e); });
}

function loadFiles(){
  var sel=document.getElementById('filesel');
  sel.onchange=function(){ fileId=this.value; page=1; syncTag(); load(); };
  fetch('/api/sources/state').then(function(r){return r.json();}).then(function(j){
    var items=(j.items||[]).filter(function(f){
      return !!f.load_table_id && (!lt||String(f.load_table_id)===String(lt));
    });
    var html='<option value="">全部资料</option>'+items.map(function(f){
      return '<option value="'+escHtml(String(f.id))+'">#'+escHtml(String(f.id))+
        ' · '+escHtml(f.name||'未命名资料')+'</option>';
    }).join('');
    if(fileId&&!items.some(function(f){return String(f.id)===String(fileId);})){
      html+='<option value="'+escHtml(fileId)+'">#'+escHtml(fileId)+' · 当前资料</option>';
    }
    sel.innerHTML=html; sel.value=fileId;
  }).catch(function(){
    sel.innerHTML='<option value="">全部资料</option>'+
      (fileId?'<option value="'+escHtml(fileId)+'">#'+escHtml(fileId)+
       ' · 当前资料</option>':'');
    sel.value=fileId;
  });
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
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'){
    if(!document.getElementById('lineagepanel').hidden) closeLineage();
    else document.getElementById('err').hidden=true;
  }
});

pg=bindPager(document.getElementById('pager'),
  function(d){ page+=d; load(); },
  function(n){ perPage=n; page=1; load(); });
function syncTag(){
  document.getElementById('tabletag').textContent=
    (table||'—')+(fileId?(' · 资料 #'+fileId):'');
}
syncTag();
if(ds) document.getElementById('backlink').href='/rules';
loadFiles();
load();
