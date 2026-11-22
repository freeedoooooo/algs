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
/* 写入方式存库值不变（upsert/insert/update），显示层统一用这三句人话 */
var MODE_LABEL={
  upsert:'已存在的行覆盖更新，不存在的新增',
  insert:'全部当新行插入，重复照插（靠回执可查）',
  update:'只覆盖已存在的行，对不上号的不动'
};
function modeLabel(m){ return MODE_LABEL[m]||m||'—'; }
var STATE_LABEL={
  pending:['待处理','gray'], extracting:['提取中','blue'],
  previewed:['已预览','green'], reviewed:['已校验','purple'],
  loading:['入库中','blue'], loaded:['已入库','green'],
  failed:['失败','red'], partial:['部分入库','yellow'],
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
/* 文件产物链接（/files/<task_file_id>/…，白名单挂载，raw 不会出现） */
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
/* 入库回执/隔离抽屉（P2，tasks/staging 共用）：
   页面放 #receipt/#rctitle/#rcbody/#rcclose 即可复用。只读。 */
function closeReceiptDrawer(){
  var r=document.getElementById('receipt');
  if(r) r.hidden=true;
}
function openReceiptDrawer(taskId){
  var drawer=document.getElementById('receipt');
  if(!drawer) return;
  document.getElementById('rctitle').textContent='任务 #'+taskId+' · 入库回执';
  document.getElementById('rcbody').innerHTML='<div class="empty">加载中…</div>';
  drawer.hidden=false;
  Promise.all([
    fetch('/api/tasks/'+taskId+'/load-log').then(function(r){return r.json();}),
    fetch('/api/tasks/'+taskId+'/quarantine').then(function(r){return r.json();})
  ]).then(function(res){
    var logs=(res[0].items||[]), qs=(res[1].items||[]).filter(function(q){
      return q.stage==='load';
    });
    var html='<div class="msg" style="margin-bottom:6px">回执 '+logs.length+
      ' 条（重跑幂等：已有回执的记录跳过）</div>';
    html+=logs.length?
      '<table class="list"><thead><tr><th>task_file</th><th>记录</th><th>动作</th>'+
      '<th>目标主键</th><th>时间</th></tr></thead><tbody>'+
      logs.map(function(l){
        return '<tr><td class="mono">'+l.task_file_id+'</td>'+
          '<td class="num">'+(l.record_index+1)+'</td>'+
          '<td>'+escHtml({insert:'新增',update:'覆盖'}[l.action]||l.action)+'</td>'+
          '<td><code class="mono">'+escHtml(l.target_pk)+'</code></td>'+
          '<td class="num">'+fmtTime(l.loaded_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">还没有回执</div>';
    html+='<div class="msg" style="margin:12px 0 6px">隔离 '+qs.length+
      ' 条（本轮只读；重新入库会重试无回执记录）</div>';
    html+=qs.length?
      '<table class="list"><thead><tr><th>task_file</th><th>记录</th><th>原因</th>'+
      '<th>时间</th></tr></thead><tbody>'+
      qs.map(function(q){
        return '<tr><td class="mono">'+q.task_file_id+'</td>'+
          '<td class="num">'+(q.record_index+1)+'</td>'+
          '<td>'+escHtml(q.reason)+'</td>'+
          '<td class="num">'+fmtTime(q.created_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">无隔离记录</div>';
    document.getElementById('rcbody').innerHTML=html;
  }).catch(function(){
    document.getElementById('rcbody').innerHTML=
      '<div class="empty">读取失败：平台库不可用</div>';
  });
}
/* ---- 列表分页共用组件（资料/任务/模板/校验台账/入库）。
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
/* ---- 流程条（仅入库页挂载，禁止各页自绘；提取/校验页经用户确认不上）。
   markup 约定：<div class="flowbar" id="flowbar" data-cur="3"></div>
   data-cur：1=提取 2=校验 3=入库；当前节点高亮不可点，其余可点。 ---- */
(function(){
  var el=document.getElementById('flowbar');
  if(!el) return;
  var cur=el.getAttribute('data-cur');
  var steps=[['src','原件','/sources'],['1','① 提取','/'],
             ['2','② 校验','/staging'],['3','③ 入库','/load']];
  el.innerHTML=steps.map(function(s,i){
    var sep=i?'<span class="fbsep">→</span>':'';
    return sep+(s[0]===cur
      ?'<span class="fbnode on">'+s[1]+'</span>'
      :'<a class="fbnode" href="'+s[2]+'">'+s[1]+'</a>');
  }).join('');
})();
/* 字段名规范化（自动对齐共用口径）：小写＋去空格/下划线 */
function normKey(s){ return String(s==null?'':s).toLowerCase().replace(/[\s_]/g,''); }
