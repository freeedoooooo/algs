/* web/report.js — 对照报告交互（生成时内联进每份 对照报告.html）。
   舞台公共件（cardOf/toast/cursorHint/hitCell/pager/lightbox 工厂）在 stage.js，先于本文件内联。 */
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
      b.classList.toggle('on',!off);
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
    /* 完整 JSON 按需加载：信封不内联进每个页卡片（多页大文件会平方级膨胀） */
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

/* 完整 JSON：紧凑信封嵌在 filecard 的 <script type="application/json"> 里
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
  if(!src){ pre.textContent='未找到完整 JSON 数据。'; return; }
  try{
    var pretty=JSON.stringify(JSON.parse(src.textContent),null,2);
    fjCache.set(fc,pretty); fill(pretty);
  }catch(e){
    pre.textContent='完整 JSON 解析失败：请点上方「下载」查看 extract.json。';
  }
}

/* JSON 复制：多页卡片有「本页 / 完整」两份 jsonpre，按按钮所在面板取，避免复制错对象 */
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

/* 点击图片全屏放大：共享 lightbox 工厂（stage.js），报告差异走钩子——
   标题取卡片 h2 + 页码；叠加框初始跟随内联 stage；点框转发回源卡片当前可见视图的原框。 */
var reportLb=bindStageLightbox({
  title:function(img,label){
    var card=cardOf(img);
    var h2=card.querySelector('h2');
    if(!h2){var fc=fileCardOf(img);h2=fc&&fc.querySelector('h2');}
    var pg=card.getAttribute('data-page');
    return (h2?h2.textContent:'图片')+(pg?' · 第 '+pg+' 页':'')+' · '+label;
  },
  boxesOnOpen:function(img){
    var st=cardOf(img).querySelector('.stage');
    return !(st&&st.classList.contains('noboxes'));
  },
  onBoxClick:function(b,srcImg){
    var srcCard=cardOf(srcImg);
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
    if(!orig) return;
    var fc=fileCardOf(srcCard),pg=srcCard.getAttribute('data-page');
    if(fc&&pg&&srcCard.hidden) activatePage(fc,pg);
    orig.dispatchEvent(new MouseEvent('click',{bubbles:true}));
  }
});
document.querySelectorAll('.stage .imgwrap img').forEach(function(img){
  img.addEventListener('mousemove',function(e){
    var hit=hitCell(img,e);
    var zoom=e.altKey||!hit;
    img.style.cursor=zoom?'zoom-in':'crosshair';
    var h=cursorHint();
    h.textContent=e.altKey?'单击：放大（Alt）':(hit?'单击：定位\nAlt + 单击：放大':'单击：放大');
    h.style.left=Math.min(e.clientX+14,window.innerWidth-h.offsetWidth-8)+'px';
    h.style.top=Math.min(e.clientY+18,window.innerHeight-h.offsetHeight-8)+'px';
    h.classList.add('on');
  });
  img.addEventListener('mouseleave',function(){
    hideCursorHint();
    img.style.cursor='';
  });
  img.addEventListener('click',function(e){
    e.stopPropagation();
    hideCursorHint();
    if(e.altKey){reportLb.open(img);return;}
    var hit=hitCell(img,e);
    if(hit){hit.dispatchEvent(new MouseEvent('click',{bubbles:true}));return;}
    reportLb.open(img);
  });
});

/* 多页文件：页签切换（只显示激活页卡片）；跨页合并表收进各页卡片 tab，完整 JSON 常驻下方 */
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
/* 单一整合页头：切页时把激活页的「页码片段」模板注入文件级 .pagehead-slot，
   文件级汇总不动，只有当前页码随页更新（路线/统计/链接已整合进右侧 tab，页头不再重复）。 */
function updatePageHead(fc){
  if(!fc) return;
  var slot=fc.querySelector('.pagehead-slot');
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var tpl=c&&c.querySelector('template.pagehead-tpl');
  if(slot&&tpl) slot.innerHTML=tpl.innerHTML;
}
/* 窗口式页码（公共件 pagerPages/renderPagerInto/alignPagerTo 在 stage.js）：
   每个页卡片各有一份 pager 副本（与页卡片同隐藏/显示），全部同步渲染。 */
function renderPager(fc){
  var c=fc.querySelector('.card[data-page]:not([hidden])');
  var cur=Number(c&&c.getAttribute('data-page'));
  fc.querySelectorAll('.pager').forEach(function(pg){
    renderPagerInto(pg,pagerPages(pg),cur);
  });
}
function alignPagers(){
  document.querySelectorAll('.stage .pager').forEach(function(pg){
    var stage=pg.closest('.stage');
    var card=stage.closest('.card');
    if(card&&card.hasAttribute('hidden')) return;
    alignPagerTo(pg,stage);
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
/* 参数快照悬浮面板：点外部收起，避免一直挂着挡内容 */
document.addEventListener('click',function(e){
  var ps=document.querySelector('.paramsnap[open]');
  if(ps&&!ps.contains(e.target)) ps.removeAttribute('open');
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
