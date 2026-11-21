/* extract_report/assets/staging.js — 校验台（P1）：DB 暂存记录表 + 编辑/确认/拒绝
   + 源图血缘回溯。右侧舞台忠实复刻对照报告（report.js 舞台逻辑移植）：默认零框，
   悬停/点击揭示单格，点图走 hitCell 命中测试可定位任意记录行/格（不限选中行），
   窗口式翻页、原图/矫正图切换、叠加框开关、光标跟随提示、全屏浮层。
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
  history.replaceState(null,'','/staging?task='+encodeURIComponent(task)+
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
function readOnly(){ return !!(taskDoc&&taskDoc.state==='loaded'); }
function recState(r){ return (r.review||{}).state||'pending'; }
function renderTable(){
  keys=collectKeys();
  var ro=readOnly();
  document.getElementById('rechead').innerHTML='<tr><th>#</th>'+
    keys.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+
    '<th>状态</th>'+(ro?'':'<th>操作</th>')+'</tr>';
  var shown=0;
  document.getElementById('recrows').innerHTML=records.map(function(r,i){
    var st=recState(r);
    if(stateFilter&&st!==stateFilter) return '';
    shown++;
    var orig=r.original||{};
    return '<tr data-i="'+i+'"><td class="idx">'+(r.index==null?i:r.index)+'</td>'+
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
    ' · 点图定位记录，点行/格高亮回溯框'+(ro?'':'，双击格改值');
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
function recordNo(i){ var r=records[i]||{}; return r.index==null?i:r.index; }
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

function viewHtml(meta,view,space,here){
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
  return '<div class="view" data-view="'+view+'" data-space="'+space+'">'+
    '<div class="imgwrap" style="--ar:'+ar+'">'+
    '<img src="'+imgUrl(src)+'" alt="'+(view==='rect'?'矫正图':'原图')+'">'+
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
  renderViewer();
}
function renderViewer(){
  var meta=metaOf(curPage);
  var views=document.getElementById('views');
  var vb=document.getElementById('viewbar');
  var hint=document.getElementById('lhint');
  var here=allAnchors.filter(function(x){return x.a.page===curPage;});
  if(!meta||!meta.size){
    views.innerHTML=''; vb.innerHTML=''; vb.hidden=true;
    document.getElementById('lpager').hidden=true;
    hint.hidden=false; hint.textContent='该页无图像载体（纯文本输入），无法叠框回溯。';
    document.getElementById('lsub').textContent='';
    return;
  }
  if(!curView||(curView==='rect'&&!meta.rectified_image)) curView='orig';
  var html=viewHtml(meta,'orig','source',here);
  if(meta.rectified_image) html+=viewHtml(meta,'rect','rectified',here);
  views.innerHTML=html;
  if(meta.rectified_image){
    vb.hidden=false;
    vb.innerHTML='<button type="button" class="viewbtn'+(curView==='orig'?' on':'')+
      '" data-view="orig" title="原始上传图">原图</button>'+
      '<button type="button" class="viewbtn'+(curView==='rect'?' on':'')+
      '" data-view="rect" title="单元格坐标基准图">矫正图</button>';
  }else{ vb.innerHTML=''; vb.hidden=true; }
  views.querySelectorAll('.view').forEach(function(v){
    v.hidden=(v.getAttribute('data-view')!==curView);
  });
  var pg=document.getElementById('lpager');
  if(pagesPresent.length>1){
    pg.hidden=false;
    pg.setAttribute('data-pages',pagesPresent.join(','));
    document.getElementById('pgtotal').textContent=pagesPresent.length;
    renderPager();
  }else pg.hidden=true;
  var drawn=here.filter(function(x){
    return x.a.cell_bbox&&x.a.space===(curView==='rect'?'rectified':'source');}).length;
  if(!allAnchors.length){ hint.hidden=false; hint.textContent='无坐标血缘。'; }
  else if(!drawn){ hint.hidden=false;
    hint.textContent='当前视图无回溯框：坐标在'+(curView==='rect'?'原图':'矫正图')+'空间，切换视图查看。'; }
  else hint.hidden=true;
  applySelection();
  /* 图片加载完成后才有真实高度：首次打开/切页时 img 尚未 load，imgwrap 高度≈0
     会把翻页胶囊锚得偏上挡住文字。与报告一致绑 load→alignPagers，加载完再精确锚定。 */
  views.querySelectorAll('img').forEach(function(im){
    im.addEventListener('load',alignPagers);
  });
  alignPagers();
  updateHead();
}
function updateHead(){
  document.getElementById('ltitle').textContent=
    selIdx>=0?('记录 #'+recordNo(selIdx)+' 血缘回溯'):'血缘回溯 · 全表';
  var meta=metaOf(curPage);
  document.getElementById('lsub').textContent=meta&&meta.size?
    ('页'+curPage+' · '+(curView==='rect'?'矫正图':'原图')+
      (selIdx>=0?(' · 选中记录 #'+recordNo(selIdx)):'')):'';
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
    p.hidden=(p.getAttribute('data-view')!==v);});
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
  if(!target){ toast('该单元格没有图像坐标，无法回溯到图'); return; }
  selIdx=i; selKey=key;
  if(target.a.page!==curPage){
    curPage=target.a.page; curView=wantViewOf(target.a.space); renderViewer();
  }else ensureViewFor(target.a.space);
  clearPin(); clearHover(); applySelection(); markLeft(); updateHead();
}
/* 点左侧行（非具体格）：加重该行全部框；若不在当前页则导航过去 */
function selectRecord(i){
  if(!records[i]) return;
  if(i===selIdx&&selKey==null){ clearSel(); updateHead(); return; }
  selIdx=i; selKey=null;
  var rp=rowPages(i);
  if(rp.length&&rp.indexOf(curPage)<0){ curPage=rp[0]; curView=null; renderViewer(); }
  clearPin(); clearHover(); applySelection(); markLeft(); updateHead();
}
function hideLineage(){
  clearSel();
  document.getElementById('lineage').hidden=true;
  closeLb();
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
    else{ records[i]=o.j.record; toast('已保存 · 转为已修改，须重新确认'); }
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
document.getElementById('lclose').onclick=hideLineage;

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
  curPage=p; curView=null; clearSel(); renderViewer();
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
  if(readOnly()){
    mb.className='banner warn';
    mb.textContent='任务已入库 · 记录只读（改值 / 确认 / 拒绝已锁定）';
  }else{
    mb.className='banner info';
    mb.textContent='双击单元格改值（自动转已修改）· ✓ 确认 · ✗ 拒绝 · 单击/悬停血缘回溯不变';
  }
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
      links.innerHTML='<a class="linkbtn" target="_blank" href="'+
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

document.getElementById('tasktag').textContent=task?('任务 #'+task):'（未指定任务）';
document.getElementById('tasklink').href=task?('/tasks?task='+encodeURIComponent(task)):'/tasks';
if(!task){
  /* 无任务参数：校验台独立入口，渲染任务选择器（/api/tasks 新任务在前） */
  document.getElementById('modebanner').hidden=true;
  document.getElementById('taskpick').hidden=false;
  fetch('/api/tasks').then(function(r){return r.json();}).then(function(j){
    var sel=document.getElementById('picksel'), items=j.items||[];
    if(!items.length){ sel.innerHTML='<option value="">暂无任务</option>'; return; }
    sel.innerHTML='<option value="">请选择…</option>'+items.map(function(t){
      var tpl=t.template||{};
      return '<option value="'+t.task_id+'">#'+t.task_id+' · '+
        escHtml(tpl.name||'')+' v'+(tpl.version||1)+' · '+
        ((STATE_LABEL[t.state]||[t.state||'—'])[0])+' · '+(t.files||[]).length+' 文件</option>';
    }).join('');
    sel.addEventListener('change',function(){
      if(sel.value) location.href='/staging?task='+encodeURIComponent(sel.value);
    });
  }).catch(function(e){ showErr('读取任务列表失败：'+e.message); });
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

/* 跨任务搜索：/api/staging/query 直查 DB field 投影，与当前任务无关 */
(function(){
  var go=document.getElementById('xs-go');
  if(!go) return;
  go.addEventListener('click',function(){
    var p=new URLSearchParams();
    var f=document.getElementById('xs-field').value.trim();
    var q=document.getElementById('xs-q').value.trim();
    var st=document.getElementById('xs-state').value;
    if(f) p.set('field',f);
    if(q) p.set('q',q);
    if(st) p.set('state',st);
    var err=document.getElementById('xs-err');
    err.hidden=true;
    fetch('/api/staging/query?'+p.toString()).then(function(r){
      return r.json().then(function(j){ return {status:r.status,j:j}; });
    }).then(function(o){
      var tbl=document.getElementById('xs-table'),
          em=document.getElementById('xs-empty'),
          tb=document.getElementById('xs-rows');
      if(o.status!==200||!o.j.ok){
        err.textContent=(o.j&&o.j.error)||('查询失败 HTTP '+o.status);
        err.hidden=false; tbl.hidden=true; em.hidden=true; return;
      }
      var items=o.j.items||[];
      tb.innerHTML=items.map(function(it){
        return '<tr><td class="mono">#'+it.task_id+'</td><td>'+
          escHtml(it.source_name)+'</td><td class="num">'+it.record_index+
          '</td><td>'+escHtml(it.field_name)+'</td><td>'+
          escHtml(it.value_text)+'</td><td>'+escHtml(it.review_state)+
          '</td><td><a class="btn ghost mini" href="/staging?task='+
          it.task_id+'&file='+it.task_file_id+'">预览</a></td></tr>';
      }).join('');
      tbl.hidden=!items.length;
      em.hidden=!!items.length;
    }).catch(function(e){
      err.textContent='查询失败：'+e; err.hidden=false;
    });
  });
})();