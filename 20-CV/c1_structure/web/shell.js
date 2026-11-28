/* web/shell.js — 列表页共用小件：转义 / 格式化 / 缩略图 /
   状态徽标 / 全屏预览。各页面自己的交互仍在各自 js 里。 */
function escHtml(s){
  return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}
function fmtSize(n){
  n=Number(n)||0;
  if(n>=1024*1024) return (n/1024/1024).toFixed(1)+' MB';
  return Math.max(1,Math.round(n/1024))+' KB';
}
function fmtTime(s){
  if(!s) return '—';
  var d=new Date(s);
  if(isNaN(d.getTime())) return String(s);
  function p(n){ return (n<10?'0':'')+n; }
  return p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes());
}
function kindOf(name){
  var e=(String(name).split('.').pop()||'').toLowerCase();
  if(['png','jpg','jpeg','bmp','webp','tif','tiff'].indexOf(e)>=0) return 'image';
  if(e==='pdf') return 'pdf';
  return 'text';
}
var KIND_LABEL={image:'图片',pdf:'PDF',text:'文本'};
/* 缩略图：图片可点击放大（data-full），PDF/文本角标新窗口打开 */
function thumbHtml(name,url){
  var k=kindOf(name);
  if(k==='image')
    return '<img class="thumb" src="'+escHtml(url)+'" data-full="'+escHtml(url)+
      '" alt="'+escHtml(name)+'" title="'+escHtml(name)+'">';
  var label=(k==='pdf'?'PDF':(String(name).split('.').pop()||'FILE').toUpperCase());
  return '<a class="thumb file" href="'+escHtml(url)+'" target="_blank" title="'+
    escHtml(name)+'"><span>'+escHtml(label.slice(0,4))+'</span></a>';
}
/* 写入方式存库值不变（upsert/insert/update），显示层统一用短标签；
   完整解释见 rules.html 下拉 title 悬浮提示 */
var MODE_LABEL={
  upsert:'覆盖或新增',
  insert:'仅新增',
  update:'仅更新'
};
function modeLabel(m){ return MODE_LABEL[m]||m||'—'; }

function closeActionMenus(){
  document.querySelectorAll('.action-menu:not([hidden])').forEach(function(menu){
    menu.hidden=true;
    var trigger=menu._actionTrigger;
    if(trigger&&trigger.isConnected) trigger.setAttribute('aria-expanded','false');
  });
}
function positionActionMenu(menu,trigger){
  var margin=8,gap=4;
  var r=trigger.getBoundingClientRect(),m=menu.getBoundingClientRect();
  var left=r.right-m.width;
  if(left<margin) left=margin;
  if(left+m.width>window.innerWidth-margin) left=window.innerWidth-margin-m.width;
  var top=r.bottom+gap;
  if(top+m.height>window.innerHeight-margin) top=r.top-m.height-gap;
  if(top<margin) top=margin;
  menu.style.left=Math.round(left)+'px';
  menu.style.top=Math.round(top)+'px';
}
function initActionMenus(){
  document.addEventListener('click',function(e){
    var trigger=e.target.closest?e.target.closest('[data-action-menu]'):null;
    if(trigger){
      var menu=document.getElementById(trigger.getAttribute('data-action-menu'));
      if(!menu) return;
      e.preventDefault();
      var wasOpen=!menu.hidden;
      closeActionMenus();
      if(wasOpen) return;
      menu._actionTrigger=trigger;
      menu.hidden=false;
      trigger.setAttribute('aria-expanded','true');
      positionActionMenu(menu,trigger);
      var first=menu.querySelector('.menu-item:not(:disabled)');
      if(first) first.focus({preventScroll:true});
      return;
    }
    if(e.target.closest&&e.target.closest('.action-menu')){
      var item=e.target.closest('.menu-item');
      if(item&&!item.hasAttribute('data-keep-open')) closeActionMenus();
      return;
    }
    closeActionMenus();
  });
  document.addEventListener('keydown',function(e){
    var open=document.querySelector('.action-menu:not([hidden])');
    var trigger=e.target.closest?e.target.closest('[data-action-menu]'):null;
    if(trigger&&(e.key==='ArrowDown'||e.key==='ArrowUp')){
      var menu=document.getElementById(trigger.getAttribute('data-action-menu'));
      if(!menu) return;
      e.preventDefault();
      var wasOpen=!menu.hidden;
      closeActionMenus();
      if(wasOpen) return;
      menu._actionTrigger=trigger;
      menu.hidden=false;
      trigger.setAttribute('aria-expanded','true');
      positionActionMenu(menu,trigger);
      var items=menu.querySelectorAll('.menu-item:not(:disabled)');
      if(items.length) items[e.key==='ArrowUp'?items.length-1:0].focus();
      return;
    }
    if(!open) return;
    if(e.key==='Escape'){
      e.preventDefault();
      var owner=open._actionTrigger;
      closeActionMenus();
      if(owner&&owner.isConnected) owner.focus();
      return;
    }
    if(!open.contains(e.target)) return;
    var entries=Array.prototype.slice.call(open.querySelectorAll('.menu-item:not(:disabled)'));
    var at=entries.indexOf(e.target);
    if(e.key==='ArrowDown'||e.key==='ArrowUp'||e.key==='Home'||e.key==='End'){
      e.preventDefault();
      var next=e.key==='Home'?0:(e.key==='End'?entries.length-1:
        (at+(e.key==='ArrowDown'?1:-1)+entries.length)%entries.length);
      if(entries[next]) entries[next].focus();
    }
  });
  window.addEventListener('resize',function(){
    var menu=document.querySelector('.action-menu:not([hidden])');
    if(menu&&menu._actionTrigger) positionActionMenu(menu,menu._actionTrigger);
  });
  window.addEventListener('scroll',function(e){
    var menu=document.querySelector('.action-menu:not([hidden])');
    if(menu&&(!e.target||!menu.contains(e.target))) closeActionMenus();
  },true);
}
function setDisclosure(toggle,open,persist){
  var body=document.getElementById(toggle.getAttribute('aria-controls'));
  if(!body) return;
  body.hidden=!open;
  toggle.setAttribute('aria-expanded',String(open));
  var key=toggle.getAttribute('data-disclosure-key');
  if(persist&&key){
    try{localStorage.setItem('c1.disclosure.'+key,open?'1':'0');}catch(e){}
  }
}
function initDisclosures(){
  document.querySelectorAll('[data-disclosure-toggle]').forEach(function(toggle){
    var key=toggle.getAttribute('data-disclosure-key'),saved=null;
    if(key){ try{saved=localStorage.getItem('c1.disclosure.'+key);}catch(e){} }
    if(saved!=null) setDisclosure(toggle,saved==='1',false);
  });
  document.addEventListener('click',function(e){
    var toggle=e.target.closest?e.target.closest('[data-disclosure-toggle]'):null;
    if(!toggle) return;
    setDisclosure(toggle,toggle.getAttribute('aria-expanded')!=='true',true);
  });
}
document.addEventListener('click',function(e){
  var drawer=e.target.closest?e.target.closest('.drawer'):null;
  if(!drawer||e.target!==drawer)return;
  if(drawer.classList.contains('drawer-anim'))animDrawerClose(drawer);
  else drawer.hidden=true;
});
initActionMenus();
if(document.readyState==='loading')
  document.addEventListener('DOMContentLoaded',initDisclosures);
else initDisclosures();

var STATE_LABEL={
  pending:['待解析','gray'], parsing:['解析中','blue'],
  to_extract:['待抽取','orange'], to_review:['待校验','purple'],
  to_load:['待入库','yellow'], loading:['入库中','cyan'],
  loaded:['已入库','green'], failed:['失败','red'],
  edited:['已修改','yellow'], confirmed:['已确认','green'],
  rejected:['已拒绝','red']
};
function stateBadge(st){
  var it=STATE_LABEL[st]||[st||'—','gray'];
  return '<span class="badge '+it[1]+'">'+escHtml(it[0])+'</span>';
}
/* 全屏预览：页面里放 <div class="lightbox" id="lb" hidden>… 即可复用 */
function bindLightbox(){
  var lb=document.getElementById('lb');
  if(!lb) return;
  var img=lb.querySelector('img');
  lb.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('img.thumb'):null;
    if(t){ img.src=t.getAttribute('data-full'); lb.hidden=false; return; }
    if(e.target===lb||e.target.closest('.lbclose')){
      lb.hidden=true; img.removeAttribute('src');
    }
  });
  document.addEventListener('keydown',function(e){
    if(!lb.hidden&&e.key==='Escape'){ lb.hidden=true; img.removeAttribute('src'); }
  });
}
/* 文件产物链接（/files/<file_id>/…，白名单挂载，raw 不会出现） */
function fileUrl(rfId,rel){
  return '/files/'+rfId+'/'+encodeURIComponent(rel);
}
function shortName(name){
  return String(name||'');
}
/* File → base64（上传/登记共用） */
function b64(file){
  return new Promise(function(ok,no){
    var r=new FileReader();
    r.onload=function(){ok(r.result.split(',')[1]);};
    r.onerror=no;
    r.readAsDataURL(file);
  });
}
/* 抽屉动画（入库回执 #receipt 等共用）：
   hidden 仍是最终状态标记（各处 hidden 判断不动），打开走进场、关闭先出场再置 hidden。 */
function animDrawerOpen(el){
  if(!el) return;
  if(el._animClose){ el._animClose(); el._animClose=null; } /* 取消未完成的关闭，避免闪退 */
  el.classList.add('drawer-anim');       /* 打标记：仅台账抽屉吃动画，其它抽屉不变 */
  el.hidden=false;
  void el.offsetWidth;                   /* 强制回流：让初始态先落地，下一帧才过渡 */
  el.classList.add('open');
}
function animDrawerClose(el){
  if(!el||el.hidden||!el.classList.contains('open')) return;
  el.classList.remove('open');
  var done=false;
  var cancel=function(){
    done=true; el.removeEventListener('transitionend',onEnd);
    if(el._animClose===cancel) el._animClose=null;
  };
  var finish=function(){
    if(done) return;
    done=true; el.removeEventListener('transitionend',onEnd);
    if(el._animClose===cancel) el._animClose=null;
    if(!el.hidden) el.hidden=true;
  };
  var onEnd=function(e){ if(e.target===el) finish(); };
  el._animClose=cancel;
  el.addEventListener('transitionend',onEnd);
  setTimeout(finish,260);                 /* 兜底：无过渡/被降帧时也能收起 */
}
/* 入库回执/隔离抽屉（资料清单/数据预览共用）：
   页面放 #receipt/#rctitle/#rcbody/#rcclose 即可复用。只读。 */
function closeReceiptDrawer(){
  var r=document.getElementById('receipt');
  if(r) animDrawerClose(r);
}
var receiptRequest=0;
function openReceiptDrawer(fileId,resultId){
  var drawer=document.getElementById('receipt');
  if(!drawer) return;
  var single=resultId!=null, request=++receiptRequest;
  var base=single?'/api/extract-results/'+encodeURIComponent(resultId):
    '/api/sources/'+encodeURIComponent(fileId);
  document.getElementById('rctitle').textContent=single?
    '抽取结果 #'+resultId+' · 入库回执 / 隔离':'资料 #'+fileId+' · 入库回执';
  document.getElementById('rcbody').innerHTML='<div class="empty">加载中…</div>';
  animDrawerOpen(drawer);
  Promise.all([
    fetch(base+'/load-log').then(function(r){return r.json();}),
    fetch(base+'/quarantine').then(function(r){return r.json();})
  ]).then(function(res){
    if(request!==receiptRequest) return;
    var logs=(res[0].items||[]), qs=(res[1].items||[]).filter(function(q){
      return q.stage==='load';
    });
    var docHead=single?'':'<th>资料ID</th>';
    var html='<div class="msg" style="margin-bottom:6px">'+(single?'当前结果回执 ':'回执 ')+logs.length+
      ' 条（重新入库时，已有回执的记录将自动跳过）</div>';
    html+=logs.length?
      '<table class="list"><thead><tr>'+docHead+'<th>记录</th><th>动作</th>'+
      '<th>目标主键</th><th>时间</th></tr></thead><tbody>'+
      logs.map(function(l){
        return '<tr>'+(single?'':'<td class="mono">'+escHtml(l.file_id)+'</td>')+
          '<td class="num">'+(l.record_index+1)+'</td>'+
          '<td>'+escHtml({insert:'新增',update:'覆盖'}[l.action]||l.action)+'</td>'+
          '<td><code class="mono">'+escHtml(l.target_pk)+'</code></td>'+
          '<td class="num">'+fmtTime(l.loaded_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">暂无回执记录</div>';
    html+='<div class="msg" style="margin:12px 0 6px">'+(single?'当前结果隔离 ':'隔离 ')+qs.length+
      ' 条（当前为只读；重新入库将重试未写入的记录）</div>';
    html+=qs.length?
      '<table class="list"><thead><tr>'+docHead+'<th>记录</th><th>原因</th>'+
      '<th>时间</th></tr></thead><tbody>'+
      qs.map(function(q){
        return '<tr>'+(single?'':'<td class="mono">'+escHtml(q.file_id)+'</td>')+
          '<td class="num">'+(q.record_index+1)+'</td>'+
          '<td>'+escHtml(q.reason)+'</td>'+
          '<td class="num">'+fmtTime(q.created_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">暂无隔离记录</div>';
    document.getElementById('rcbody').innerHTML=html;
  }).catch(function(){
    if(request===receiptRequest) document.getElementById('rcbody').innerHTML=
      '<div class="empty">读取失败：平台库不可用</div>';
  });
}
/* ---- 列表分页共用组件（资料/抽取规则/校验台账/入库）。
   每页条数用户可选（10/20/50/100，默认 20，localStorage 记忆，全站点统一）；
   列表为空时隐藏分页条；翻页后滚回列表顶部；筛选变化由各页自行回第 1 页。
   markup 约定：
     <div class="pager" id="…" hidden><span class="pginfo"></span>
       <button type="button" class="pgprev">上一页</button>
       <button type="button" class="pgnext">下一页</button></div>
   用法：var pg=bindPager(el,function(d){page+=d;render();},
                        function(n){size=n;page=1;render();});
        pg.render(pageSlice(list,page,size))  // 前端分页
        pg.render({page:p,pages:ps,total:total,per:size})  // 服务端分页（资料页） */
var PAGE_SIZES=[10,20,50,100];
function getListPer(){
  var n=Number(localStorage.getItem('c1.list_per'));
  return PAGE_SIZES.indexOf(n)>=0?n:20;
}
function pageSlice(list,page,per){
  per=per||getListPer();
  var pages=Math.max(1,Math.ceil(list.length/per));
  var p=Math.min(Math.max(1,page||1),pages);
  return {rows:list.slice((p-1)*per,p*per),page:p,pages:pages,total:list.length,per:per};
}
function seqNo(info,i){ return (info.page-1)*info.per+i+1; }
function bindPager(el,onGo,onSize){
  var prev=el.querySelector('.pgprev'),next=el.querySelector('.pgnext');
  var sel=null;
  if(onSize){
    sel=document.createElement('select');
    sel.className='pagesize';
    sel.title='每页条数';
    PAGE_SIZES.forEach(function(n){
      var o=document.createElement('option');
      o.value=n;o.textContent=n+' 条/页';
      sel.appendChild(o);
    });
    el.insertBefore(sel,el.firstChild);
    sel.onchange=function(){
      try{localStorage.setItem('c1.list_per',sel.value);}catch(e){}
      onSize(Number(sel.value));
    };
  }
  function go(d){
    onGo(d);
    if(el.parentNode) el.parentNode.scrollIntoView({behavior:'smooth',block:'start'});
  }
  prev.onclick=function(){ if(!prev.disabled) go(-1); };
  next.onclick=function(){ if(!next.disabled) go(1); };
  return {render:function(info){
    el.hidden=info.total===0;
    if(sel) sel.value=info.per||getListPer();
    el.querySelector('.pginfo').textContent=
      '共 '+info.total+' 条 · 第 '+info.page+'/'+info.pages+' 页';
    prev.disabled=info.page<=1;
    next.disabled=info.page>=info.pages;
  }};
}
(function(){
  var r=document.getElementById('receipt');
  if(!r) return;
  var c=document.getElementById('rcclose');
  if(c) c.onclick=closeReceiptDrawer;
  r.addEventListener('click',function(e){ if(e.target===r) closeReceiptDrawer(); });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape') closeReceiptDrawer();
  });
})();
/* ---- 台账列宽可拖动（所有 table.list 通用，2026-11-25）----
   列宽存 localStorage，按「页面 pathname + 表序号」隔离；拖动表头右边缘改宽，
   双击表格顶部空白处恢复默认。用 colgroup 控宽，table-layout:fixed 下最稳。 */
(function initColResize(){
  var KEY='c1.colwidth';
  function store(){
    try{ return JSON.parse(localStorage.getItem(KEY)||'{}'); }catch(e){ return {}; }
  }
  function save(o){ try{ localStorage.setItem(KEY,JSON.stringify(o)); }catch(e){} }
  function tableKey(tbl){
    var tables=Array.prototype.slice.call(document.querySelectorAll('table.list'));
    return location.pathname+'#'+tables.indexOf(tbl);
  }
  function setup(tbl){
    if(tbl.__colReady) return;
    var heads=tbl.querySelectorAll('thead th');
    if(!heads.length) return;
    /* 自动包裹滚动容器：所有台账表格宽于容器时出横向滚动条；
       弹窗内小表（.dpanel/.pipe-panel）不包，已有 .tblscroll 的不重复包 */
    if(!tbl.parentElement.classList.contains('tblscroll')
       && !tbl.closest('.dpanel,.pipe-panel,.stgmain')){
      var wrap=document.createElement('div');
      wrap.className='tblscroll';
      tbl.parentNode.insertBefore(wrap,tbl);
      wrap.appendChild(tbl);
    }
    tbl.__colReady=true;
    var n=heads.length;
    var cg=tbl.querySelector('colgroup');
    if(!cg){ cg=document.createElement('colgroup'); tbl.insertBefore(cg,tbl.firstChild); }
    function fillCols(){
      if(cg.children.length!==n){
        cg.innerHTML='';
        for(var i=0;i<n;i++) cg.appendChild(document.createElement('col'));
      }
    }
    fillCols();
    var k=tableKey(tbl), saved=store()[k]||[];
    function apply(){
      fillCols();
      if(saved.length) tbl.style.tableLayout='fixed';
      for(var i=0;i<n;i++){
        var w=saved[i];
        cg.children[i].style.width=w?w+'px':'';
        heads[i].classList.add('col-resizable');
        if(!heads[i].querySelector('.col-grip')){
          var g=document.createElement('span'); g.className='col-grip';
          heads[i].appendChild(g);
        }
      }
    }
    apply();
    tbl.addEventListener('mousedown',function(e){
      var grip=e.target.closest?e.target.closest('.col-grip'):null;
      if(!grip) return;
      var th=grip.parentNode, idx=Array.prototype.indexOf.call(heads,th);
      if(idx<0) return;
      e.preventDefault();
      var startX=e.clientX;
      var startW=th.getBoundingClientRect().width;
      var min=Math.max(28,parseInt(getComputedStyle(th).paddingLeft,10)*2+24);
      /* 冻结当前各列宽再切 fixed，避免 auto 布局下拖动抖动 */
      for(var j=0;j<n;j++){
        if(!cg.children[j].style.width)
          cg.children[j].style.width=Math.round(heads[j].getBoundingClientRect().width)+'px';
      }
      tbl.style.tableLayout='fixed';
      document.body.style.cursor='col-resize';
      document.body.style.userSelect='none';
      function move(ev){
        var w=Math.max(min,Math.round(startW+(ev.clientX-startX)));
        cg.children[idx].style.width=w+'px';
      }
      function up(){
        document.removeEventListener('mousemove',move);
        document.removeEventListener('mouseup',up);
        document.body.style.cursor=''; document.body.style.userSelect='';
        saved=cg.children.length?Array.prototype.map.call(cg.children,function(c){
          return parseInt(c.style.width,10)||0; }):[];
        var all=store(); all[k]=saved; save(all);
      }
      document.addEventListener('mousemove',move);
      document.addEventListener('mouseup',up);
    });
    /* 双击表头恢复默认列宽 */
    tbl.addEventListener('dblclick',function(e){
      if(!e.target.closest||!e.target.closest('thead th')) return;
      var all=store(); delete all[k]; save(all);
      saved=[];
      tbl.style.tableLayout='';
      for(var i=0;i<n;i++) cg.children[i].style.width='';
    });
  }
  function boot(){
    document.querySelectorAll('table.list').forEach(setup);
    /* 动态渲染的表格（thead 后生成）补绑定 */
    var mo=new MutationObserver(function(){
      document.querySelectorAll('table.list').forEach(setup);
    });
    mo.observe(document.body,{childList:true,subtree:true});
  }
  if(document.readyState==='loading')
    document.addEventListener('DOMContentLoaded',boot);
  else boot();
})();

/* ---- 流程条组件已移除（2026-11-22 用户确认入库页也不需要） ---- */
/* 字段名规范化（自动对齐共用口径）：小写＋去空格/下划线 */
function normKey(s){ return String(s==null?'':s).toLowerCase().replace(/[\s_]/g,''); }
