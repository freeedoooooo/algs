/* web/staging.js — 校验台（P1）：DB 暂存记录表 + 编辑/确认/拒绝
   + 源图血缘回溯。右侧舞台忠实复刻对照报告（report.js 舞台逻辑移植）：默认零框，
   悬停/点击揭示单格，点图走 hitCell 命中测试可定位任意记录行/格（不限选中行），
   窗口式翻页（全页预渲染、切页只切显隐，与报告同架构）、原图/矫正图切换、
   叠加框开关、光标跟随提示、全屏浮层、左右方向键翻页。
   匹配键用 data-i（记录序）/data-key（字段）。单击=血缘钉住，双击=改值（P1）。
   数据经 /api/tasks/<id>/staging|extract 读 DB；图片经 /files/<task_file_id>/…。 */
var task=new URLSearchParams(location.search).get('task')||'';
var curFile=new URLSearchParams(location.search).get('file')||'';
var taskDoc=null, records=[], keys=[], selIdx=-1, selKey=null, stateFilter='';
var pageMap={}, allAnchors=[], pagesPresent=[], curPage=null, curView=null, allOn=false;

function showErr(t){
  var e=document.getElementById('err');
  e.hidden=false; e.textContent=t;
}
function imgUrl(rel){
  return '/files/'+encodeURIComponent(curFile)+'/'+
    String(rel).split('/').map(encodeURIComponent).join('/');
}
function renderTabs(){
  var tabs=document.getElementById('filetabs');
  var files=(taskDoc&&taskDoc.files||[]).filter(function(f){return f.task_file_id;});
  if(files.length<2){ tabs.hidden=true; return; }
  tabs.hidden=false;
  tabs.innerHTML=files.map(function(f){
    return '<button type="button" class="ftab'+(String(f.task_file_id)===curFile?' on':'')+
      '" data-rf="'+f.task_file_id+'" title="'+escHtml(f.name)+'">'+
      escHtml(shortName(f.name))+'</button>';
  }).join('');
}
document.getElementById('filetabs').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-rf]'):null;
  if(!b) return;
  curFile=b.getAttribute('data-rf');
  history.replaceState(null,'','/review?task='+encodeURIComponent(task)+
    '&file='+encodeURIComponent(curFile));
  renderTabs(); loadStaging();
});

function collectKeys(){
  var seen={}, out=[];
  records.forEach(function(r){
    Object.keys(r.values||{}).forEach(function(k){
      if(!seen[k]){ seen[k]=true; out.push(k); }
    });
  });
  return out;
}
function readOnly(){
  return !!(taskDoc&&['loading','partial','loaded'].indexOf(taskDoc.state)>=0);
}
function recState(r){ return (r.review||{}).state||'pending'; }
function renderTable(){
  keys=collectKeys();
  var ro=readOnly();
  document.getElementById('rechead').innerHTML='<tr><th class="seq">序号</th>'+
    keys.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+
    '<th>状态</th>'+(ro?'':'<th>操作</th>')+'</tr>';
  var shown=0;
  document.getElementById('recrows').innerHTML=records.map(function(r,i){
    var st=recState(r);
    if(stateFilter&&st!==stateFilter) return '';
    shown++;
    var orig=r.original||{};
    return '<tr data-i="'+i+'"><td class="idx">'+((r.index==null?i:r.index)+1)+'</td>'+
      keys.map(function(k){
        var v=(r.values||{})[k];
        var ed=orig[k]!==undefined&&
          String(v==null?'':v)!==String(orig[k]==null?'':orig[k]);
        var tip=ed?('原值：'+orig[k]+'\n现值：'+(v==null?'':v)):(v==null?'':v);
        return '<td class="cell'+(ed?' edited':'')+'" data-i="'+i+'" data-key="'+
          escHtml(k)+'" title="'+escHtml(tip)+'">'+escHtml(v==null?'':v)+'</td>';
      }).join('')+
      '<td>'+stateBadge(st)+'</td>'+
      (ro?'':'<td class="acts">'+
        (st==='confirmed'?'':'<button type="button" class="rowbtn ok" data-act="confirmed" data-i="'+i+'" title="确认">✓</button>')+
        (st==='rejected'?'':'<button type="button" class="rowbtn no" data-act="rejected" data-i="'+i+'" title="拒绝">✗</button>')+
      '</td>')+'</tr>';
  }).join('');
  document.getElementById('empty').hidden=records.length>0;
  document.getElementById('summary').textContent=
    '共 '+records.length+' 条记录 · '+keys.length+' 个字段'+
    (stateFilter?(' · 筛选后 '+shown+' 条'):'')+
    ' · 点击图片定位记录，单击行或单元格高亮回溯框'+(ro?'':'，双击单元格修改取值');
  renderChips();
}
function renderChips(){
  var bar=document.getElementById('reviewbar');
  bar.hidden=!records.length;
  if(!records.length) return;
  var counts={pending:0,edited:0,confirmed:0,rejected:0};
  records.forEach(function(r){
    var s=recState(r); if(counts[s]!=null) counts[s]++;
  });
  var defs=[['','全部',records.length],['pending','待校验',counts.pending],
            ['edited','已修改',counts.edited],['confirmed','已确认',counts.confirmed],
            ['rejected','已拒绝',counts.rejected]];
  document.getElementById('chips').innerHTML=defs.map(function(d){
    return '<button type="button" class="chip'+(stateFilter===d[0]?' on':'')+
      '" data-state="'+d[0]+'">'+d[1]+' '+d[2]+'</button>';
  }).join('');
  var n=counts.pending+counts.edited, bb=document.getElementById('bulk-confirm');
  bb.textContent='确认全部待审 ('+n+')';
  bb.disabled=!n||readOnly();
}

/* ---- 右侧：源图舞台（复刻对照报告） ---- */
function buildAnchors(){
  allAnchors=[]; var pset={};
  records.forEach(function(r,i){
    var lin=r.lineage||{};
    keys.forEach(function(k){
      (lin[k]||[]).forEach(function(a){
        allAnchors.push({i:i, key:k, a:a});
        if(a.page!=null) pset[a.page]=true;
      });
    });
  });
  pagesPresent=Object.keys(pset).map(Number).sort(function(a,b){return a-b;});
}
function metaOf(p){ return pageMap[p]||null; }
function viewSize(meta,view){
  if(view==='rect') return meta.rectified_size||meta.size||[0,0];
  return meta.size||[0,0];
}
function recordNo(i){ var r=records[i]||{}; return (r.index==null?i:r.index)+1; }
function rowPages(i){
  var s={};
  allAnchors.forEach(function(x){ if(x.i===i&&x.a.page!=null) s[x.a.page]=true; });
  return Object.keys(s).map(Number).sort(function(a,b){return a-b;});
}
function anchorSpace(i,key){
  var t=allAnchors.filter(function(x){return x.i===i&&x.key===key&&x.a.cell_bbox;})[0];
  return t?t.a.space:'source';
}
function visibleView(){ return document.querySelector('#views .view:not([hidden])'); }
function rectsFor(i,key,view){
  var v=view||visibleView(); if(!v) return [];
  return v.querySelectorAll('.cellbox[data-i="'+i+'"][data-key="'+cssEsc(key)+'"]');
}
function rowRects(i,view){
  var v=view||visibleView(); if(!v) return [];
  return v.querySelectorAll('.cellbox[data-i="'+i+'"]');
}
function cellFor(i,key){
  return document.querySelector('#recrows td.cell[data-i="'+i+'"][data-key="'+cssEsc(key)+'"]');
}
function cssEsc(s){ return String(s).replace(/["\\]/g,'\\$&'); }

function viewHtml(meta,view,space,here,page){
  var sz=viewSize(meta,view), w=sz[0]||0, h=sz[1]||0;
  var src=view==='rect'?meta.rectified_image:meta.image;
  var ar=(w&&h)?(w/h):1.5;
  var rects='';
  here.forEach(function(x){
    var a=x.a, b=a.cell_bbox;
    if(a.space!==space||!b||b.length<4) return;
    rects+='<rect class="cellbox" data-i="'+x.i+'" data-key="'+escHtml(x.key)+
      '" x="'+b[0]+'" y="'+b[1]+'" width="'+Math.max(0,b[2]-b[0])+
      '" height="'+Math.max(0,b[3]-b[1])+'"><title>记录 #'+recordNo(x.i)+' · '+
      escHtml(x.key)+'&#10;'+escHtml(a.raw_text||'')+'</title></rect>';
  });
  return '<div class="view" data-page="'+page+'" data-view="'+view+'" data-space="'+space+'">'+
    '<div class="imgwrap" style="--ar:'+ar+'">'+
    '<img src="'+imgUrl(src)+'" width="'+w+'" height="'+h+
    '" alt="'+(view==='rect'?'矫正图':'原图')+'">'+
    '<svg class="cellsvg" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none">'+rects+'</svg>'+
    '<button type="button" class="boxtoggle'+(allOn?' on':'')+'">'+
    (allOn?'隐藏叠加框':'显示叠加框')+'</button>'+
    '</div></div>';
}
function initViewer(){
  selIdx=-1; selKey=null;
  var panel=document.getElementById('lineage');
  var first=pagesPresent.length?pagesPresent[0]:null;
  var meta=first!=null?metaOf(first):null;
  if(!meta||!meta.size){ panel.hidden=true; return; }
  curPage=first; curView=null;
  panel.hidden=false;
  buildViews();
  showPage(curPage);
}
/* 与报告同架构：所有页的视图一次性预渲染（图片只加载一次），
   切页只切显隐——不再 innerHTML 重建，杜绝「新图未加载→高度塌缩→翻页胶囊上跳」。 */
function buildViews(){
  var views=document.getElementById('views'), html='';
  pagesPresent.forEach(function(p){
    var meta=metaOf(p);
    if(!meta||!meta.size) return;
    var here=allAnchors.filter(function(x){return x.a.page===p;});
    html+=viewHtml(meta,'orig','source',here,p);
    if(meta.rectified_image) html+=viewHtml(meta,'rect','rectified',here,p);
  });
  views.innerHTML=html;
  views.querySelectorAll('img').forEach(function(im){
    im.addEventListener('load',alignPagers);
  });
}
function showPage(p){
  curPage=p;
  var meta=metaOf(curPage);
  var has=!!(meta&&meta.size);
  var views=document.getElementById('views');
  var vb=document.getElementById('viewbar');
  var hint=document.getElementById('lhint');
  if(!curView||(curView==='rect'&&!(has&&meta.rectified_image))) curView='orig';
  views.querySelectorAll('.view').forEach(function(v){
    v.hidden=!(has&&+v.getAttribute('data-page')===curPage&&
      v.getAttribute('data-view')===curView);
  });
  if(has&&meta.rectified_image){
    vb.hidden=false;
    vb.innerHTML='<button type="button" class="viewbtn'+(curView==='orig'?' on':'')+
      '" data-view="orig" title="原始上传图">原图</button>'+
      '<button type="button" class="viewbtn'+(curView==='rect'?' on':'')+
      '" data-view="rect" title="单元格坐标基准图">矫正图</button>';
  }else{ vb.innerHTML=''; vb.hidden=true; }
  var pg=document.getElementById('lpager');
  if(pagesPresent.length>1){
    pg.hidden=false;
    pg.setAttribute('data-pages',pagesPresent.join(','));
    document.getElementById('pgtotal').textContent=pagesPresent.length;
    renderPager();
  }else pg.hidden=true;
  var here=allAnchors.filter(function(x){return x.a.page===curPage;});
  var drawn=here.filter(function(x){
    return x.a.cell_bbox&&x.a.space===(curView==='rect'?'rectified':'source');}).length;
  if(!has){ hint.hidden=false;
    hint.textContent='该页无图像载体（纯文本输入），不支持叠加框回溯。';
    document.getElementById('lsub').textContent='';
  }else if(!allAnchors.length){ hint.hidden=false; hint.textContent='该记录暂无坐标信息。'; }
  else if(!drawn){ hint.hidden=false;
    hint.textContent='当前视图无回溯框：坐标位于'+(curView==='rect'?'原图':'矫正图')+'像素空间，请切换视图查看。'; }
  else hint.hidden=true;
  applySelection();
  alignPagers();
  updateHead();
}
function updateHead(){
  /* 选中记录号只在 lsub 显示一次，标题不重复 */
  document.getElementById('ltitle').textContent='血缘回溯';
  var meta=metaOf(curPage);
  document.getElementById('lsub').textContent=meta&&meta.size?
    ('页'+curPage+' · '+(curView==='rect'?'矫正图':'原图')+
      (selIdx>=0?(' · 选中记录 #'+recordNo(selIdx)):' · 全表')):'';
}
function applySelection(){
  document.querySelectorAll('#recrows tr').forEach(function(tr){
    tr.classList.toggle('sel',+tr.getAttribute('data-i')===selIdx);
  });
  if(allOn) document.querySelectorAll('#views .cellbox').forEach(function(r){r.classList.add('all');});
  if(selIdx<0) return;
  if(selKey!=null){
    var td=cellFor(selIdx,selKey); if(td) td.classList.add('pin');
    rectsFor(selIdx,selKey).forEach(function(r){r.classList.add('pin');});
  }else{
    rowRects(selIdx).forEach(function(r){r.classList.add('pin');});
  }
}
function clearHover(){
  document.querySelectorAll('#views .cellbox.hv,#recrows td.cell.hv').forEach(function(x){
    x.classList.remove('hv');});
}
function clearPin(){
  document.querySelectorAll('#views .cellbox.pin,#recrows td.cell.pin').forEach(function(x){
    x.classList.remove('pin');});
  document.querySelectorAll('#recrows tr.sel').forEach(function(tr){tr.classList.remove('sel');});
}
function clearSel(){ selIdx=-1; selKey=null; clearPin(); clearHover(); }
function markLeft(){
  document.querySelectorAll('#recrows tr').forEach(function(tr){
    tr.classList.toggle('sel',+tr.getAttribute('data-i')===selIdx);
  });
  if(selIdx>=0&&selKey!=null){
    var td=cellFor(selIdx,selKey);
    if(td) td.scrollIntoView({block:'nearest',inline:'nearest'});
  }
}
function setView(v){
  var meta=metaOf(curPage);
  if(v==='rect'&&!(meta&&meta.rectified_image)) return;
  curView=v;
  document.querySelectorAll('#viewbar .viewbtn').forEach(function(b){
    b.classList.toggle('on',b.getAttribute('data-view')===v);});
  document.querySelectorAll('#views .view').forEach(function(p){
    p.hidden=!(+p.getAttribute('data-page')===curPage&&
      p.getAttribute('data-view')===v);});
  clearHover(); applySelection(); alignPagers(); updateHead();
}
function ensureViewFor(space){
  var w=wantViewOf(space);
  if(curView!==w) setView(w);
}
function hoverCell(i,key,on){
  rectsFor(i,key).forEach(function(r){r.classList.toggle('hv',on);});
  var td=cellFor(i,key); if(td) td.classList.toggle('hv',on);
}
/* 钉住某行某字段：导航到该框所在页/视图，左侧定位到格，图上加重对应框 */
function pinField(key,i){
  if(i==null) i=selIdx;
  if(i<0||!records[i]) return;
  var target=allAnchors.filter(function(x){
    return x.i===i&&x.key===key&&x.a.cell_bbox;})[0];
  if(!target){ toast('该单元格没有图像坐标，无法回溯定位'); return; }
  selIdx=i; selKey=key;
  showLineage();
  if(target.a.page!==curPage){
    curView=wantViewOf(target.a.space); showPage(target.a.page);
  }else ensureViewFor(target.a.space);
  clearPin(); clearHover(); applySelection(); markLeft(); updateHead();
}
/* 点左侧行（非具体格）：加重该行全部框；若不在当前页则导航过去 */
function selectRecord(i){
  if(!records[i]) return;
  if(i===selIdx&&selKey==null){ clearSel(); updateHead(); return; }
  selIdx=i; selKey=null;
  showLineage();
  var rp=rowPages(i);
  if(rp.length&&rp.indexOf(curPage)<0){ showPage(rp[0]); }
  var a0=allAnchors.filter(function(x){return x.i===i&&x.a.cell_bbox;})[0];
  if(a0) ensureViewFor(a0.a.space);
  clearPin(); clearHover(); applySelection(); markLeft(); updateHead();
}
/* 收起＝右侧细竖条（不占表格宽度）：点竖条或点数据自动弹出。
   箭头方向即动作方向：展开态 › 折向右栏，收起态 ‹ 向左弹出。 */
function setCollapsed(on){
  var panel=document.getElementById('lineage');
  panel.classList.toggle('collapsed',on);
  var b=document.getElementById('ltoggle');
  b.textContent=on?'‹':'›';
  b.title=on?'展开血缘回溯':'收起血缘回溯';
  b.setAttribute('aria-expanded',on?'false':'true');
  if(on){ clearSel(); closeLb(); }else alignPagers();
}
function showLineage(){
  var panel=document.getElementById('lineage');
  if(panel.hidden) return;
  if(panel.classList.contains('collapsed')) setCollapsed(false);
}

/* ---- 事件委托（容器静态、内容动态重建，委托 survive rebuild） ---- */
/* 左侧表：点格钉住字段；点行选中整行；悬停双向高亮 */
document.getElementById('recrows').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('button[data-act]'):null;
  if(b){ e.stopPropagation();
    reviewRows([+b.getAttribute('data-i')],b.getAttribute('data-act')); return; }
  var td=e.target.closest?e.target.closest('td.cell'):null;
  if(td){ pinField(td.getAttribute('data-key'),+td.getAttribute('data-i')); return; }
  var tr=e.target.closest?e.target.closest('tr[data-i]'):null;
  if(tr) selectRecord(+tr.getAttribute('data-i'));
});
document.getElementById('recrows').addEventListener('mouseover',function(e){
  var td=e.target.closest?e.target.closest('td.cell'):null;
  if(td) hoverCell(+td.getAttribute('data-i'),td.getAttribute('data-key'),true);
});
document.getElementById('recrows').addEventListener('mouseout',function(e){
  var td=e.target.closest?e.target.closest('td.cell'):null;
  if(td) hoverCell(+td.getAttribute('data-i'),td.getAttribute('data-key'),false);
});

/* ---- P1 校验：双击改值 / ✓✗ / 筛选 / 批量确认 ---- */
document.getElementById('recrows').addEventListener('dblclick',function(e){
  if(readOnly()) return;
  var td=e.target.closest?e.target.closest('td.cell'):null;
  if(!td||td.querySelector('input')) return;
  startEdit(td);
});
function startEdit(td){
  var i=+td.getAttribute('data-i'),key=td.getAttribute('data-key');
  var r=records[i]; if(!r) return;
  var old=(r.values||{})[key]; old=old==null?'':String(old);
  var inp=document.createElement('input');
  inp.className='celledit'; inp.value=old;
  td.textContent=''; td.appendChild(inp); inp.focus(); inp.select();
  var done=false;
  function finish(commit){
    if(done) return; done=true;
    if(commit&&inp.value!==old) patchCell(i,key,inp.value);
    else{ renderTable(); applySelection(); }
  }
  inp.addEventListener('keydown',function(ev){
    ev.stopPropagation();
    if(ev.key==='Enter'){ ev.preventDefault(); finish(true); }
    else if(ev.key==='Escape'){ ev.preventDefault(); finish(false); }
  });
  inp.addEventListener('blur',function(){ finish(true); });
  inp.addEventListener('click',function(ev){ ev.stopPropagation(); });
}
function reviewBase(){
  return '/api/tasks/'+encodeURIComponent(task)+'/staging/'+encodeURIComponent(curFile);
}
function patchCell(i,key,val){
  var body={values:{}}; body.values[key]=val;
  var idx=records[i].index==null?i:records[i].index;
  fetch(reviewBase()+'/'+idx,{method:'PATCH',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
  }).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(o){
    if(!o.ok||!o.j.ok) toast('保存失败：'+((o.j&&o.j.error)||''));
    else{ records[i]=o.j.record; toast('已保存，记录转为「已修改」，请重新确认'); }
    renderTable(); applySelection();
  }).catch(function(e){ toast('保存失败：'+e); renderTable(); applySelection(); });
}
function reviewRows(idxs,state){
  var indexes=idxs.map(function(i){
    return records[i].index==null?i:records[i].index;
  });
  fetch(reviewBase()+'/review',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({indexes:indexes,state:state})
  }).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(o){
    if(!o.ok||!o.j.ok){ toast('操作失败：'+((o.j&&o.j.error)||'')); return; }
    idxs.forEach(function(i){
      records[i].review={state:state,at:(records[i].review||{}).at};
    });
    renderTable(); applySelection();
    toast((state==='confirmed'?'已确认 ':'已拒绝 ')+o.j.updated+' 条');
  }).catch(function(e){ toast('操作失败：'+e); });
}
document.getElementById('chips').addEventListener('click',function(e){
  var c=e.target.closest?e.target.closest('.chip'):null;
  if(!c) return;
  stateFilter=c.getAttribute('data-state');
  renderTable(); applySelection();
});
document.getElementById('bulk-confirm').addEventListener('click',function(){
  var idxs=[];
  records.forEach(function(r,i){
    var s=recState(r); if(s==='pending'||s==='edited') idxs.push(i);
  });
  if(!idxs.length||readOnly()) return;
  if(!confirm('确认当前文件全部待审记录（'+idxs.length+' 条）？\n含已修改但未确认的记录。')) return;
  reviewRows(idxs,'confirmed');
});
/* 右侧图框：可见态（悬停/钉住/整表网格）才可交互；悬停同步高亮，点击定位左侧 */
document.getElementById('views').addEventListener('mouseover',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(rc) hoverCell(+rc.getAttribute('data-i'),rc.getAttribute('data-key'),true);
});
document.getElementById('views').addEventListener('mouseout',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(rc) hoverCell(+rc.getAttribute('data-i'),rc.getAttribute('data-key'),false);
});
document.getElementById('views').addEventListener('click',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(rc){ e.stopPropagation(); pinField(rc.getAttribute('data-key'),+rc.getAttribute('data-i')); return; }
  var bt=e.target.closest?e.target.closest('.boxtoggle'):null;
  if(bt){ e.stopPropagation(); toggleBoxes(); }
});
function toggleBoxes(){
  allOn=!allOn;
  document.querySelectorAll('#views .boxtoggle').forEach(function(b){
    b.classList.toggle('on',allOn);
    b.textContent=allOn?'隐藏叠加框':'显示叠加框';});
  document.querySelectorAll('#views .cellbox').forEach(function(r){
    r.classList.toggle('all',allOn);});
}
/* 原图 / 矫正图切换 */
document.getElementById('viewbar').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-view]'):null;
  if(b) setView(b.getAttribute('data-view'));
});
/* 收起态整条竖栏可点展开；展开态只有「收起」钮触发折叠 */
document.querySelector('#lineage .lhead').addEventListener('click',function(e){
  var panel=document.getElementById('lineage');
  if(panel.classList.contains('collapsed')){ setCollapsed(false); return; }
  if(e.target.closest('#ltoggle')) setCollapsed(true);
});

/* ---- 窗口式翻页（公共件 pagerPages/renderPagerInto/alignPagerTo 在 stage.js） ---- */
function renderPager(){
  var pg=document.getElementById('lpager');
  renderPagerInto(pg,pagerPages(pg),curPage);
}
function alignPagers(){
  var pg=document.getElementById('lpager');
  if(pg.hidden) return;
  alignPagerTo(pg,document.getElementById('lstage'));
}
function goPage(p){
  if(pagesPresent.indexOf(p)<0) return;
  /* 与报告一致：切页保留当前视图（原图/矫正图），只清钉住/悬停 */
  clearSel(); showPage(p);
}
function curIndex(){
  var i=pagesPresent.indexOf(curPage); return i<0?0:i;
}
function goIndex(i){
  goPage(pagesPresent[Math.max(0,Math.min(pagesPresent.length-1,i))]);
}
document.getElementById('lpager').addEventListener('click',function(e){
  var num=e.target.closest?e.target.closest('.pg-num'):null;
  if(num){ goPage(+num.getAttribute('data-page')); return; }
  var btn=e.target.closest?e.target.closest('.pg-btn'):null;
  if(!btn||btn.disabled) return;
  var a=btn.getAttribute('data-pg'),i=curIndex();
  if(a==='first') goIndex(0);
  else if(a==='prev') goIndex(i-1);
  else if(a==='next') goIndex(i+1);
  else if(a==='last') goIndex(pagesPresent.length-1);
});
(function(){
  var jump=document.querySelector('#lpager .pg-jump');
  function doJump(){
    var v=parseInt(jump.value,10);
    if(isNaN(v)){ jump.value=pagesPresent[curIndex()]; return; }
    var i=pagesPresent.indexOf(v);
    if(i<0){ i=0; pagesPresent.forEach(function(p,k){
      if(Math.abs(p-v)<Math.abs(pagesPresent[i]-v)) i=k; }); }
    goIndex(i); jump.value=pagesPresent[curIndex()];
  }
  jump.addEventListener('keydown',function(e){
    e.stopPropagation();
    if(e.key==='Enter'){ e.preventDefault(); doJump(); jump.blur(); }
  });
  jump.addEventListener('blur',doJump);
  jump.addEventListener('click',function(e){ e.stopPropagation(); });
})();
window.addEventListener('resize',alignPagers);
/* 左右方向键翻页（与报告一致）：焦点在工作区（记录表/血缘侧栏）内且不在输入控件时生效 */
document.addEventListener('keydown',function(e){
  if(e.key!=='ArrowLeft'&&e.key!=='ArrowRight') return;
  var t=e.target;
  if(t&&(/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)||t.isContentEditable)) return;
  if(!(t&&t.closest&&t.closest('.stgwrap'))) return;
  if(pagesPresent.length<2) return;
  var i=curIndex(),ni=e.key==='ArrowLeft'?i-1:i+1;
  if(ni<0||ni>=pagesPresent.length) return;
  e.preventDefault();
  goIndex(ni);
});

/* ---- 全屏浮层（共享 lightbox 工厂 stage.js）：克隆当前 imgwrap，滚轮缩放/拖拽/框可点。
   差异走钩子：标题带页码+血缘语义；叠加框初始跟随整表开关 allOn，切换时同步克隆框 .all；
   点框关闭全屏后回左侧钉住对应记录行/格。 ---- */
var closeLb=function(){};
var stagingLb=bindStageLightbox({
  title:function(img,label){ return '页'+curPage+' · '+label+' · 血缘回溯框'; },
  boxesOnOpen:function(){ return allOn; },
  syncBoxes:function(on,content){
    content.querySelectorAll('.cellbox').forEach(function(r){r.classList.toggle('all',on);});
    document.getElementById('lbBoxes').classList.toggle('on',on);
  },
  onBoxClick:function(b){ pinField(b.getAttribute('data-key'),+b.getAttribute('data-i')); }
});
closeLb=stagingLb.close;
/* 点图行为跟随光标：悬停命中内容→十字光标单击定位，Alt+单击/空白→放大 */
var views=document.getElementById('views');
views.addEventListener('mousemove',function(e){
  var img=e.target.closest?e.target.closest('img'):null; if(!img) return;
  var hit=hitCell(img,e);
  var zoom=e.altKey||!hit;
  img.style.cursor=zoom?'zoom-in':'crosshair';
  var h=cursorHint();
  h.textContent=e.altKey?'单击：放大（Alt）':(hit?'单击：定位\nAlt + 单击：放大':'单击：放大');
  h.style.left=Math.min(e.clientX+14,window.innerWidth-h.offsetWidth-8)+'px';
  h.style.top=Math.min(e.clientY+18,window.innerHeight-h.offsetHeight-8)+'px';
  h.classList.add('on');
});
views.addEventListener('mouseout',function(e){
  var img=e.target.closest?e.target.closest('img'):null;
  if(img){ hideCursorHint(); img.style.cursor=''; }
});
views.addEventListener('click',function(e){
  var img=e.target.closest?e.target.closest('img'):null; if(!img) return;
  e.stopPropagation(); hideCursorHint();
  if(e.altKey){ stagingLb.open(img); return; }
  var hit=hitCell(img,e);
  if(hit){ pinField(hit.getAttribute('data-key'),+hit.getAttribute('data-i')); return; }
  stagingLb.open(img);
});

/* ---- 加载 ---- */
function loadStaging(){
  document.getElementById('err').hidden=true;
  var mb=document.getElementById('modebanner');
  var st=taskDoc&&taskDoc.state;
  if(st==='loading'){
    mb.className='banner info';
    mb.textContent='入库进行中 · 记录只读（完成后自动刷新）';
  }else if(st==='partial'){
    mb.className='banner warn';
    mb.textContent='任务部分入库 · 记录只读 · 可点击「重新入库」重试未写入记录';
  }else if(readOnly()){
    mb.className='banner warn';
    mb.textContent='任务已入库 · 记录只读，修改、确认、拒绝操作已锁定';
  }else{
    mb.className='banner info';
    mb.textContent='双击单元格修改取值，记录自动转为「已修改」；✓ 确认 · ✗ 拒绝；单击或悬停可查看血缘回溯';
  }
  updateLoadButtons();
  var u='/api/tasks/'+encodeURIComponent(task)+'/staging'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  var eu='/api/tasks/'+encodeURIComponent(task)+'/extract'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  Promise.all([
    fetch(u).then(function(r){
      if(!r.ok) return r.json().then(function(j){throw new Error(j.error||('HTTP '+r.status));});
      return r.json();
    }),
    fetch(eu).then(function(r){ return r.ok?r.json():null; }).catch(function(){return null;})
  ]).then(function(res){
    var doc=res[0], ex=res[1];
    pageMap={};
    ((ex&&ex.pages)||[]).forEach(function(p){ pageMap[p.index]=p; });
    var f=(doc.files||[])[0]||{};
    records=f.records||[];
    renderTable(); buildAnchors(); initViewer();
    var links=document.getElementById('filelinks');
    if(curFile){
      links.innerHTML='<a class="btn mini" target="_blank" href="'+
        fileUrl(curFile,'对照报告.html')+'">对照报告</a>';
    }else links.innerHTML='';
    var t=doc.template||{};
    document.getElementById('tplbadge').innerHTML=
      '<span class="badge blue">'+escHtml((t.name||'原始透传')+' v'+(t.version||1))+'</span>';
  }).catch(function(e){
    records=[]; renderTable(); buildAnchors(); initViewer();
    showErr('读取预览数据失败：'+e.message);
  });
}

/* ---- P2c 手动入库闸门：previewed/partial 可见；未绑定打开库向导（入库时
   选业务库＋规则），已绑定直接提交。门禁计数由后端 409 兜底，点击后轮询
   任务态直至入库完成自动刷新。 ---- */
var loadPoll=null;
function updateLoadButtons(){
  var lb=document.getElementById('loadbtn'), rb=document.getElementById('rcbtn');
  var t=taskDoc||{}, hasLoad=!!t.load;
  lb.hidden=!(t.state==='previewed'||t.state==='partial');
  lb.textContent=t.state==='partial'?'重新入库':'入库';
  rb.hidden=!(hasLoad&&(t.state==='loaded'||t.state==='partial'));
}
document.getElementById('loadbtn').onclick=function(){
  var t=taskDoc||{};
  if(!t.load&&t.state==='previewed'){
    openLoadWizard({taskId:task, templateId:(t.template||{}).template_id,
      getSample:function(){ return Promise.resolve(records.slice(0,3)); },
      onDone:function(){ loadStaging(); }});
    return;
  }
  var lb=this; lb.disabled=true;
  fetch('/api/tasks/'+encodeURIComponent(task)+'/load',{method:'POST'})
    .then(function(r){
      return r.json().catch(function(){return {};}).then(function(j){
        return {s:r.status,j:j};
      });
    }).then(function(o){
      lb.disabled=false;
      if(!o.j.ok){ showErr('无法入库：'+(o.j.error||('HTTP '+o.s))); return; }
      document.getElementById('err').hidden=true;
      var mb=document.getElementById('modebanner');
      mb.className='banner info';
      mb.textContent='入库进行中 · 记录只读（完成后自动刷新）';
      taskDoc.state='loading'; renderTable(); updateLoadButtons();
      clearInterval(loadPoll);
      loadPoll=setInterval(function(){
        fetch('/api/tasks/'+encodeURIComponent(task)).then(function(r){
          return r.json();
        }).then(function(j){
          if(!j.task) return;
          taskDoc=j.task;
          if(taskDoc.state!=='loading'){
            clearInterval(loadPoll); loadPoll=null;
            loadStaging();
          }
        }).catch(function(){});
      },1500);
    }).catch(function(){ lb.disabled=false; showErr('入库请求失败：平台库不可用'); });
};
document.getElementById('rcbtn').onclick=function(){ openReceiptDrawer(task); };

/* ---- 任务级台账（无 task 入口）：客户端搜索/筛选，与资料/任务页工具栏同构 ---- */
var ledgerItems=[], lq='',
    lprog=new URLSearchParams(location.search).get('prog')||'',
    ledPage=1, ledSize=getListPer();
var pgLed=bindPager(document.getElementById('ledpager'),function(d){
  ledPage+=d; renderLedger();
},function(n){ ledSize=n; ledPage=1; renderLedger(); });
function ledCnt(r){
  return '<td class="num">'+r.records_n+'</td>'+
    '<td class="num">'+r.pending_n+'</td>'+
    '<td class="num'+(r.edited_n?' led-edited':'')+'">'+r.edited_n+'</td>'+
    '<td class="num">'+r.confirmed_n+'</td>'+
    '<td class="num">'+r.rejected_n+'</td>';
}
function ledMatch(r){
  if(lprog==='todo'&&!(r.pending_n>0)) return false;
  if(lprog==='edited'&&!(r.edited_n>0)) return false;
  if(lprog==='done'&&r.pending_n>0) return false;
  if(lq){
    var tpl=r.template||{};
    var hay=(r.task_id+' '+(tpl.name||'')+' '+
      (r.files||[]).map(function(f){return f.name;}).join(' ')).toLowerCase();
    if(hay.indexOf(lq)<0) return false;
  }
  return true;
}
function renderLedger(){
  var list=ledgerItems.filter(ledMatch);
  var info=pageSlice(list,ledPage,ledSize);
  ledPage=info.page;
  document.getElementById('ledger').hidden=!list.length;
  var empty=document.getElementById('ledgerempty');
  empty.hidden=list.length>0;
  if(!list.length){
    empty.innerHTML=ledgerItems.length?
      '<b>无匹配任务</b>请调整搜索关键词或筛选条件。':
      '<b>暂无可校验的记录</b>请先到「解析」页上传文件。';
  }
  document.getElementById('ledgerrows').innerHTML=info.rows.map(function(r,i){
    var tpl=r.template||{};
    var main='<tr class="led-task" data-task="'+r.task_id+'" title="点击展开/收起文件子行">'+
      '<td class="seq">'+seqNo(info,i)+'</td>'+
      '<td class="mono"><span class="led-caret">▸</span>#'+r.task_id+'</td>'+
      '<td>'+r.files.length+' 个资料</td>'+
      '<td>'+escHtml((tpl.name||'原始透传')+' v'+(tpl.version||1))+'</td>'+
      ledCnt(r)+
      '<td>'+stateBadge(r.task_state)+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td></tr>';
    var subs=r.files.map(function(f){
      return '<tr class="led-file" data-task="'+r.task_id+'" data-file="'+
        f.task_file_id+'" hidden>'+
        '<td></td>'+
        '<td class="mono" title="资料ID（与入库回执中的「资料ID」一致）">资料 #'+f.task_file_id+'</td>'+
        '<td><span class="nm led-subname" title="'+escHtml(f.name)+'">'+
        escHtml(shortName(f.name))+'</span></td>'+
        '<td></td>'+ledCnt(f)+'<td></td><td></td></tr>';
    }).join('');
    return main+subs;
  }).join('');
  pgLed.render(info);
}

var tasktag=document.getElementById('tasktag');
tasktag.textContent=task?('任务 #'+task):'';
tasktag.hidden=!task;
document.getElementById('tasklink').href=task?('/tasks?task='+encodeURIComponent(task)):'/tasks';
/* 默认收起成细竖条：表格撑满全宽，点数据自动弹出（用户裁决） */
setCollapsed(true);
if(!task){
  /* 无任务参数＝台账入口：页头与资料/任务同构（标题＋右对齐工具栏，无返回），
     面板内直接表格。任务行汇总校验进度，点任务行展开文件子行，点子行进校验台。 */
  document.getElementById('modebanner').hidden=true;
  document.querySelector('.stgwrap').hidden=true;
  document.getElementById('summary').hidden=true;
  document.getElementById('taskpick').hidden=false;
  document.getElementById('tasklink').hidden=true;
  document.getElementById('filelinks').hidden=true;
  document.getElementById('tplbadge').hidden=true;
  document.getElementById('ledgerbar').hidden=false;
  document.querySelector('.pagehead h1').textContent='校验台账';
  document.getElementById('lq').addEventListener('input',function(){
    lq=this.value.trim().toLowerCase(); ledPage=1; renderLedger();
  });
  document.getElementById('lprog').onchange=function(){ lprog=this.value; ledPage=1; renderLedger(); };
  if(lprog) document.getElementById('lprog').value=lprog;   // ?prog=todo 深链（工作台）
  fetch('/api/staging/ledger').then(function(r){
    if(!r.ok) return r.json().then(function(j){throw new Error(j.error||('HTTP '+r.status));});
    return r.json();
  }).then(function(j){
    ledgerItems=j.items||[]; renderLedger();
  }).catch(function(e){ showErr('读取校验台账失败：'+e.message); });
}else{
  fetch('/api/tasks/'+encodeURIComponent(task)).then(function(r){
    if(!r.ok) throw new Error('任务不存在');
    return r.json();
  }).then(function(j){
    taskDoc=j.task;
    if(!curFile){
      var f=(taskDoc.files||[]).find(function(x){return x.task_file_id;});
      curFile=f?String(f.task_file_id):'';
    }
    renderTabs(); loadStaging();
  }).catch(function(e){ showErr(e.message); });
}

/* 台账：点任务行展开/收起其文件子行；点文件子行进入该文件的校验台 */
document.getElementById('ledgerrows').addEventListener('click',function(e){
  var tr=e.target.closest?e.target.closest('tr[data-task]'):null;
  if(!tr) return;
  if(tr.classList.contains('led-file')){
    location.href='/review?task='+tr.getAttribute('data-task')+
      '&file='+tr.getAttribute('data-file');
    return;
  }
  var open=tr.classList.toggle('open');
  var n=tr.nextElementSibling;
  while(n&&n.classList.contains('led-file')){
    n.hidden=!open; n=n.nextElementSibling;
  }
});