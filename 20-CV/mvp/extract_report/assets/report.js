/* extract_report/assets/report.js — 对照报告交互（生成时内联进每份 对照报告.html） */
function cardOf(el){ return el.closest('.card'); }
function activeSpace(card){
  var tp=card.querySelector('.tabpanel:not([hidden])');
  var t=tp?tp.getAttribute('data-tab'):'';
  if(t==='tables'){
    var p=card.querySelector('.tblpane:not([hidden])');
    return p?p.getAttribute('data-space'):'';
  }
  if(t==='text'||t==='md'){ return card.getAttribute('data-textspace')||'source'; }
  return '';
}
function currentView(card){
  var b=card.querySelector('.viewbtn.on');
  return b ? b.getAttribute('data-view') : 'orig';
}
function elSpace(el){
  var host=el.closest('[data-space]');
  return host?host.getAttribute('data-space'):activeSpace(cardOf(el));
}
function wantViewOf(space){ return space==='rectified' ? 'rect' : 'orig'; }
function ensureViewFor(card,space){
  var w=wantViewOf(space);
  if(currentView(card)===w) return;
  var b=card.querySelector('.viewbtn[data-view="'+w+'"]');
  if(b) b.click();
}
function ensureView(card){ ensureViewFor(card,activeSpace(card)); }
function matchingRects(card,el){
  var sel='.cellbox[data-card="'+el.getAttribute('data-card')+'"]'+
          '[data-tbl="'+el.getAttribute('data-tbl')+'"]'+
          '[data-cell="'+el.getAttribute('data-cell')+'"]';
  return card.querySelectorAll(sel);
}
function clearHover(card){
  /* 文字行用 .hl、单元格用 .hv，移开时两类都要清，否则文字行框高亮残留 */
  card.querySelectorAll('.hv,.hl').forEach(function(x){x.classList.remove('hv','hl');});
}
function clearPin(card){
  card.querySelectorAll('.pin').forEach(function(x){x.classList.remove('pin');});
}
/* 追溯不到时的轻提示：底部居中 toast，2.4s 自动消失 */
var toastEl=null,toastTimer=null;
function toast(msg){
  if(!toastEl){
    toastEl=document.createElement('div');
    toastEl.id='trace-toast';
    document.body.appendChild(toastEl);
  }
  toastEl.textContent=msg;
  toastEl.classList.add('on');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(function(){toastEl.classList.remove('on');},2400);
}
/* 反向定位公共件：图框 → 数据侧。先激活对应 tab/子页签（切换会清 pin，须先做），再滚动到位 */
function matchingCells(card,el){
  return card.querySelectorAll('.cell[data-card="'+el.getAttribute('data-card')+'"]'+
    '[data-tbl="'+el.getAttribute('data-tbl')+'"][data-cell="'+el.getAttribute('data-cell')+'"]');
}
function activateTab(card,t){
  var b=card.querySelector('.ctab[data-tab="'+t+'"]');
  if(b&&!b.classList.contains('on')) b.click();
}
function revealCell(card,el){
  activateTab(card,'tables');
  var tb=card.querySelector('.tbltab[data-tbl="'+el.getAttribute('data-tbl')+'"]');
  if(tb&&!tb.classList.contains('on')) tb.click();
  el.scrollIntoView({block:'nearest',inline:'nearest'});
}
function revealScell(card,el){
  activateTab(card,'stitch');
  var sb=card.querySelector('.stitchtab[data-stitch="'+el.getAttribute('data-stitch')+'"]');
  if(sb&&!sb.classList.contains('on')) sb.click();
  el.scrollIntoView({block:'nearest',inline:'nearest'});
}

/* OCR 文字行 <-> 识别框 双向高亮；框所在视图由 data-space 决定，点击可切视图钉住 */
document.querySelectorAll('[data-card][data-idx]').forEach(function(el){
  function matches(){
    var c=el.getAttribute('data-card'),i=el.getAttribute('data-idx');
    return document.querySelectorAll('[data-card="'+c+'"][data-idx="'+i+'"]');
  }
  el.addEventListener('mouseenter',function(){
    var card=cardOf(el);
    if(currentView(card)!==wantViewOf(elSpace(el))) return;
    clearHover(card);
    matches().forEach(function(x){x.classList.add('hl');});
  });
  el.addEventListener('mouseleave',function(){clearHover(cardOf(el));});
  el.addEventListener('click',function(){
    var card=cardOf(el),was=el.classList.contains('pin');
    clearPin(card);clearHover(card);
    if(was) return;
    /* 从图上的识别框反向点入：切到文字 tab 并滚动到对应行（tab 切换会清 pin，先做）；
       文档 tab 下则就地滚动到 md 行，不把用户拽离文档视图 */
    if(el.tagName==='polygon'){
      var tp=card.querySelector('.tabpanel:not([hidden])');
      var tt=tp?tp.getAttribute('data-tab'):'';
      if(tt==='md'){
        var ml=card.querySelector('.tabpanel[data-tab="md"] .mdline[data-idx="'+el.getAttribute('data-idx')+'"]');
        if(ml) ml.scrollIntoView({block:'nearest',inline:'nearest'});
      }else{
        activateTab(card,'text');
        var row=card.querySelector('.tabpanel[data-tab="text"] tr[data-idx="'+el.getAttribute('data-idx')+'"]');
        if(row) row.scrollIntoView({block:'nearest',inline:'nearest'});
      }
    }
    if(!card.querySelector('polygon.box[data-idx="'+el.getAttribute('data-idx')+'"]')){
      toast('该行没有图像识别框，无法回溯到图');
      return;
    }
    ensureViewFor(card,elSpace(el));
    matches().forEach(function(x){x.classList.add('pin');});
  });
});

/* 原图 / 矫正图：两套坐标系互斥 */
document.querySelectorAll('.viewbtn').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),v=btn.getAttribute('data-view');
    card.querySelectorAll('.viewbtn').forEach(function(b){b.classList.toggle('on',b===btn);});
    card.querySelectorAll('.view').forEach(function(p){
      p.hidden=(p.getAttribute('data-view')!==v);
    });
    alignPagers();
  });
});

/* 内联图叠加框开关：原图 / 矫正图各有一个按钮，共用 stage.noboxes，状态同步 */
document.querySelectorAll('.boxtoggle').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),stage=card.querySelector('.stage');
    var off=stage.classList.toggle('noboxes');
    card.querySelectorAll('.boxtoggle').forEach(function(b){
      b.classList.toggle('on',off);
      b.textContent=off?'显示叠加框':'隐藏叠加框';
    });
  });
});

/* 右栏 tab：文字行 / 表格 / 文档 / JSON 切换；左图吸顶始终可见，切 tab 后视图跟随坐标空间 */
document.querySelectorAll('.ctab').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),t=btn.getAttribute('data-tab');
    clearPin(card);clearHover(card);
    card.querySelectorAll('.ctab').forEach(function(b){b.classList.toggle('on',b===btn);});
    card.querySelectorAll('.tabpanel').forEach(function(p){
      p.hidden=(p.getAttribute('data-tab')!==t);
    });
    /* 整份 JSON 按需加载：信封不内联进每个页卡片（多页大文件会平方级膨胀） */
    if(t==='filejson') loadFileJson(card);
    /* 文档面板多表同屏：放开全部单格框；切回表格面板恢复「只显选中表」 */
    if(t==='md'){
      card.querySelectorAll('.cellbox').forEach(function(r){r.classList.remove('off');});
    }else if(t==='tables'){
      var on=card.querySelector('.tbltab.on');
      var ti=on?on.getAttribute('data-tbl'):'0';
      card.querySelectorAll('.cellbox').forEach(function(r){
        r.classList.toggle('off',r.getAttribute('data-tbl')!==ti);
      });
    }
    ensureView(card);
  });
});

/* 次要调试开关：默认关闭，正常单格定位不需要 */
document.querySelectorAll('.allcells').forEach(function(btn){
  btn.addEventListener('click',function(e){
    e.stopPropagation();
    var card=cardOf(btn),on=!btn.classList.contains('on');
    btn.classList.toggle('on',on);
    btn.textContent=on?'隐藏整表网格':'显示整表网格';
    card.querySelectorAll('.cellbox').forEach(function(r){r.classList.toggle('all',on);});
  });
});

/* 多表 tab：只显示选中表，图上只叠选中表的框 */
document.querySelectorAll('.tbltab').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),ti=btn.getAttribute('data-tbl');
    clearPin(card);clearHover(card);
    card.querySelectorAll('.tbltab').forEach(function(b){b.classList.toggle('on',b===btn);});
    card.querySelectorAll('.tblpane').forEach(function(p){
      p.hidden=(p.getAttribute('data-tbl')!==ti);
    });
    card.querySelectorAll('.cellbox').forEach(function(r){
      r.classList.toggle('off',r.getAttribute('data-tbl')!==ti);
    });
    ensureView(card);
  });
});

/* 单格定位：默认零框，悬停临时高亮一格，点击钉住（再点取消） */
document.querySelectorAll('td.cell,th.cell').forEach(function(el){
  el.addEventListener('mouseenter',function(){
    var card=cardOf(el);
    if(currentView(card)!==wantViewOf(elSpace(el))) return;
    clearHover(card);
    el.classList.add('hv');
    matchingRects(card,el).forEach(function(r){r.classList.add('hv');});
  });
  el.addEventListener('mouseleave',function(){clearHover(cardOf(el));});
  el.addEventListener('click',function(){
    var card=cardOf(el),was=el.classList.contains('pin');
    clearPin(card);clearHover(card);
    if(was) return;
    if(!matchingRects(card,el).length){
      toast('该单元格没有图像坐标，无法回溯到图');
      return;
    }
    ensureViewFor(card,elSpace(el));
    el.classList.add('pin');
    matchingRects(card,el).forEach(function(r){r.classList.add('pin');});
  });
});

/* 反向定位：图上单元格框 → 表格单元格。悬停临时高亮，点击切表格 tab/子页签 + 滚动钉住。
   框默认隐藏，可见态（整表网格/钉住）才可交互；隐藏态的反向定位走图片点击命中测试 hitCell。 */
document.querySelectorAll('.cellbox').forEach(function(r){
  r.addEventListener('mouseenter',function(){
    var card=cardOf(r);
    if(currentView(card)!==wantViewOf(elSpace(r))) return;
    clearHover(card);
    r.classList.add('hv');
    matchingCells(card,r).forEach(function(x){x.classList.add('hv');});
  });
  r.addEventListener('mouseleave',function(){clearHover(cardOf(r));});
  r.addEventListener('click',function(e){
    e.stopPropagation();
    var card=cardOf(r),was=r.classList.contains('pin');
    clearPin(card);clearHover(card);
    if(was) return;
    var cells=matchingCells(card,r);
    if(cells.length) revealCell(card,cells[0]);
    ensureViewFor(card,elSpace(r));
    matchingRects(card,r).forEach(function(x){x.classList.add('pin');});
    cells.forEach(function(x){x.classList.add('pin');});
  });
});

/* 反向定位：图上跨页合并格框 → 合并表单元格（框画在哪页，scell 副本就在当前页卡片里） */
document.querySelectorAll('.stitchbox').forEach(function(r){
  function scells(){
    return cardOf(r).querySelectorAll('.scell[data-stitch="'+r.getAttribute('data-stitch')+'"]'+
      '[data-cell="'+r.getAttribute('data-cell')+'"]');
  }
  r.addEventListener('mouseenter',function(){
    var card=cardOf(r);
    if(currentView(card)!==wantViewOf(elSpace(r))) return;
    clearScellHover(fileCardOf(r));
    r.classList.add('hv');
    scells().forEach(function(x){x.classList.add('hv');});
  });
  r.addEventListener('mouseleave',function(){clearScellHover(fileCardOf(r));});
  r.addEventListener('click',function(e){
    e.stopPropagation();
    var card=cardOf(r),fc=fileCardOf(r),was=r.classList.contains('pin');
    clearPin(fc);clearScellHover(fc);
    if(was) return;
    var cs=scells();
    if(cs.length) revealScell(card,cs[0]);
    ensureViewFor(card,elSpace(r));
    r.classList.add('pin');
    cs.forEach(function(x){x.classList.add('pin');});
  });
});

/* 整份 JSON：紧凑信封嵌在 filecard 的 <script type="application/json"> 里
   （全报告仅一份，不逐页内联——平方级膨胀），首次打开 tab 时才解析美化。
   不用 fetch：file:// 直开时浏览器禁止 fetch 本地文件，嵌入则两种打开都成立。
   美化结果按 filecard 缓存，多个页卡片副本共享。 */
var fjCache=new Map();
function loadFileJson(card){
  var pre=card.querySelector('.tabpanel[data-tab="filejson"] .jsonpre');
  if(!pre||pre.getAttribute('data-loaded')) return;
  function fill(text){ pre.textContent=text; pre.setAttribute('data-loaded','1'); }
  var fc=card.closest('.filecard');
  if(fjCache.has(fc)){ fill(fjCache.get(fc)); return; }
  var src=fc&&fc.querySelector('script.filejson-src');
  if(!src){ pre.textContent='未找到整份 JSON 数据。'; return; }
  try{
    var pretty=JSON.stringify(JSON.parse(src.textContent),null,2);
    fjCache.set(fc,pretty); fill(pretty);
  }catch(e){
    pre.textContent='整份 JSON 解析失败：请点上方「下载」查看 result.json。';
  }
}

/* JSON 复制：多页卡片有「本页 / 整份」两份 jsonpre，按按钮所在面板取，避免复制错对象 */
document.querySelectorAll('.copyjson').forEach(function(btn){
  btn.addEventListener('click',function(){
    var host=btn.closest('.panel')||cardOf(btn);
    var pre=host.querySelector('.jsonpre');
    if(!pre) return;
    navigator.clipboard.writeText(pre.textContent).then(function(){
      btn.textContent='已复制';
      setTimeout(function(){btn.textContent='复制 JSON';},1500);
    });
  });
});

/* 图片点击命中测试（定位模式）：按数据侧优先级取目标，与当前 tab 无关——
   ① 跨页合并格框 stitchbox → 跨页合并 tab；② 单格框 cellbox → 表格 tab；
   ③ 识别框 polygon（四边形射线法）→ 文本/文档 tab。同级重叠取面积最小者（最内层）。
   合并表区域的格框与单格框几何重合，靠优先级保证先跳跨页合并。叠加框隐藏时也生效。
   坐标按 viewBox 1:1 换算。命中返回图框元素（其 click 处理器负责切 tab/钉住），未命中 null。 */
function hitCell(img,e){
  var card=cardOf(img);
  var view=img.closest('.view');
  var svg=view&&view.querySelector('svg');
  if(!svg||!svg.viewBox||!svg.viewBox.baseVal||!svg.viewBox.baseVal.width) return null;
  var vb=svg.viewBox.baseVal,r=img.getBoundingClientRect();
  if(!r.width||!r.height) return null;
  var x=(e.clientX-r.left)/r.width*vb.width,y=(e.clientY-r.top)/r.height*vb.height;
  function bestRect(list){
    var best=null,bestA=Infinity;
    Array.prototype.forEach.call(list,function(b){
      var bx=+b.getAttribute('x'),by=+b.getAttribute('y'),
          bw=+b.getAttribute('width'),bh=+b.getAttribute('height');
      if(x>=bx&&x<=bx+bw&&y>=by&&y<=by+bh&&bw*bh<bestA){bestA=bw*bh;best=b;}
    });
    return best;
  }
  var cellSvg=view.querySelector('.cellsvg');
  if(cellSvg){
    var s=bestRect(cellSvg.querySelectorAll('.stitchbox'));
    if(s) return s;
    var c=bestRect(cellSvg.querySelectorAll('.cellbox'));
    if(c) return c;
  }
  var best=null,bestA=Infinity;
  view.querySelectorAll('polygon.box').forEach(function(p){
    var pts=(p.getAttribute('points')||'').trim().split(/\s+/).map(function(s){
      var xy=s.split(',');return [+xy[0],+xy[1]];
    });
    if(pts.length<3) return;
    var inside=false,minX=Infinity,minY=Infinity,maxX=-Infinity,maxY=-Infinity;
    for(var i=0,j=pts.length-1;i<pts.length;j=i++){
      var xi=pts[i][0],yi=pts[i][1],xj=pts[j][0],yj=pts[j][1];
      if(xi<minX)minX=xi;
      if(xi>maxX)maxX=xi;
      if(yi<minY)minY=yi;
      if(yi>maxY)maxY=yi;
      if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi) inside=!inside;
    }
    if(inside&&(maxX-minX)*(maxY-minY)<bestA){bestA=(maxX-minX)*(maxY-minY);best=p;}
  });
  if(best){
    var tp=card.querySelector('.tabpanel:not([hidden])');
    var tt=tp?tp.getAttribute('data-tab'):'';
    /* 文档 tab 下表格 cell 的文字没有 md 行：不拽去文本 tab，给提示（格框通常已在②命中） */
    if(tt==='md'&&!card.querySelector(
      '.tabpanel[data-tab="md"] .mdline[data-idx="'+best.getAttribute('data-idx')+'"]')) return null;
  }
  return best;
}

/* 点图行为开关：定位（命中测试反向追溯，未命中给提示）/ 放大（单击直接全屏）。
   与 boxtoggle 同款角标、同套同步机制：stage.clickzoom，原图/矫正图两副本一致。
   定位模式下双击仍可放大，作为不切开关的快捷逃生口。 */
document.querySelectorAll('.clickmode').forEach(function(btn){
  btn.addEventListener('click',function(e){
    e.stopPropagation();
    var card=cardOf(btn),stage=card.querySelector('.stage');
    var zoom=stage.classList.toggle('clickzoom');
    card.querySelectorAll('.clickmode').forEach(function(b){
      b.classList.toggle('on',zoom);
      b.textContent=zoom?'点图：放大':'点图：定位';
    });
  });
});

/* 点击图片全屏放大：克隆整个 .imgwrap，叠加框按同一 viewBox 1:1 跟随 */
(function(){
  var lb=document.getElementById('lightbox');
  var stage=document.getElementById('lbStage');
  var content=document.getElementById('lbContent');
  var scaleEl=document.getElementById('lbScale');
  var titleEl=document.getElementById('lbTitle');
  var openBtn=document.getElementById('lbOpen');
  var boxesBtn=document.getElementById('lbBoxes');
  if(!lb||!stage||!content) return;
  var scale=1,fit=1,tx=0,ty=0,imgW=0,imgH=0,drag=null,srcCard=null,moved=false;
  function apply(){
    content.style.transform='translate('+tx+'px,'+ty+'px) scale('+scale+')';
    scaleEl.textContent=Math.round(scale*100)+'%';
  }
  function clamp(v){return Math.max(fit*0.3,Math.min(12,v));}
  function setScale(v,mx,my){
    var old=scale;scale=clamp(v);
    if(mx!==undefined){
      tx=mx-(mx-tx)*(scale/old);
      ty=my-(my-ty)*(scale/old);
    }
    apply();
  }
  function fitWindow(){
    var r=stage.getBoundingClientRect();
    fit=Math.min(r.width/imgW,r.height/imgH)*0.94;
    if(!isFinite(fit)||fit<=0) fit=1;
    scale=fit;tx=0;ty=0;apply();
  }
  function open(img){
    var wrap=img.closest('.imgwrap');
    if(!wrap) return;
    var view=img.closest('.view');
    var label=(view&&view.getAttribute('data-view')==='rect')?'矫正图':'原图';
    var card=cardOf(img);
    srcCard=card;
    var h2=card.querySelector('h2');
    if(!h2){var fc=fileCardOf(img);h2=fc&&fc.querySelector('h2');}
    var pg=card.getAttribute('data-page');
    titleEl.textContent=(h2?h2.textContent:'图片')+(pg?' · 第 '+pg+' 页':'')+' · '+label;
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
    /* 全屏叠加框默认跟随内联 stage 的状态（初始默认隐藏），可再单独切换 */
    var srcStage=card.querySelector('.stage');
    var nb=!!(srcStage&&srcStage.classList.contains('noboxes'));
    lb.classList.toggle('lb-noboxes',nb);
    boxesBtn.textContent=nb?'显示叠加框':'隐藏叠加框';
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
  document.querySelectorAll('.stage .imgwrap img').forEach(function(img){
    img.setAttribute('title','单击：定位（右上可切「点图：放大」）；双击：放大');
    img.addEventListener('click',function(e){
      e.stopPropagation();
      var card=cardOf(img);
      if(card.querySelector('.stage').classList.contains('clickzoom')){open(img);return;}
      var hit=hitCell(img,e);
      if(hit){hit.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}
      toast('点击处没有可定位的文字框或单元格');
    });
    img.addEventListener('dblclick',function(e){
      e.stopPropagation();
      open(img);
    });
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
      if(a==='boxes'){
        var h=!lb.classList.contains('lb-noboxes');
        lb.classList.toggle('lb-noboxes',h);
        boxesBtn.textContent=h?'显示叠加框':'隐藏叠加框';
      }
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
  /* 全屏里点叠加框反向定位：关闭全屏，回到报告钉住原格/行（拖动松手不算点击）。
     克隆框不带处理器，按 data 属性找回源卡片里当前可见视图中的原框，转发点击。 */
  stage.addEventListener('click',function(e){
    if(moved||!srcCard) return;
    var b=e.target.closest?e.target.closest('.cellbox,.stitchbox,.box'):null;
    if(!b) return;
    e.stopPropagation();
    var sel;
    if(b.classList.contains('cellbox'))
      sel='.cellbox[data-tbl="'+b.getAttribute('data-tbl')+'"][data-cell="'+b.getAttribute('data-cell')+'"]';
    else if(b.classList.contains('stitchbox'))
      sel='.stitchbox[data-stitch="'+b.getAttribute('data-stitch')+'"][data-cell="'+b.getAttribute('data-cell')+'"]';
    else
      sel='.box[data-idx="'+b.getAttribute('data-idx')+'"]';
    var orig=null;
    srcCard.querySelectorAll(sel).forEach(function(r){
      var v=r.closest('.view');
      if(!orig&&v&&!v.hidden) orig=r;
    });
    close();
    if(!orig) return;
    var fc=fileCardOf(srcCard),pg=srcCard.getAttribute('data-page');
    if(fc&&pg&&srcCard.hidden) activatePage(fc,pg);
    orig.dispatchEvent(new MouseEvent('click',{bubbles:true}));
  });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') close();
    else if(e.key==='+'||e.key==='=') setScale(scale*1.25);
    else if(e.key==='-') setScale(scale/1.25);
    else if(e.key==='0') fitWindow();
  });
})();

/* 多页文件：页签切换（只显示激活页卡片）；跨页合并表收进各页卡片 tab，整份 JSON 常驻下方 */
function fileCardOf(el){ return el.closest('.filecard'); }
function showPage(fc,p){
  if(!fc) return false;
  var changed=false;
  fc.querySelectorAll('.card[data-page]').forEach(function(c){
    var hide=(c.getAttribute('data-page')!==String(p));
    if(c.hidden!==hide){c.hidden=hide;changed=true;}
  });
  return changed;
}
function activeTabOf(fc){
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var b=c&&c.querySelector('.ctab.on');
  return b?b.getAttribute('data-tab'):null;
}
function activeStitchOf(fc){
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var b=c&&c.querySelector('.stitchtab.on');
  return b?b.getAttribute('data-stitch'):null;
}
/* 切页保留当前激活 tab：在「跨页合并」tab 翻页时合并表不丢；悬停合并格切页同理。
   合并表内容渲染在每个页卡片的 stitch tab 里，切页后点亮新卡片的同一 tab 即可无缝衔接。
   多条跨页链时一并保留选中的合并表子页签，避免切页后高亮落在隐藏链上。 */
/* 单一整合页头：切页时把激活页的「页相关片段」模板注入文件级 .pagehead-slot，
   文件级汇总不动，只有当前页码/路线/统计/链接随页更新（不再每页各一个可见页头）。 */
function updatePageHead(fc){
  if(!fc) return;
  var slot=fc.querySelector('.pagehead-slot');
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var tpl=c&&c.querySelector('template.pagehead-tpl');
  if(slot&&tpl) slot.innerHTML=tpl.innerHTML;
}
/* 窗口式页码：首末页 + 当前页±1 常显，其余收进 …，页数再多也只占一小条。
   页码列表取自 data-pages（指定页提取时页码可能不连续）。 */
function pagerPages(pg){
  return (pg.getAttribute('data-pages')||'').split(',').filter(Boolean).map(Number);
}
function renderPager(fc){
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var cur=Number(c&&c.getAttribute('data-page'));
  /* 每个页卡片各有一份 pager 副本（与页卡片同隐藏/显示），全部同步渲染 */
  fc.querySelectorAll('.pager').forEach(function(pg){
    var pages=pagerPages(pg);
    var ci=pages.indexOf(cur);
    if(ci<0) ci=0;
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
  });
}
/* 翻页组件贴靠源图：按当前激活 imgwrap 的实测底缘 / 水平中心锚定 pager，
   窗口伸缩 / 切页 / 切视图 / 图片加载后始终悬浮在源图底部（不占布局、不压图宽）。
   垂直方向只用 bottom 锚定：若设 top 而 CSS bottom 仍在，绝对定位元素会被
   上下同时约束而拉伸，offsetHeight 读到拉伸高度 → 锚定计算自我污染。 */
function alignPagers(){
  document.querySelectorAll('.stage .pager').forEach(function(pg){
    var stage=pg.closest('.stage');
    var card=stage.closest('.card');
    if(card&&card.hasAttribute('hidden')) return;
    var iw=stage.querySelector('.view:not([hidden]) .imgwrap');
    if(!iw) return;
    var sr=stage.getBoundingClientRect(),ir=iw.getBoundingClientRect();
    if(!ir.width) return;
    pg.style.left=Math.round(ir.left-sr.left+ir.width/2)+'px';
    pg.style.bottom=Math.max(6,Math.round(sr.bottom-ir.bottom+8))+'px';
  });
}
function switchPage(fc,p){
  if(!fc) return false;
  var tab=activeTabOf(fc),sub=activeStitchOf(fc);
  /* 合并表在每页卡片各渲染一份：切页前记住当前滚动位置，切页后还原，
     否则新卡片滚动归零→光标下的行换掉→又触发切页→页交接行高频来回抖动。
     选择器必须用直接子级 `> .tablewrap`：pane 外/内若混入隐藏预览表(.aux-src 里的
     .tablewrap)，后代选择器会误命中它(scrollTop 恒 0)，同步失效→频闪复现。 */
  var oc=fc.querySelector('.card[data-page]:not([hidden])');
  var osp=oc&&oc.querySelector('.stitchpane:not([hidden]) > .tablewrap');
  var sTop=osp?osp.scrollTop:0,sLeft=osp?osp.scrollLeft:0;
  var changed=showPage(fc,p);
  if(changed){
    clearPin(fc);clearHover(fc);
    var nc=fc.querySelector('.card[data-page="'+p+'"]');
    var b=tab&&nc&&nc.querySelector('.ctab[data-tab="'+tab+'"]');
    if(b&&!b.classList.contains('on')) b.click();
    if(tab==='stitch'&&sub!=null&&nc){
      var sb=nc.querySelector('.stitchtab[data-stitch="'+sub+'"]');
      if(sb&&!sb.classList.contains('on')) sb.click();
    }
    if(tab==='stitch'&&nc){
      var nsp=nc.querySelector('.stitchpane:not([hidden]) > .tablewrap');
      if(nsp){nsp.scrollTop=sTop;nsp.scrollLeft=sLeft;}
    }
    updatePageHead(fc);
    renderPager(fc);
    alignPagers();
  }
  return changed;
}
function activatePage(fc,p){ switchPage(fc,p); }
/* 翻页事件：每个页卡片各有一份 pager 副本，点击走 filecard 委托，
   跳页输入框逐副本绑定；页码列表各副本一致，取第一份即可。 */
document.querySelectorAll('.filecard').forEach(function(fc){
  if(!fc.querySelector('.pager')) return;
  function pages(){ return pagerPages(fc.querySelector('.pager')); }
  function curIndex(){
    var c=fc.querySelector('.card[data-page]:not([hidden])');
    var i=pages().indexOf(Number(c&&c.getAttribute('data-page')));
    return i<0?0:i;
  }
  function go(i){
    var ps=pages();
    activatePage(fc,String(ps[Math.max(0,Math.min(ps.length-1,i))]));
  }
  fc.addEventListener('click',function(e){
    if(!(e.target.closest&&e.target.closest('.pager'))) return;
    var num=e.target.closest('.pg-num');
    if(num){activatePage(fc,num.getAttribute('data-page'));return;}
    var btn=e.target.closest('.pg-btn');
    if(!btn||btn.disabled) return;
    var a=btn.getAttribute('data-pg'),i=curIndex();
    if(a==='first') go(0);
    else if(a==='prev') go(i-1);
    else if(a==='next') go(i+1);
    else if(a==='last') go(pages().length-1);
  });
  fc.querySelectorAll('.pager .pg-jump').forEach(function(jump){
    function doJump(){
      var ps=pages(),v=parseInt(jump.value,10);
      if(isNaN(v)){jump.value=ps[curIndex()];return;}
      var i=ps.indexOf(v);
      if(i<0){ /* 输入的页码不在本次提取范围：就近落到存在的页 */
        i=0;ps.forEach(function(p,k){if(Math.abs(p-v)<Math.abs(ps[i]-v))i=k;});
      }
      go(i);jump.value=ps[curIndex()];
    }
    jump.addEventListener('keydown',function(e){
      e.stopPropagation();
      if(e.key==='Enter'){e.preventDefault();doJump();jump.blur();}
    });
    jump.addEventListener('blur',doJump);
    jump.addEventListener('click',function(e){e.stopPropagation();});
  });
});
/* 左右方向键翻页：仅焦点在该文件卡片内且不在输入控件时生效，不劫持全局 */
document.addEventListener('keydown',function(e){
  if(e.key!=='ArrowLeft'&&e.key!=='ArrowRight') return;
  var t=e.target;
  if(t&&(/^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)||t.isContentEditable)) return;
  var fc=t&&t.closest?t.closest('.filecard'):null;
  var pg=fc&&fc.querySelector('.pager');
  if(!pg) return;
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var ps=pagerPages(pg);
  var i=ps.indexOf(Number(c&&c.getAttribute('data-page')));if(i<0)i=0;
  var ni=e.key==='ArrowLeft'?i-1:i+1;
  if(ni<0||ni>=ps.length) return;
  e.preventDefault();
  activatePage(fc,String(ps[ni]));
});
/* 初始：每个多页文件把第 1 页片段注入整合页头 + 渲染页码窗口 */
document.querySelectorAll('.filecard').forEach(function(fc){ updatePageHead(fc); renderPager(fc); });
alignPagers();
window.addEventListener('resize',alignPagers);
document.querySelectorAll('.stage img').forEach(function(im){
  im.addEventListener('load',alignPagers);
});

/* 跨页合并表多表 tab */
document.querySelectorAll('.stitchtab').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),si=btn.getAttribute('data-stitch');
    clearPin(card);clearHover(card);
    card.querySelectorAll('.stitchtab').forEach(function(b){b.classList.toggle('on',b===btn);});
    card.querySelectorAll('.stitchpane').forEach(function(p){
      p.hidden=(p.getAttribute('data-stitch')!==si);
    });
  });
});

/* 跨页合并表单元格：页感知回溯（filecard 级委托）。
   悬停/点击→切到该格所在页→高亮该页图上的格。
   不用逐副本 mouseenter/mouseleave：切页会隐藏光标底下的那份副本，
   旧副本补发的 stale mouseleave 清掉刚加的高亮、新副本在鼠标不动时又不补发
   mouseenter，表现为「悬停卡住、回溯不了框」。改为 mousemove 委托 + 格键去重：
   高亮只随「光标下的格键」变化，与切页换 DOM 副本无关。 */
function scellKey(el){
  return el.getAttribute('data-stitch')+'|'+el.getAttribute('data-cell');
}
function scellMatches(fc,el){
  return fc.querySelectorAll('[data-stitch="'+el.getAttribute('data-stitch')+'"]'+
    '[data-cell="'+el.getAttribute('data-cell')+'"]');
}
/* 只清跨页格高亮，不碰逐页表格/文字行的 .hv（它们走各自的 enter/leave） */
function clearScellHover(fc){
  fc.querySelectorAll('.scell.hv,.stitchbox.hv').forEach(function(x){x.classList.remove('hv');});
}
function scellReveal(fc,el){
  var pc=fc.querySelector('.card[data-page="'+el.getAttribute('data-page')+'"]');
  if(!pc) return null;
  switchPage(fc,el.getAttribute('data-page'));
  ensureViewFor(pc,el.getAttribute('data-space')||'source');
  return pc;
}
document.querySelectorAll('.filecard').forEach(function(fc){
  var lastKey=null;
  function hover(el){
    var pc=scellReveal(fc,el);if(!pc)return;
    var space=el.getAttribute('data-space')||'source';
    if(currentView(pc)!==wantViewOf(space))return;
    clearScellHover(fc);
    scellMatches(fc,el).forEach(function(x){x.classList.add('hv');});
  }
  fc.addEventListener('mousemove',function(e){
    var t=e.target;
    /* 图上合并框的反向悬停由框自身管理，委托 here 不清它的高亮 */
    if(t&&t.closest&&t.closest('.stitchbox'))return;
    var el=t&&t.closest?t.closest('.scell'):null;
    var key=el?scellKey(el):null;
    if(key===lastKey)return;
    lastKey=key;
    if(!el){clearScellHover(fc);return;}
    hover(el);
  });
  fc.addEventListener('mouseleave',function(){lastKey=null;clearScellHover(fc);});
  fc.addEventListener('click',function(e){
    var t=e.target;
    var el=t&&t.closest?t.closest('.scell'):null;
    if(!el)return;
    var was=el.classList.contains('pin');
    if(!fc.querySelector('.stitchbox[data-stitch="'+el.getAttribute('data-stitch')+'"]'+
      '[data-cell="'+el.getAttribute('data-cell')+'"]')){
      toast('该合并格没有图像坐标，无法回溯到图');
      return;
    }
    var pc=scellReveal(fc,el);if(!pc)return;
    clearPin(fc);clearScellHover(fc);
    lastKey=null;
    if(was)return;
    scellMatches(fc,el).forEach(function(x){x.classList.add('pin');});
  });
});

/* 辅助内容弹窗：文本原文 / 提取诊断点按钮弹出，不占版面 */
(function(){
  var m=document.createElement('div');
  m.id='auxmodal'; m.hidden=true;
  m.innerHTML='<div class="aux-card"><div class="aux-head">'+
    '<span class="aux-title"></span>'+
    '<button type="button" class="aux-close">关闭 (Esc)</button></div>'+
    '<div class="aux-body"></div></div>';
  document.body.appendChild(m);
  var title=m.querySelector('.aux-title'),body=m.querySelector('.aux-body');
  function close(){ m.hidden=true; document.body.style.overflow=''; body.innerHTML=''; }
  document.querySelectorAll('.auxbtn').forEach(function(btn){
    btn.addEventListener('click',function(e){
      e.stopPropagation();                 // 不触发所在 details 收起
      var src=document.getElementById(btn.getAttribute('data-aux'));
      if(!src) return;
      title.textContent=btn.getAttribute('data-title')||'详情';
      body.innerHTML=src.innerHTML;
      m.hidden=false; document.body.style.overflow='hidden';
    });
  });
  m.addEventListener('click',function(e){
    if(e.target===m||(e.target.closest&&e.target.closest('.aux-close'))) close();
  });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&!m.hidden) close();
  });
})();
