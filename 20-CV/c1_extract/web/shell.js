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
          '<td>'+escHtml(l.action)+'</td>'+
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