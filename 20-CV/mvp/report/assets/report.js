/* report/assets/report.js — 对照报告交互（生成时内联进 index.html） */
function cardOf(el){ return el.closest('.card'); }
function activeSpace(card){
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
  var scale=1,fit=1,tx=0,ty=0,imgW=0,imgH=0,drag=null;
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
    img.addEventListener('click',function(e){e.stopPropagation();open(img);});
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
    drag={x:e.clientX,y:e.clientY,tx:tx,ty:ty};
    stage.classList.add('dragging');
  });
  window.addEventListener('mousemove',function(e){
    if(!drag) return;
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
