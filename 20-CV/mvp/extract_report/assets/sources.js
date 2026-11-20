/* extract_report/assets/sources.js — 资料库：列表/搜索/过滤/分页 + 上传登记 + 删除保护 */
var page=1, PER=20, total=0, q='', kind='', qTimer=null;
var rows=document.getElementById('rows'),empty=document.getElementById('empty');

function srcUrl(row){
  var base=String(row.rel_path||'').split('/').pop();
  return '/srcfiles/'+encodeURIComponent(base);
}
function render(items){
  rows.innerHTML=items.map(function(r){
    var sha=String(r.sha256||'');
    return '<tr data-id="'+r.id+'">'+
      '<td><div class="namecell">'+thumbHtml(r.name,srcUrl(r))+
        '<span class="nm" title="'+escHtml(r.name)+'">'+escHtml(r.name)+'</span></div></td>'+
      '<td>'+(KIND_LABEL[r.kind]||escHtml(r.kind))+'</td>'+
      '<td class="num">'+fmtSize(r.size_bytes)+'</td>'+
      '<td><code class="mono" title="'+escHtml(sha)+'">'+escHtml(sha.slice(0,8))+'</code></td>'+
      '<td>'+escHtml(r.tags||'—')+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<a class="linkbtn" href="/?from_source='+r.id+'" title="到提取页预选此文件">提取</a>'+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  empty.hidden=items.length>0;
  document.getElementById('pager').hidden=total<=PER;
  document.getElementById('pginfo').textContent='共 '+total+' 条 · 第 '+page+' 页';
  document.getElementById('prev').disabled=page<=1;
  document.getElementById('next').disabled=page*PER>=total;
}
function load(){
  var u='/api/sources?page='+page+'&q='+encodeURIComponent(q)+
    '&kind='+encodeURIComponent(kind);
  fetch(u).then(function(r){
    if(r.status===503){
      document.getElementById('degraded').hidden=false;
      render([]); total=0;
      document.getElementById('pager').hidden=true;
      return null;
    }
    document.getElementById('degraded').hidden=true;
    return r.json();
  }).then(function(j){
    if(!j) return;
    total=j.total||0; render(j.items||[]);
  }).catch(function(){
    document.getElementById('degraded').hidden=false; render([]);
  });
}
document.getElementById('q').addEventListener('input',function(){
  var v=this.value.trim();
  clearTimeout(qTimer);
  qTimer=setTimeout(function(){ q=v; page=1; load(); },300);
});
document.getElementById('kind').onchange=function(){ kind=this.value; page=1; load(); };
document.getElementById('prev').onclick=function(){ if(page>1){page--;load();} };
document.getElementById('next').onclick=function(){ if(page*PER<total){page++;load();} };

rows.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-del]'):null;
  if(!b) return;
  var id=b.getAttribute('data-del'),name=b.getAttribute('data-name');
  if(!confirm('删除「'+name+'」的登记与规范副本？\n已产生的批次产物不受影响。')) return;
  fetch('/api/sources/'+id,{method:'DELETE'}).then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
    .then(function(o){
      if(o.s===409){ alert('不能删除：'+(o.j.reason||'已被运行引用')); return; }
      if(!o.j.ok){ alert('删除失败：'+(o.j.error||o.s)); return; }
      load();
    }).catch(function(){ alert('删除失败：平台库不可用'); });
});

/* 上传 = 只登记不提取；逐个 POST，哈希命中提示复用 */
function b64(file){
  return new Promise(function(ok,no){
    var r=new FileReader();
    r.onload=function(){ok(r.result.split(',')[1]);};
    r.onerror=no;
    r.readAsDataURL(file);
  });
}
document.getElementById('upbtn').onclick=function(){
  document.getElementById('picker').click();
};
document.getElementById('picker').onchange=async function(){
  var fs=this.files; this.value='';
  if(!fs.length) return;
  var msg=document.getElementById('upmsg');
  msg.hidden=false; msg.textContent='登记中…';
  var added=0,reused=0,fail=[];
  for(var i=0;i<fs.length;i++){
    var f=fs[i];
    if(f.size>20*1024*1024){ fail.push(f.name+'（超 20MB）'); continue; }
    try{
      var res=await fetch('/api/sources',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:f.name,data:await b64(f)})
      });
      var j=await res.json();
      if(j.ok){ j.dedup?reused++:added++; }
      else fail.push(f.name+'（'+(j.error||res.status)+'）');
    }catch(e){ fail.push(f.name+'（网络错误）'); }
  }
  var parts=[];
  if(added) parts.push('新登记 '+added+' 个');
  if(reused) parts.push('哈希命中复用 '+reused+' 个');
  if(fail.length) parts.push('失败：'+fail.join('、'));
  msg.innerHTML=(fail.length?'<span class="err">':'<span class="ok">')+
    escHtml(parts.join(' · '))+'</span>';
  page=1; load();
};
bindLightbox();
load();