/* extract_report/assets/stage.js — 报告/校验台共享舞台交互。
   生成报告时内联在 report.js 之前（builder.py）；校验台经 /static 引用。
   页面各自的 wiring（逐卡绑定 / 动态渲染 / 钉住转发）留 report.js / staging.js。 */
function cardOf(el){ return el.closest('.card'); }
function wantViewOf(space){ return space==='rectified' ? 'rect' : 'orig'; }

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

/* 点图行为跟随光标：悬停命中→十字光标，空白→放大光标；pill 即时提示单击动作 */
var hintEl=null;
function cursorHint(){
  if(!hintEl){
    hintEl=document.createElement('div');
    hintEl.id='cursor-hint';
    document.body.appendChild(hintEl);
  }
  return hintEl;
}
function hideCursorHint(){ if(hintEl) hintEl.classList.remove('on'); }

/* 图片点击命中测试（定位模式）：按数据侧优先级取目标，与当前 tab 无关——
   ① 跨页合并格框 stitchbox → 跨页合并 tab；② 单格框 cellbox → 表格 tab；
   ③ 识别框 polygon（四边形射线法）→ 文本/文档 tab。同级重叠取面积最小者（最内层）。
   合并表区域的格框与单格框几何重合，靠优先级保证先跳跨页合并。叠加框隐藏时也生效。
   坐标按 viewBox 1:1 换算。命中返回图框元素（其 click 处理器负责切 tab/钉住），未命中 null。
   校验台 DOM 无 .card / polygon：cardOf 为 null 安全（polygon 分支不会命中）。 */
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

/* 窗口式页码：首末页 + 当前页±1 常显，其余收进 …，页数再多也只占一小条。
   页码列表取自 data-pages（指定页提取时页码可能不连续）。 */
function pagerPages(pg){
  return (pg.getAttribute('data-pages')||'').split(',').filter(Boolean).map(Number);
}
function renderPagerInto(pg,pages,cur){
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
}
/* 翻页组件贴靠源图：按当前激活 imgwrap 的实测底缘 / 水平中心锚定 pager。
   垂直方向只用 bottom 锚定：若设 top 而 CSS bottom 仍在，绝对定位元素会被
   上下同时约束而拉伸，offsetHeight 读到拉伸高度 → 锚定计算自我污染。 */
function alignPagerTo(pg,stage){
  var iw=stage.querySelector('.view:not([hidden]) .imgwrap');
  if(!iw) return;
  var sr=stage.getBoundingClientRect(),ir=iw.getBoundingClientRect();
  if(!ir.width) return;
  pg.style.left=Math.round(ir.left-sr.left+ir.width/2)+'px';
  pg.style.bottom=Math.max(6,Math.round(sr.bottom-ir.bottom+8))+'px';
}

/* 全屏浮层工厂：克隆整个 .imgwrap，叠加框按同一 viewBox 1:1 跟随；
   滚轮缩放/拖拽/双击/键盘/点框反向定位全部共享，页面差异走 opts 钩子：
   title(img,label)→标题；boxesOnOpen(img)→初始叠加框开关；
   onBoxClick(box,srcImg)→点框关闭全屏后的转发；syncBoxes(on,content)→额外同步。 */
function bindStageLightbox(opts){
  var lb=document.getElementById('lightbox');
  var stage=document.getElementById('lbStage');
  var content=document.getElementById('lbContent');
  var scaleEl=document.getElementById('lbScale');
  var titleEl=document.getElementById('lbTitle');
  var openBtn=document.getElementById('lbOpen');
  var boxesBtn=document.getElementById('lbBoxes');
  if(!lb||!stage||!content) return {open:function(){},close:function(){}};
  var scale=1,fit=1,tx=0,ty=0,imgW=0,imgH=0,drag=null,moved=false,srcImg=null;
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
  function setBoxes(on){
    lb.classList.toggle('lb-noboxes',!on);
    boxesBtn.textContent=on?'隐藏叠加框':'显示叠加框';
    if(opts.syncBoxes) opts.syncBoxes(on,content);
  }
  function open(img){
    hideCursorHint();
    var wrap=img.closest('.imgwrap');
    if(!wrap) return;
    var view=img.closest('.view');
    var label=(view&&view.getAttribute('data-view')==='rect')?'矫正图':'原图';
    srcImg=img;
    titleEl.textContent=opts.title(img,label);
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
    setBoxes(opts.boxesOnOpen(img));
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
  document.querySelectorAll('[data-lb]').forEach(function(btn){
    btn.addEventListener('click',function(e){
      e.stopPropagation();
      var a=btn.getAttribute('data-lb');
      if(a==='close'){close();return;}
      if(a==='fit'){fitWindow();return;}
      if(a==='one'){scale=1;tx=0;ty=0;apply();return;}
      if(a==='in'){setScale(scale*1.25);return;}
      if(a==='out'){setScale(scale/1.25);return;}
      if(a==='boxes'){setBoxes(lb.classList.contains('lb-noboxes'));}
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
  /* 全屏里点叠加框反向定位：关闭全屏，交页面钩子钉住原格/行（拖动松手不算点击） */
  stage.addEventListener('click',function(e){
    if(moved||!srcImg) return;
    var b=e.target.closest?e.target.closest('.cellbox,.stitchbox,.box'):null;
    if(!b) return;
    e.stopPropagation();
    close();
    if(opts.onBoxClick) opts.onBoxClick(b,srcImg);
  });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') close();
    else if(e.key==='+'||e.key==='=') setScale(scale*1.25);
    else if(e.key==='-') setScale(scale/1.25);
    else if(e.key==='0') fitWindow();
  });
  return {open:open,close:close};
}