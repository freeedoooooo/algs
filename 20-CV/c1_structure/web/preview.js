/* web/preview.js — 资料数据预览（P1）：DB 暂存记录表 + 编辑/确认/拒绝
   + 源图血缘回溯。右侧舞台忠实复刻对照报告（report.js 舞台逻辑移植）：默认零框，
   悬停/点击揭示单格，点图走 hitCell 命中测试可定位任意记录行/格（不限选中行），
   窗口式翻页（全页预渲染、切页只切显隐，与报告同架构）、原图/矫正图切换、
   叠加框开关、光标跟随提示、全屏浮层、左右方向键翻页。
   匹配键用 data-i（记录序）/data-key（字段）。单击=血缘钉住，双击=改值（P1）。
   数据经 /api/sources/<id>/staging|parse 读 DB；图片经 /files/<file_id>/…。 */
var file=new URLSearchParams(location.search).get('file')||'';
var curFile=file;
var traceRecord=new URLSearchParams(location.search).get('index')||'';
var traceKey=new URLSearchParams(location.search).get('key')||'';
var pendingTrace=null;
var embedMode=new URLSearchParams(location.search).get('embed')==='1';
var reviewView=new URLSearchParams(location.search).get('view')==='review';
var fileDoc=null, records=[], keys=[], selIdx=-1, selKey=null, stateFilter='';
var srcMap={};
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
  document.getElementById('filetabs').hidden=true;
}
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
  return !!(fileDoc&&['loading','loaded'].indexOf(fileDoc.state)>=0);
}
function recState(r){ return (r.review||{}).state||'pending'; }
/* 记录级徽标：pending 是「待校验」（与筛选 chips 一致），区别于资料级「待解析」 */
function recBadge(st){
  var m={pending:['待校验','gray'],edited:['已修改','yellow'],
         confirmed:['已确认','green'],rejected:['已拒绝','red']};
  var it=m[st]||[st,'gray'];
  return '<span class="badge '+it[1]+'">'+it[0]+'</span>';
}
/* 字段映射悬停说明：源列（名称或「第 N 列」）→ 目标字段 */
function srcNote(t,src){ return '映射：'+src+' → '+t; }
function renderTable(){
  keys=collectKeys();
  var ro=readOnly();
  document.getElementById('rechead').innerHTML='<tr><th class="seq">序号</th>'+
    keys.map(function(k){
      var s=srcMap[k];
      if(s===undefined) return '<th>'+escHtml(k)+'</th>';
      var cap='（'+(s||'未选源列')+'）';
      return '<th title="'+escHtml(s?srcNote(k,s):'抽取规则未选择源列')+'">'+
        escHtml(k)+'<span class="srccap'+(s?'':' none')+'">'+
        escHtml(cap)+'</span></th>';
    }).join('')+
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
        if(srcMap[k]) tip+='\n'+srcNote(k,srcMap[k]);
        return '<td class="cell'+(ed?' edited':'')+'" data-i="'+i+'" data-key="'+
          escHtml(k)+'" title="'+escHtml(tip)+'">'+escHtml(v==null?'':v)+'</td>';
      }).join('')+
      '<td>'+recBadge(st)+'</td>'+
      (ro?'':'<td class="acts">'+
        (st==='confirmed'?'':'<button type="button" class="rowbtn ok" data-act="confirmed" data-i="'+i+'" title="确认">✓</button>')+
        (st==='rejected'?'':'<button type="button" class="rowbtn no" data-act="rejected" data-i="'+i+'" title="拒绝">✗</button>')+
      '</td>')+'</tr>';
  }).join('');
  var em=document.getElementById('empty');
  em.hidden=records.length>0;
  if(records.length===0)
    em.innerHTML=(fileState()==='to_extract')?
      '<b>已解析 · 尚未抽取</b>该文件还没有生成暂存记录，点右上角「执行抽取」。':
      '<b>暂无解析记录</b>该文件尚无解析产物，或解析未完成。';
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
      escHtml(x.key)+'&#10;'+escHtml(a.raw_text||'')+
      (srcMap[x.key]?('&#10;'+escHtml(srcNote(x.key,srcMap[x.key]))):'')+
      '</title></rect>';
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
  var mk=Object.keys(srcMap).filter(function(k){return srcMap[k];});
  var lsub=document.getElementById('lsub');
  lsub.textContent=(meta&&meta.size?
    ('页'+curPage+' · '+(curView==='rect'?'矫正图':'原图')+
      (selIdx>=0?(' · 选中记录 #'+recordNo(selIdx)):' · 全表')):'')+
    (mk.length?(' · 映射 '+mk.map(function(k){return srcMap[k]+'→'+k;})
      .join('，')):'');
  lsub.title=mk.length?('字段映射：'+String.fromCharCode(10)+
    mk.map(function(k){return srcNote(k,srcMap[k]);})
    .join(String.fromCharCode(10))):'';
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
  /* embed=1：原图格子 → 数据看板左侧业务表的反向定位 */
  if(embedMode&&window.parent!==window){
    try{ window.parent.postMessage({c1PinField:{key:key,record_index:i}},'*'); }catch(e){}
  }
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
  /* embed=1：把折叠态同步给父页面（数据看板右侧面板跟着收窄/展开） */
  if(embedMode&&window.parent!==window){
    try{ window.parent.postMessage({c1LineageCollapsed:on},'*'); }catch(e){}
  }
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
  return '/api/sources/'+encodeURIComponent(file)+'/staging';
}
function patchCell(i,key,val){
  var body={values:{}}; body.values[key]=val;
  var idx=records[i].index==null?i:records[i].index;
  fetch(reviewBase()+'/'+idx,{method:'PATCH',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
  }).then(function(r){return r.json().then(function(j){return {ok:r.ok,j:j};});})
  .then(function(o){
    if(!o.ok||!o.j.ok) toast('保存失败：'+((o.j&&o.j.error)||''));
    else{
      records[i]=o.j.record;
      toast('已保存，记录转为「已修改」，请重新确认');
      if(o.j.file_state&&fileDoc) fileDoc.state=o.j.file_state;
      updateLoadButtons();
    }
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
    if(o.j.file_state&&fileDoc) fileDoc.state=o.j.file_state;
    updateLoadButtons();
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

/* 几何命中核心（页面 .view 用）：两级判定——
   ① 包含点的最小格框 rect；② 行带兜底（点击 y 落在哪条记录的坐标带内，x 不限）。 */
function stageHit(svg,img,e,space,p){
  if(!svg||!svg.viewBox||!svg.viewBox.baseVal||!svg.viewBox.baseVal.width||!img) return null;
  var vb=svg.viewBox.baseVal,r=img.getBoundingClientRect();
  if(!r.width||!r.height) return null;
  var x=(e.clientX-r.left)/r.width*vb.width,y=(e.clientY-r.top)/r.height*vb.height;
  var bestR=null,bestA=Infinity;
  Array.prototype.forEach.call(svg.querySelectorAll('.cellbox'),function(b){
    var bx=+b.getAttribute('x'),by=+b.getAttribute('y'),
        bw=+b.getAttribute('width'),bh=+b.getAttribute('height');
    if(x>=bx&&x<=bx+bw&&y>=by&&y<=by+bh&&bw*bh<bestA){bestA=bw*bh;bestR=b;}
  });
  var best=-1,bestD=Infinity;
  allAnchors.forEach(function(xa){
    var b=xa.a.cell_bbox;
    if(xa.a.page!==p||xa.a.space!==space||!b||b.length<4) return;
    if(y>=b[1]&&y<=b[3]){
      var d=Math.abs(y-(b[1]+b[3])/2);
      if(d<bestD){bestD=d;best=xa.i;}
    }
  });
  return {rect:bestR,row:best};
}
function hitRow(view,e){
  if(!view) return -1;
  var h=stageHit(view.querySelector('svg'),view.querySelector('img'),e,
    view.getAttribute('data-space'),+view.getAttribute('data-page'));
  return h?h.row:-1;
}

/* 当前页某坐标空间是否存在可画的回溯框（行带/命中判定的前置检查） */
function spaceWithAnchors(p,sp){
  return allAnchors.some(function(x){
    var a=x.a; return a.page===p&&a.space===sp&&a.cell_bbox&&a.cell_bbox.length>=4;});
}
/* 原图↔矫正图跨空间提示：本视图无框、对侧有框（坐标位于另一图像空间） */
function crossView(v){
  var sp=v&&v.getAttribute('data-space'); if(!sp) return false;
  var oth=sp==='source'?'rectified':'source';
  return spaceWithAnchors(curPage,oth)&&!spaceWithAnchors(curPage,sp);
}

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
  var v=img.closest('.view');
  var hit=hitCell(img,e);
  var row=!!(!hit&&hitRow(v,e)>=0);
  var cross=!hit&&!row&&crossView(v);
  var zoom=e.altKey||!(hit||row||cross);
  img.style.cursor=zoom?'zoom-in':'crosshair';
  var h=cursorHint();
  h.textContent=e.altKey?'单击：放大（Alt）':
    (hit?'单击：定位\nAlt + 单击：放大':
      (row?'单击：定位本行\nAlt + 单击：放大':
        (cross?'单击：定位（自动切到有框视图）\nAlt + 单击：放大':'单击：放大')));
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
  var v=img.closest('.view');
  var hit=hitCell(img,e);
  if(hit){ pinField(hit.getAttribute('data-key'),+hit.getAttribute('data-i')); return; }
  /* 映射转换后无框列/格间空白：行带兜底定位整行，回溯不再退化成纯放大 */
  var ri=hitRow(v,e);
  if(ri>=0){ selectRecord(ri); return; }
  /* 本视图坐标在对侧图像空间（如矫正图）：切视图后按同一屏幕位置重试 */
  if(crossView(v)){
    var sp=v.getAttribute('data-space');
    setView(wantViewOf(sp==='source'?'rectified':'source'));
    var nv=visibleView(), nimg=nv&&nv.querySelector('img');
    if(nimg){
      hit=hitCell(nimg,e);
      if(hit){ pinField(hit.getAttribute('data-key'),+hit.getAttribute('data-i')); return; }
      ri=hitRow(nv,e);
      if(ri>=0){ selectRecord(ri); return; }
    }
    return;
  }
  stagingLb.open(img);
});

/* ---- 加载 ---- */
function loadStaging(){
  document.getElementById('err').hidden=true;
  var mb=document.getElementById('modebanner');
  var st=fileDoc&&fileDoc.state;
  if(st==='loading'){
    mb.className='banner info';
    mb.textContent='入库进行中 · 记录只读（完成后自动刷新）';
  }else if(st==='to_load'&&fileDoc&&fileDoc.error){
    mb.className='banner warn';
    mb.textContent='上次入库未完成：'+fileDoc.error+' · 可点击「重新入库」重试';
  }else if(readOnly()){
    mb.className='banner warn';
    mb.textContent='任务已入库 · 记录只读，修改、确认、拒绝操作已锁定';
  }else{
    mb.className='banner info';
    mb.textContent='双击单元格修改取值，记录自动转为「已修改」；✓ 确认 · ✗ 拒绝；单击或悬停可查看血缘回溯；悬停列名/数据格/回溯框看字段映射';
  }
  updateLoadButtons();
  updateExButton();
  var u='/api/sources/'+encodeURIComponent(file)+'/staging';
  var eu='/api/sources/'+encodeURIComponent(file)+'/parse';
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
    srcMap=(doc.rule||{}).field_sources||{};
    if(reviewView&&!stateFilter){
      var rc={pending:0,edited:0,rejected:0};
      records.forEach(function(r){ var s=recState(r); if(rc[s]!=null) rc[s]++; });
      stateFilter=rc.pending?'pending':(rc.edited?'edited':(rc.rejected?'rejected':''));
      reviewView=false;   // 只做初始定位；后续由用户自由切筛选
    }
    renderTable(); buildAnchors(); initViewer();
    var wantIndex=traceRecord;
    if(traceRecord){
      var ti=records.findIndex(function(r){return String(r.index)===String(traceRecord);});
      if(ti>=0) selectRecord(ti);
      else toast('该 record_id 不在当前资料中');
      traceRecord='';
      history.replaceState(null,'',location.pathname+
        '?file='+encodeURIComponent(file)+
        (embedMode?'&embed=1':'')+
        (reviewView?'&view=review':''));
    }
    if(traceKey){
      var ki=records.findIndex(function(r){return String(r.index)===String(wantIndex);});
      if(ki>=0) pinField(traceKey,ki);
      else toast('该 record_id 不在当前资料中');
      traceKey='';
    }
    if(pendingTrace){
      var pi=records.findIndex(function(r){
        return String(r.index)===String(pendingTrace.index);
      });
      if(pi>=0) pinField(pendingTrace.key,pi);
      pendingTrace=null;
    }
    var links=document.getElementById('filelinks');
    if(curFile){
      links.innerHTML='<a class="btn mini" target="_blank" href="'+
        fileUrl(curFile,'对照报告.html')+'">对照报告</a>';
    }else links.innerHTML='';
    var t=doc.rule||{};
    document.getElementById('tplbadge').innerHTML=
      '<span class="badge blue">'+escHtml((t.name||'原始透传')+' v'+(t.version||1))+'</span>';
  }).catch(function(e){
    records=[]; srcMap={}; renderTable(); buildAnchors(); initViewer();
    showErr('读取预览数据失败：'+e.message);
  });
}

/* ---- P2c 手动入库闸门：to_load（派生态，全部记录已确认）可见；未绑定打开库向导（入库时
   选业务库＋规则），已绑定直接提交。入库前预检由后端 409 兜底，点击后轮询
   任务态直至入库完成自动刷新。 ---- */
var loadPoll=null;
function updateLoadButtons(){
  var lb=document.getElementById('loadbtn'), rb=document.getElementById('rcbtn');
  var t=fileDoc||{}, hasLoad=!!t.load;
  lb.hidden=!(t.state==='to_load');
  lb.textContent=t.error?'重新入库':'入库';
  rb.hidden=!(hasLoad&&(t.state==='loaded'||t.state==='to_load'));
}

/* ---- 抽取入口（数据预览页）：to_extract=执行抽取；to_review/to_load=
   重新抽取（先删后插覆盖校验结论，须确认）。按钮只作用当前文件页签。 ---- */
function fileState(){
  var f=(fileDoc&&fileDoc.files||[]).find(function(x){
    return String(x.file_id)===curFile;});
  return f&&f.state;
}
function updateExButton(){
  var b=document.getElementById('exbtn'), st=fileState();
  if(!curFile||['to_extract','to_review','to_load'].indexOf(st)<0||
     readOnly()){ b.hidden=true; renderExRule(true); return; }
  b.hidden=false;
  b.textContent=st==='to_extract'?'执行抽取':'重新抽取';
  renderExRule();
}
/* 抽取规则版本下拉（方案A）：默认＝任务已绑规则（未绑=原始透传）；
   选其他版本则本次抽取时后端改绑任务（set_rule）。 */
var rulesList=null, rulesLoading=false;
function renderExRule(hide){
  var sel=document.getElementById('exrule');
  if(hide){ sel.hidden=true; return; }
  sel.hidden=false;
  var bound=String((fileDoc&&fileDoc.rule||{}).version_id||'');
  if(!rulesList){
    if(!rulesLoading){ rulesLoading=true;
      fetch('/api/extract-rules').then(function(r){return r.json();})
        .then(function(j){ rulesList=j.items||[]; renderExRule(); })
        .catch(function(){ rulesList=[]; renderExRule(); });
    }
    sel.innerHTML='<option value="">默认（已绑定规则）</option>';
    return;
  }
  sel.innerHTML='<option value="">默认（已绑定规则）</option>'+
    rulesList.map(function(t){
      return '<option value="'+(t.current_version_id||'')+'">'+
        escHtml((t.name||'原始透传')+' v'+(t.current_version||1))+'</option>';
    }).join('');
  sel.value=bound;
  if(sel.selectedIndex<0) sel.selectedIndex=0;
}
document.getElementById('exbtn').onclick=function(){
  var b=this, st=fileState(), rv=document.getElementById('exrule').value;
  if(st!=='to_extract'&&!confirm('重新抽取将按所选抽取规则覆盖该文件全部暂存记录，已做的校验确认会清零。继续？'))return;
  b.disabled=true;
  fetch('/api/sources/'+encodeURIComponent(file)+'/extract',{
    method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({
                         force:st!=='to_extract',
                         rule_version_id:rv?Number(rv):null})
  }).then(function(r){
    return r.json().then(function(j){
      if(!r.ok) throw new Error(j.error||('HTTP '+r.status)); return j;});
  }).then(function(j){
    var n=(j.files||[]).reduce(function(s,f){return s+(f.records_n||0);},0);
    toast('抽取完成：生成 '+n+' 条记录');
    return fetch('/api/sources/'+encodeURIComponent(file)).then(function(r){
      return r.json();});
  }).then(function(j){
    fileDoc=j.file; loadStaging();
  }).catch(function(e){ showErr('抽取失败：'+e.message); })
  .then(function(){ b.disabled=false; });
};
document.getElementById('loadbtn').onclick=function(){
  var t=fileDoc||{};
  if(!t.load){
    openLoadWizard({fileId:file, ruleId:(t.rule||{}).rule_id,
      getSample:function(){ return Promise.resolve(records.slice(0,3)); },
      onDone:function(){ loadStaging(); }});
    return;
  }
  var lb=this; lb.disabled=true;
  fetch('/api/sources/'+encodeURIComponent(file)+'/load',{method:'POST'})
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
      fileDoc.state='loading'; renderTable(); updateLoadButtons();
      clearInterval(loadPoll);
      loadPoll=setInterval(function(){
        fetch('/api/sources/'+encodeURIComponent(file)).then(function(r){
          return r.json();
        }).then(function(j){
          if(!j.file) return;
          fileDoc=j.file;
          if(fileDoc.state!=='loading'){
            clearInterval(loadPoll); loadPoll=null;
            loadStaging();
          }
        }).catch(function(){});
      },1500);
    }).catch(function(){ lb.disabled=false; showErr('入库请求失败：平台库不可用'); });
};
document.getElementById('rcbtn').onclick=function(){ openReceiptDrawer(file); };

var filetag=document.getElementById('filetag');
filetag.textContent=file?('资料 #'+file):'';
filetag.hidden=!file;
document.getElementById('filelink').href='/sources';
/* 默认收起成细竖条：表格撑满全宽，点数据自动弹出（用户裁决）。
   embed=1（数据看板右侧血缘）：只留血缘面板、强制展开，不显示台账入口。 */
if(embedMode){
  document.body.classList.add('embed-lineage');
  setCollapsed(false);
}else setCollapsed(true);
/* 数据看板切单元格时不重建 iframe，只发消息让预览重新钉住对应格子 */
window.addEventListener('message',function(e){
  if(!e.data||!e.data.c1TraceKey) return;
  if(!records.length){ pendingTrace=e.data.c1TraceKey; return; }
  var ti=records.findIndex(function(r){
    return String(r.index)===String(e.data.c1TraceKey.index);
  });
  if(ti>=0) pinField(e.data.c1TraceKey.key,ti);
});
if(embedMode&&!file){
  document.getElementById('err').hidden=false;
  document.getElementById('err').textContent='缺少 file 参数';
}else if(!file){
  /* 无 file 参数：台账已迁到资料清单，直接跳转 */
  location.replace('/sources');
}else{
  fetch('/api/sources/'+encodeURIComponent(file)).then(function(r){
    if(!r.ok) throw new Error('资料不存在');
    return r.json();
  }).then(function(j){
    fileDoc=j.file;
    loadStaging();
  }).catch(function(e){ showErr(e.message); });
}

