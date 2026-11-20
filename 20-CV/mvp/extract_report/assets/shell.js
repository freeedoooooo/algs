/* extract_report/assets/shell.js — 列表页共用小件：转义 / 格式化 / 缩略图 /
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
  pending:['待处理','gray'], extracting:['运行中','blue'],
  previewed:['已预览','green'], reviewed:['已校验','purple'],
  loading:['入库中','blue'], loaded:['已入库','green'],
  failed:['失败','red'], partial:['部分失败','yellow'],
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
/* 文件产物链接（白名单挂载，raw 不会出现） */
function fileUrl(caseName,rel){
  return '/files/'+encodeURIComponent(caseName)+'/'+encodeURIComponent(rel);
}
function shortName(name){
  return String(name||'').replace(/^\d{14}(-\d+)?_/,'');
}