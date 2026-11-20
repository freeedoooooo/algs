/* extract_report/assets/staging.js — 数据预览：records.json 记录表 + 源图血缘回溯。
   右侧舞台忠实复刻对照报告（report.js 舞台逻辑移植）：默认零框，悬停/点击揭示单格，
   点图走 hitCell 命中测试可定位任意记录行/格（不限选中行），窗口式翻页、原图/矫正图
   切换、叠加框开关、光标跟随提示、全屏浮层。匹配键用 data-i（记录序）/data-key（字段）。
   数据全部来自预生成文件（records.json + extract.json），不依赖平台库。 */
var batch=new URLSearchParams(location.search).get('batch')||'';
var curFile=new URLSearchParams(location.search).get('file')||'';
var runDoc=null, records=[], keys=[], selIdx=-1, selKey=null;
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
  var files=(runDoc&&runDoc.files||[]).filter(function(f){return f.case;});
  if(files.length<2){ tabs.hidden=true; return; }
  tabs.hidden=false;
  tabs.innerHTML=files.map(function(f){
    return '<button type="button" class="ftab'+(f.case===curFile?' on':'')+
      '" data-case="'+escHtml(f.case)+'" title="'+escHtml(f.name)+'">'+
      escHtml(shortName(f.name))+'</button>';
  }).join('');
}
document.getElementById('filetabs').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-case]'):null;
  if(!b) return;
  curFile=b.getAttribute('data-case');
  history.replaceState(null,'','/staging?batch='+encodeURIComponent(batch)+
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
function renderTable(){
  keys=collectKeys();
  document.getElementById('rechead').innerHTML='<tr><th>#</th>'+
    keys.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+
    '<th>状态</th></tr>';
  document.getElementById('recrows').innerHTML=records.map(function(r,i){
    return '<tr data-i="'+i+'"><td class="idx">'+(r.index==null?i:r.index)+'</td>'+
      keys.map(function(k){
        var v=(r.values||{})[k];
        return '<td class="cell" data-i="'+i+'" data-key="'+escHtml(k)+'" title="'+
          escHtml(v)+'">'+escHtml(v==null?'':v)+'</td>';
      }).join('')+
      '<td>'+stateBadge((r.review||{}).state||'pending')+'</td></tr>';
  }).join('');
  document.getElementById('empty').hidden=records.length>0;
  document.getElementById('summary').textContent=
    '共 '+records.length+' 条记录 · '+keys.length+' 个字段 · 点图定位记录，点行/格高亮回溯框';
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
function wantViewOf(space){ return space==='rectified'?'rect':'orig'; }
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

/* ---- 窗口式翻页（移植 report.js renderPager / alignPagers） ---- */
function pagerPages(pg){
  return (pg.getAttribute('data-pages')||'').split(',').filter(Boolean).map(Number);
}
function renderPager(){
  var pg=document.getElementById('lpager');
  var pages=pagerPages(pg);
  var ci=pages.indexOf(curPage); if(ci<0) ci=0;
  var html='',last=-1;
  pages.forEach(function(p,i){
    if(!(i===0||i===pages.length-1||Math.abs(i-ci)<=1)) return;
    if(last>=0&&i-last>1) html+='<span class="pg-gap">…</span>';
    html+='<button type="button" class="pg-num'+(i===ci?' on':'')+
      '" data-page="'+p+'" title="第 '+p+' 页">'+p+'</button>';
    last=i;
  });
  pg.querySelector('.pg-nums').innerHTML=html;
  pg.querySelector('[data-pg="first"]').disabled=(ci===0);
  pg.querySelector('[data-pg="prev"]').disabled=(ci===0);
  pg.querySelector('[data-pg="next"]').disabled=(ci===pages.length-1);
  pg.querySelector('[data-pg="last"]').disabled=(ci===pages.length-1);
  var jump=pg.querySelector('.pg-jump');
  if(document.activeElement!==jump) jump.value=pages[ci];
}
function alignPagers(){
  var pg=document.getElementById('lpager');
  if(pg.hidden) return;
  var stage=document.getElementById('lstage');
  var iw=stage.querySelector('.view:not([hidden]) .imgwrap');
  if(!iw) return;
  var sr=stage.getBoundingClientRect(),ir=iw.getBoundingClientRect();
  if(!ir.width) return;
  pg.style.left=Math.round(ir.left-sr.left+ir.width/2)+'px';
  pg.style.bottom=Math.max(6,Math.round(sr.bottom-ir.bottom+8))+'px';
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

/* ---- 追溯失败轻提示 + 光标跟随提示（移植 report.js） ---- */
var toastEl=null,toastTimer=null;
function toast(msg){
  if(!toastEl){ toastEl=document.createElement('div'); toastEl.id='trace-toast';
    document.body.appendChild(toastEl); }
  toastEl.textContent=msg; toastEl.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(function(){toastEl.classList.remove('on');},2400);
}
var hintEl=null;
function cursorHint(){
  if(!hintEl){ hintEl=document.createElement('div'); hintEl.id='cursor-hint';
    document.body.appendChild(hintEl); }
  return hintEl;
}
function hideCursorHint(){ if(hintEl) hintEl.classList.remove('on'); }

/* 图片点击命中测试（移植 report.js hitCell）：按 viewBox 1:1 换算，同级重叠取面积最小者。
   叠加框隐藏时也生效——据此点图可定位任意记录行/格，无需默认叠全表框。 */
function hitCell(img,e){
  var view=img.closest('.view');
  var svg=view&&view.querySelector('.cellsvg');
  if(!svg||!svg.viewBox||!svg.viewBox.baseVal||!svg.viewBox.baseVal.width) return null;
  var vb=svg.viewBox.baseVal,r=img.getBoundingClientRect();
  if(!r.width||!r.height) return null;
  var x=(e.clientX-r.left)/r.width*vb.width,y=(e.clientY-r.top)/r.height*vb.height;
  var best=null,bestA=Infinity;
  svg.querySelectorAll('.cellbox').forEach(function(b){
    var bx=+b.getAttribute('x'),by=+b.getAttribute('y'),
        bw=+b.getAttribute('width'),bh=+b.getAttribute('height');
    if(x>=bx&&x<=bx+bw&&y>=by&&y<=by+bh&&bw*bh<bestA){bestA=bw*bh;best=b;}
  });
  return best;
}

/* ---- 全屏浮层（移植 report.js lightbox）：克隆当前 imgwrap，滚轮缩放/拖拽/框可点 ---- */
var closeLb=function(){};
(function(){
  var lb=document.getElementById('lightbox');
  var stage=document.getElementById('lbStage');
  var content=document.getElementById('lbContent');
  var scaleEl=document.getElementById('lbScale');
  var titleEl=document.getElementById('lbTitle');
  var openBtn=document.getElementById('lbOpen');
  var boxesBtn=document.getElementById('lbBoxes');
  if(!lb||!stage||!content) return;
  var scale=1,fit=1,tx=0,ty=0,imgW=0,imgH=0,drag=null,moved=false;
  function apply(){
    content.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')';
    scaleEl.textContent=Math.round(scale*100)+'%';
  }
  function clamp(v){return Math.max(fit*0.3,Math.min(12,v));}
  function setScale(v,mx,my){
    var old=scale;scale=clamp(v);
    if(mx!==undefined){ tx=mx-(mx-tx)*(scale/old); ty=my-(my-ty)*(scale/old); }
    apply();
  }
  function fitWindow(){
    var r=stage.getBoundingClientRect();
    fit=Math.min(r.width/imgW,r.height/imgH)*0.94;
    if(!isFinite(fit)||fit<=0) fit=1;
    scale=fit;tx=0;ty=0;apply();
  }
  function setLbBoxes(on){
    lb.classList.toggle('lb-noboxes',!on);
    content.querySelectorAll('.cellbox').forEach(function(r){r.classList.toggle('all',on);});
    boxesBtn.textContent=on?'隐藏叠加框':'显示叠加框';
    boxesBtn.classList.toggle('on',on);
  }
  function open(img){
    hideCursorHint();
    var wrap=img.closest('.imgwrap'); if(!wrap) return;
    var view=img.closest('.view');
    var label=(view&&view.getAttribute('data-view')==='rect')?'矫正图':'原图';
    titleEl.textContent='页'+curPage+' · '+label+' · 血缘回溯框';
    openBtn.href=img.getAttribute('src');
    var clone=wrap.cloneNode(true);
    clone.className='lb-content';clone.id='lbContent';
    content.parentNode.replaceChild(clone,content);
    content=clone;
    var ci=clone.querySelector('img');
    ci.removeAttribute('width');ci.removeAttribute('height');
    ci.style.width='';ci.style.height='';
    imgW=img.naturalWidth||ci.naturalWidth||1000;
    imgH=img.naturalHeight||ci.naturalHeight||700;
    ci.style.width=imgW+'px';ci.style.height=imgH+'px';
    lb.hidden=false;document.body.style.overflow='hidden';
    setLbBoxes(allOn);
    fitWindow();
    if(!ci.complete){
      ci.addEventListener('load',function(){
        imgW=ci.naturalWidth;imgH=ci.naturalHeight;
        ci.style.width=imgW+'px';ci.style.height=imgH+'px';fitWindow();
      });
    }
  }
  function close(){
    lb.hidden=true;document.body.style.overflow='';drag=null;
    stage.classList.remove('dragging');
  }
  closeLb=close;
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
    if(e.altKey){ open(img); return; }
    var hit=hitCell(img,e);
    if(hit){ pinField(hit.getAttribute('data-key'),+hit.getAttribute('data-i')); return; }
    open(img);
  });
  document.querySelectorAll('[data-lb]').forEach(function(btn){
    btn.addEventListener('click',function(e){
      e.stopPropagation();
      var a=btn.getAttribute('data-lb');
      if(a==='close'){close();return;}
      if(a==='fit'){fitWindow();return;}
      if(a==='one'){scale=1;tx=0;ty=0;apply();return;}
      if(a==='in'){setScale(scale*1.25);return;}
      if(a==='out'){setScale(scale/1.25);return;}
      if(a==='boxes'){ setLbBoxes(lb.classList.contains('lb-noboxes')); }
    });
  });
  stage.addEventListener('wheel',function(e){
    e.preventDefault();
    var r=stage.getBoundingClientRect();
    setScale(scale*(e.deltaY<0?1.15:1/1.15),
      e.clientX-r.left-r.width/2,e.clientY-r.top-r.height/2);
  },{passive:false});
  stage.addEventListener('mousedown',function(e){
    if(e.button!==0) return;
    drag={x:e.clientX,y:e.clientY,tx:tx,ty:ty};moved=false;
    stage.classList.add('dragging');
  });
  window.addEventListener('mousemove',function(e){
    if(!drag) return;
    if(Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y)>4) moved=true;
    tx=drag.tx+(e.clientX-drag.x);ty=drag.ty+(e.clientY-drag.y);apply();
  });
  window.addEventListener('mouseup',function(){drag=null;stage.classList.remove('dragging');});
  stage.addEventListener('dblclick',function(e){
    e.preventDefault();
    if(Math.abs(scale-1)<0.01) fitWindow();
    else{scale=1;tx=0;ty=0;apply();}
  });
  /* 全屏里点回溯框：关闭全屏，回到左侧钉住对应记录行/格 */
  stage.addEventListener('click',function(e){
    if(moved) return;
    var b=e.target.closest?e.target.closest('.cellbox'):null;
    if(!b) return;
    e.stopPropagation();
    var i=+b.getAttribute('data-i'),key=b.getAttribute('data-key');
    close();
    pinField(key,i);
  });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') close();
    else if(e.key==='+'||e.key==='=') setScale(scale*1.25);
    else if(e.key==='-') setScale(scale/1.25);
    else if(e.key==='0') fitWindow();
  });
})();

/* ---- 加载 ---- */
function loadStaging(){
  document.getElementById('err').hidden=true;
  var u='/api/runs/'+encodeURIComponent(batch)+'/staging'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  var eu='/api/runs/'+encodeURIComponent(batch)+'/extract'+
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

document.getElementById('batchtag').textContent=batch||'（未指定批次）';
document.getElementById('runlink').href=batch?('/runs?batch='+encodeURIComponent(batch)):'/runs';
if(!batch){
  showErr('缺少批次参数。请从记录详情或提取完成提示进入。');
}else{
  fetch('/api/runs/'+encodeURIComponent(batch)).then(function(r){
    if(!r.ok) throw new Error('批次不存在');
    return r.json();
  }).then(function(j){
    runDoc=j.run;
    if(!curFile){
      var f=(runDoc.files||[]).find(function(x){return x.case;});
      curFile=f?f.case:'';
    }
    renderTabs(); loadStaging();
  }).catch(function(e){ showErr(e.message); });
}