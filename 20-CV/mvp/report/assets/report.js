/* report/assets/report.js — 对照报告交互（生成时内联进 index.html） */
function cardOf(el){ return el.closest('.card'); }
function activeSpace(card){
  var tp=card.querySelector('.tabpanel[data-tab="tables"]');
  if(tp && tp.hidden) return '';
  var p=card.querySelector('.tblpane:not([hidden])');
  return p ? p.getAttribute('data-space') : '';
}
function currentView(card){
  var b=card.querySelector('.viewbtn.on');
  return b ? b.getAttribute('data-view') : 'orig';
}
function wantView(card){ return activeSpace(card)==='rectified' ? 'rect' : 'orig'; }
function viewMatches(card){ return currentView(card)===wantView(card); }
function ensureView(card){
  var w=wantView(card);
  if(currentView(card)===w) return;
  var b=card.querySelector('.viewbtn[data-view="'+w+'"]');
  if(b) b.click();
}
function matchingRects(card,el){
  var sel='.cellbox[data-card="'+el.getAttribute('data-card')+'"]'+
          '[data-tbl="'+el.getAttribute('data-tbl')+'"]'+
          '[data-cell="'+el.getAttribute('data-cell')+'"]';
  return card.querySelectorAll(sel);
}
function clearHover(card){
  card.querySelectorAll('.hv').forEach(function(x){x.classList.remove('hv');});
}
function clearPin(card){
  card.querySelectorAll('.pin').forEach(function(x){x.classList.remove('pin');});
}

/* ---- 取 x 坐标工具：点图读自然像素 x，画竖线预览，收集后复制填 column_lines ----
   坐标空间跟随所点视图：doc_unwarp=off 点原图、on 点矫正图，与重切所用空间一致。
   用 img.getBoundingClientRect() 换算，内联图与全屏缩放/平移下都准确。 */
var SVGNS='http://www.w3.org/2000/svg';
var pickMode=false, pickVals=[];
(function(){
  var tog=document.createElement('button');
  tog.type='button'; tog.id='picktoggle'; tog.className='picktoggle';
  tog.textContent='取 x 坐标';
  var bar=document.createElement('div');
  bar.id='pickbar'; bar.className='pickbar'; bar.hidden=true;
  bar.innerHTML='<span class="picklabel">点图取 x（复制填 column_lines）</span>'+
    '<span class="pickvals" id="pickvals"></span>'+
    '<button type="button" data-pick="copy">复制</button>'+
    '<button type="button" data-pick="clear">清空</button>'+
    '<button type="button" data-pick="exit">退出</button>';
  document.body.appendChild(tog); document.body.appendChild(bar);
  tog.addEventListener('click',function(){ setPickMode(!pickMode); });
  bar.addEventListener('click',function(e){
    var b=e.target.closest?e.target.closest('[data-pick]'):null;
    if(!b) return;
    var a=b.getAttribute('data-pick');
    if(a==='copy'){
      if(!pickVals.length) return;
      navigator.clipboard.writeText(pickVals.join(',')).then(function(){
        b.textContent='已复制'; setTimeout(function(){b.textContent='复制';},1500);
      });
    }else if(a==='clear'){ clearPick(); }
    else if(a==='exit'){ setPickMode(false); }
  });
})();
function setPickMode(on){
  pickMode=on;
  document.body.classList.toggle('picking',on);
  document.getElementById('pickbar').hidden=!on;
  var tog=document.getElementById('picktoggle');
  tog.hidden=on;
  tog.classList.toggle('on',on);
  tog.textContent=on?'退出取数':'取 x 坐标';
  var lp=document.getElementById('lbPick');
  if(lp){ lp.classList.toggle('on',on); lp.textContent=on?'退出取数':'取 x 坐标'; }
  renderPickBar();
}
function renderPickBar(){
  var el=document.getElementById('pickvals');
  if(el) el.textContent=pickVals.length?pickVals.join(', '):'（尚未取点）';
}
function clearPickLines(){
  document.querySelectorAll('.pickline').forEach(function(x){x.remove();});
}
function clearPick(){ pickVals=[]; clearPickLines(); renderPickBar(); }
function naturalX(img,clientX){
  var r=img.getBoundingClientRect();
  var nw=img.naturalWidth||1000;
  var x=(clientX-r.left)*nw/(r.width||1);
  return Math.max(0,Math.min(nw,Math.round(x)));
}
function addPoint(img,e){
  var x=naturalX(img,e.clientX);
  pickVals.push(x);
  var wrap=img.closest('.imgwrap')||img.parentElement;
  if(wrap){
    var svg=wrap.querySelector('svg');
    if(!svg){
      svg=document.createElementNS(SVGNS,'svg');
      svg.setAttribute('class','cellsvg');
      svg.setAttribute('preserveAspectRatio','none');
      svg.setAttribute('viewBox','0 0 '+(img.naturalWidth||1000)+' '+(img.naturalHeight||700));
      wrap.appendChild(svg);
    }
    var vb=svg.viewBox.baseVal;
    var ln=document.createElementNS(SVGNS,'line');
    ln.setAttribute('class','pickline');
    ln.setAttribute('x1',x); ln.setAttribute('x2',x);
    ln.setAttribute('y1',0); ln.setAttribute('y2',vb.height);
    svg.appendChild(ln);
  }
  renderPickBar();
}

/* OCR 文字行 <-> 原图识别框 双向高亮 */
document.querySelectorAll('[data-card][data-idx]').forEach(function(el){
  el.addEventListener('mouseenter',function(){
    var c=el.getAttribute('data-card'),i=el.getAttribute('data-idx');
    document.querySelectorAll('[data-card="'+c+'"][data-idx="'+i+'"]')
      .forEach(function(x){x.classList.add('hl');});
  });
  el.addEventListener('mouseleave',function(){
    document.querySelectorAll('.hl').forEach(function(x){x.classList.remove('hl');});
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
  });
});

/* 右栏 tab：文字行 / 表格 / JSON 切换；左图吸顶始终可见，切 tab 后视图跟随坐标空间 */
document.querySelectorAll('.ctab').forEach(function(btn){
  btn.addEventListener('click',function(){
    var card=cardOf(btn),t=btn.getAttribute('data-tab');
    clearPin(card);clearHover(card);
    card.querySelectorAll('.ctab').forEach(function(b){b.classList.toggle('on',b===btn);});
    card.querySelectorAll('.tabpanel').forEach(function(p){
      p.hidden=(p.getAttribute('data-tab')!==t);
    });
    ensureView(card);
  });
});

/* 次要调试开关：默认关闭，正常单格定位不需要 */
document.querySelectorAll('.allcells').forEach(function(btn){
  btn.addEventListener('click',function(){
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
    if(!viewMatches(card)) return;
    clearHover(card);
    el.classList.add('hv');
    matchingRects(card,el).forEach(function(r){r.classList.add('hv');});
  });
  el.addEventListener('mouseleave',function(){clearHover(cardOf(el));});
  el.addEventListener('click',function(){
    var card=cardOf(el),was=el.classList.contains('pin');
    clearPin(card);clearHover(card);
    if(was) return;
    ensureView(card);
    el.classList.add('pin');
    matchingRects(card,el).forEach(function(r){r.classList.add('pin');});
  });
});

/* JSON 复制 */
document.querySelectorAll('.copyjson').forEach(function(btn){
  btn.addEventListener('click',function(){
    var pre=cardOf(btn).querySelector('.jsonpre');
    if(!pre) return;
    navigator.clipboard.writeText(pre.textContent).then(function(){
      btn.textContent='已复制';
      setTimeout(function(){btn.textContent='复制 JSON';},1500);
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
  var scale=1,fit=1,tx=0,ty=0,imgW=0,imgH=0,drag=null,moved=0;
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
    var h2=cardOf(img).querySelector('h2');
    titleEl.textContent=(h2?h2.textContent:'图片')+' · '+label;
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
    fitWindow();
    ci.addEventListener('click',function(e){
      if(!pickMode) return;
      e.stopPropagation();
      if(moved>5) return;          // 刚才是拖拽平移，不是取点
      addPoint(ci,e);
    });
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
    img.setAttribute('title','点击放大查看');
    img.addEventListener('click',function(e){
      e.stopPropagation();
      if(pickMode){ addPoint(img,e); return; }
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
      if(a==='pick'){ setPickMode(!pickMode); }
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
    drag={x:e.clientX,y:e.clientY,tx:tx,ty:ty};moved=0;
    stage.classList.add('dragging');
  });
  window.addEventListener('mousemove',function(e){
    if(!drag) return;
    moved=Math.abs(e.clientX-drag.x)+Math.abs(e.clientY-drag.y);
    tx=drag.tx+(e.clientX-drag.x);ty=drag.ty+(e.clientY-drag.y);apply();
  });
  window.addEventListener('mouseup',function(){drag=null;stage.classList.remove('dragging');});
  stage.addEventListener('dblclick',function(e){
    e.preventDefault();
    if(Math.abs(scale-1)<0.01) fitWindow();
    else{scale=1;tx=0;ty=0;apply();}
  });
  document.addEventListener('keydown',function(e){
    if(lb.hidden) return;
    if(e.key==='Escape') close();
    else if(e.key==='+'||e.key==='=') setScale(scale*1.25);
    else if(e.key==='-') setScale(scale/1.25);
    else if(e.key==='0') fitWindow();
  });
})();
