/* web/sources.js — 资料库：列表/搜索/过滤/分页 + 上传登记 + 删除保护 */
var page=1, total=0, q='', kind='', size=getListPer(), qTimer=null;
var rows=document.getElementById('rows'),empty=document.getElementById('empty');
var pg=bindPager(document.getElementById('pager'),
  function(d){ page+=d; load(); },
  function(n){ size=n; page=1; load(); });

function srcUrl(row){
  return '/srcfiles/'+row.id;
}
function render(items){
  rows.innerHTML=items.map(function(r,i){
    var sha=String(r.sha256||'');
    return '<tr data-id="'+r.id+'">'+
      '<td class="seq">'+((page-1)*size+i+1)+'</td>'+
      '<td class="mono">'+r.id+'</td>'+
      '<td><div class="namecell">'+thumbHtml(r.name,srcUrl(r))+
        '<span class="nm" title="'+escHtml(r.name)+'">'+escHtml(r.name)+'</span></div></td>'+
      '<td>'+(KIND_LABEL[r.kind]||escHtml(r.kind))+'</td>'+
      '<td class="num">'+fmtSize(r.size_bytes)+'</td>'+
      '<td><code class="mono" title="'+escHtml(sha)+'">'+escHtml(sha.slice(0,8))+'</code></td>'+
      '<td>'+escHtml(r.tags||'—')+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<a class="linkbtn" href="/extract?from_source='+r.id+'" title="在提取页使用此文件">提取</a>'+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  empty.hidden=items.length>0;
  pg.render({page:page,pages:Math.max(1,Math.ceil(total/size)),total:total,per:size});
}
function load(){
  var u='/api/sources?page='+page+'&size='+size+'&q='+encodeURIComponent(q)+
    '&kind='+encodeURIComponent(kind);
  fetch(u).then(function(r){
    if(r.status===503){
      document.getElementById('degraded').hidden=false;
      total=0; render([]);
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

rows.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-del]'):null;
  if(!b) return;
  var id=b.getAttribute('data-del'),name=b.getAttribute('data-name');
  if(!confirm('确认删除「'+name+'」的登记记录及其原件文件？\n已生成的任务产物不受影响。')) return;
  fetch('/api/sources/'+id,{method:'DELETE'}).then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});})
    .then(function(o){
      if(o.s===409){ alert('不能删除：'+(o.j.error||'已被任务引用')); return; }
      if(!o.j.ok){ alert('删除失败：'+(o.j.error||o.s)); return; }
      load();
    }).catch(function(){ alert('删除失败：平台库不可用'); });
});

/* 上传 = 只登记不提取；逐个 POST，哈希命中提示复用（b64 在 shell.js） */
document.getElementById('upbtn').onclick=function(){
  document.getElementById('picker').click();
};
document.getElementById('picker').onchange=async function(){
  var fs=this.files; this.value='';
  if(!fs.length) return;
  var msg=document.getElementById('upmsg');
  msg.hidden=false; msg.textContent='正在登记…';
  var added=0,reused=0,fail=[];
  for(var i=0;i<fs.length;i++){
    var f=fs[i];
    if(f.size>20*1024*1024){ fail.push(f.name+'（超过 20MB）'); continue; }
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
  if(reused) parts.push('内容相同，已复用 '+reused+' 个');
  if(fail.length) parts.push('失败：'+fail.join('、'));
  msg.innerHTML=(fail.length?'<span class="err">':'<span class="ok">')+
    escHtml(parts.join(' · '))+'</span>';
  page=1; load();
};
bindLightbox();
load();