/* web/sources.js — 资料清单（唯一功能入口）：列表/筛选/分页 + 上传登记 +
   解析/重放/预览/入库/回执/删除 + 文件流程追踪弹窗。
   模型：一条资料 = 一次运行（file_id 为键）。 */
var page=1, total=0, q='', kind='', fstate='', size=getListPer(), qTimer=null;
var itemsCache=[];
var rows=document.getElementById('rows'),empty=document.getElementById('empty');
var pg=bindPager(document.getElementById('pager'),
  function(d){ page+=d; load(); },
  function(n){ size=n; page=1; load(); });

function srcUrl(row){ return '/srcfiles/'+row.id; }

function render(items){
  rows.innerHTML=items.map(function(r,i){
    var sha=String(r.sha256||'');
    var st=stateBadge(r.state);
    var rule=r.rule_version_id?'已绑定 v'+escHtml(r.current_version||''):'—';
    var canReview=['to_review','to_load','loaded'].indexOf(r.state)>=0;
    var canLoad=r.state==='to_load';
    var canReplay=['to_extract','to_review','to_load','failed'].indexOf(r.state)>=0;
    return '<tr data-id="'+r.id+'">'+
      '<td class="seq">'+((page-1)*size+i+1)+'</td>'+
      '<td class="mono">'+r.id+'</td>'+
      '<td><div class="namecell">'+thumbHtml(r.name,srcUrl(r))+
        '<a class="nm pipe-link" href="#" data-pipe="'+r.id+
        '" data-name="'+escHtml(r.name)+'" title="查看该文件流程">'+
        escHtml(r.name)+'</a></div></td>'+
      '<td>'+(KIND_LABEL[r.kind]||escHtml(r.kind))+'</td>'+
      '<td class="num">'+fmtSize(r.size_bytes)+'</td>'+
      '<td>'+st+'</td>'+
      '<td>'+rule+'</td>'+
      '<td><code class="mono" title="'+escHtml(sha)+'">'+
        escHtml(sha.slice(0,8))+'</code></td>'+
      '<td>'+escHtml(r.tags||'—')+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-pipe="'+r.id+
        '" data-name="'+escHtml(r.name)+'" title="查看流程">流程</button>'+
        '<a class="linkbtn" href="'+srcUrl(r)+'?download=1">下载</a>'+
        (r.state==='pending'||r.state==='failed'
          ? '<button type="button" class="linkbtn" data-parse="'+r.id+'">解析</button>'
          : '')+
        (canReplay
          ? '<button type="button" class="linkbtn" data-replay="'+r.id+
            '" data-name="'+escHtml(r.name)+'">重放</button>'
          : '')+
        (canReview
          ? '<a class="linkbtn" href="/preview?file='+r.id+'">预览</a>'
          : '')+
        (canLoad
          ? '<button type="button" class="linkbtn" data-load="'+r.id+'">入库</button>'
          : '')+
        (r.state==='loaded'||r.state==='to_load'
          ? '<button type="button" class="linkbtn" data-rc="'+r.id+'">回执</button>'
          : '')+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  empty.hidden=items.length>0;
  pg.render({page:page,pages:Math.max(1,Math.ceil(total/size)),total:total,per:size});
}
document.getElementById('q').addEventListener('input',function(){
  var v=this.value.trim(); clearTimeout(qTimer);
  qTimer=setTimeout(function(){ q=v; page=1; load(); },300);
});
document.getElementById('kind').onchange=function(){ kind=this.value; page=1; load(); };
document.getElementById('fstate').onchange=function(){ fstate=this.value; page=1; load(); };

function api(method,path,body){
  return fetch(path,{method:method,
    headers:{'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});});
}

rows.addEventListener('click',function(e){
  var t=e.target.closest?e.target.closest('[data-pipe]'):null;
  if(t){ e.preventDefault(); openPipe(+t.getAttribute('data-pipe'),
    t.getAttribute('data-name')||t.textContent); return; }
  var b=e.target.closest?e.target.closest('[data-del]'):null;
  if(b){
    var id=b.getAttribute('data-del'),name=b.getAttribute('data-name');
    if(!confirm('确认删除「'+name+'」的登记记录及其原件文件？\n已生成的产物不受影响。')) return;
    api('DELETE','/api/sources/'+id).then(function(o){
      if(o.s===409){ alert('不能删除：'+(o.j.error||'正在处理或已入库')); return; }
      if(!o.j.ok){ alert('删除失败：'+(o.j.error||o.s)); return; }
      load();
    }).catch(function(){ alert('删除失败：平台库不可用'); });
    return;
  }
  var p=e.target.closest?e.target.closest('[data-parse]'):null;
  if(p){
    var pid=p.getAttribute('data-parse');
    api('POST','/api/sources/'+pid+'/parse',{}).then(function(o){
      if(o.s===200&&o.j.ok) load();
      else alert('解析失败：'+(o.j.error||o.s));
    }).catch(function(){ alert('解析失败：平台库不可用'); });
    return;
  }
  var rp=e.target.closest?e.target.closest('[data-replay]'):null;
  if(rp){
    var rid=rp.getAttribute('data-replay'),rname=rp.getAttribute('data-name');
    if(!confirm('确认重放解析「'+rname+'」？\n将清空该资料的暂存、产物、回执与校验结论，原地重新解析。')) return;
    api('POST','/api/sources/'+rid+'/reparse',{}).then(function(o){
      if(o.s===200&&o.j.ok) load();
      else alert('重放失败：'+(o.j.error||o.s));
    }).catch(function(){ alert('重放失败：平台库不可用'); });
    return;
  }
  var ld=e.target.closest?e.target.closest('[data-load]'):null;
  if(ld){
    var lid=+ld.getAttribute('data-load');
    openLoadWizard({fileId:lid, ruleId:null, getSample:function(){return null;}});
    return;
  }
  var rc=e.target.closest?e.target.closest('[data-rc]'):null;
  if(rc){ openReceiptDrawer(+rc.getAttribute('data-rc')); return; }
});
function load(){
  var u='/api/sources?page='+page+'&size='+size+'&q='+encodeURIComponent(q)+
    '&kind='+encodeURIComponent(kind)+'&state='+encodeURIComponent(fstate);
  fetch(u).then(function(r){
    if(r.status===503){ document.getElementById('degraded').hidden=false;
      total=0; itemsCache=[]; render([]); return null; }
    document.getElementById('degraded').hidden=true; return r.json();
  }).then(function(j){
    if(!j) return;
    total=j.total||0; itemsCache=j.items||[]; render(itemsCache);
  }).catch(function(){ document.getElementById('degraded').hidden=false; render([]); });
};

/* 上传 = 只登记不解析（不去重，每次新行）；单文件 */
document.getElementById('upbtn').onclick=function(){ document.getElementById('picker').click(); };
document.getElementById('picker').onchange=async function(){
  var fs=this.files; this.value='';
  if(!fs.length) return;
  var msg=document.getElementById('upmsg');
  msg.hidden=false; msg.textContent='正在登记…';
  var added=0,fail=[];
  for(var i=0;i<fs.length;i++){
    var f=fs[i];
    if(f.size>20*1024*1024){ fail.push(f.name+'（超过 20MB）'); continue; }
    try{
      var res=await fetch('/api/sources',{method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({name:f.name,data:await b64(f)})});
      var j=await res.json();
      if(j.ok) added++;
      else fail.push(f.name+'（'+(j.error||res.status)+'）');
    }catch(e){ fail.push(f.name+'（网络错误）'); }
  }
  var parts=[];
  if(added) parts.push('已登记 '+added+' 个');
  if(fail.length) parts.push('失败：'+fail.join('、'));
  msg.innerHTML=(fail.length?'<span class="err">':'<span class="ok">')+
    escHtml(parts.join(' · '))+'</span>';
  page=1; load();
};

/* ---- 文件流程追踪弹窗：一资料=单链路，四节点，点节点左列表右详情 ---- */
var pipeData=null, pipeNode='parse', pipeSel=0;
var NODES=[['parse','解析'],['extract','抽取'],['review','校验'],['load','入库']];

function nodeState(st,key){
  st=String(st||'');
  if(st==='failed') return 'fail';
  if(!st) return '';
  var rank={pending:0,parsing:1,to_extract:2,to_review:3,to_load:4,
            loading:5,loaded:6}[st];
  if(rank==null) return '';
  var need={parse:1,extract:2,review:3,load:4}[key];
  if(st==='parsing'&&key==='parse') return 'doing';
  if(st==='loading'&&key==='load') return 'doing';
  return rank>=need?'done':'';
}
function nodeDesc(key,p){
  if(key==='parse') return (p.parse_artifacts||[]).indexOf('对照报告.html')>=0
    ? '对照报告已生成' : '尚未解析';
  if(key==='extract') return p.rule?((p.rule.name||'规则')+' v'+(p.rule.version||1)):'未绑定规则';
  if(key==='review'){
    var c=p.review_counts||{}, n=Object.keys(c).reduce(function(a,k){return a+c[k];},0);
    return n?(n+' 条 · 确认 '+(c.confirmed||0)):'暂无记录';
  }
  var l=p.load||{}, acts=p.load_actions||{};
  return l.target_table?((l.target_table)+' · '+((acts.insert||0)+(acts.update||0))+' 条')
    :'未入库';
}
function pipeItems(key,p){
  var out=[];
  if(key==='parse'){
    (p.parse_artifacts||[]).forEach(function(n){
      out.push({label:n,kind:'artifact',url:'/files/'+p.file_id+'/'+encodeURIComponent(n)});
    });
  }else if(key==='extract'){
    if(p.rule) out.push({label:(p.rule.name||'规则')+' v'+(p.rule.version||1),kind:'version',rule:p.rule});
  }else if(key==='review'){
    var c=p.review_counts||{};
    ['confirmed','edited','rejected','pending'].forEach(function(k){
      if(c[k]) out.push({label:k,kind:'review',state:k,n:c[k]});
    });
  }else if(key==='load'){
    var l=p.load||{};
    if(l.target_table) out.push({label:l.target_table,kind:'table',load:l,actions:p.load_actions||{}});
  }
  return out;
}
function pipeDetail(key,item,p){
  if(!item) return '<div class="empty">暂无内容</div>';
  var h='';
  if(item.kind==='version'){
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<div class="kv"><b>规则 ID</b>'+escHtml(item.rule.rule_id)+'</div>'+
      '<div class="kv"><b>版本 ID</b>'+escHtml(item.rule.version_id)+'</div>'+
      '<a class="linkbtn" href="/extract?rule='+encodeURIComponent(item.rule.rule_id)+
      '" target="_blank" rel="noopener">打开抽取规则 →</a>';
  }else if(item.kind==='review'){
    var label={confirmed:'已确认',edited:'已修改',rejected:'已拒绝',pending:'待校验'}[item.state]||item.state;
    h='<h4>'+escHtml(label)+' · '+item.n+' 条</h4>'+
      '<a class="linkbtn" href="/preview?file='+p.file_id+
      '" target="_blank" rel="noopener">打开数据预览 →</a>';
  }else if(item.kind==='table'){
    var acts=item.actions||{};
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<div class="kv"><b>业务库</b>'+escHtml(item.load.db_name||'—')+'</div>'+
      '<div class="kv"><b>写入方式</b>'+escHtml(item.load.write_mode||'—')+'</div>'+
      '<div class="kv"><b>新增/覆盖</b>'+(acts.insert||0)+' / '+(acts.update||0)+'</div>'+
      '<a class="linkbtn" href="/dashboard?ds='+encodeURIComponent(item.load.datasource_id||'')+
      '&table='+encodeURIComponent(item.label)+
      '" target="_blank" rel="noopener">查看数据看板 →</a>';
  }else{
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<a class="linkbtn" href="'+escHtml(item.url)+'" target="_blank">打开产物 →</a>';
  }
  return h;
}
function renderPipeDetail(){
  var p=pipeData||{}, items=pipeItems(pipeNode,p);
  if(pipeNode==='parse'){
    var arts=p.parse_artifacts||[];
    var card=function(title,desc,name){
      var ok=arts.indexOf(name)>=0;
      return '<div class="parse-card"><h4>'+escHtml(title)+'</h4>'+
        '<p class="msg">'+escHtml(desc)+'</p>'+
        (ok?('<a class="linkbtn" target="_blank" rel="noopener" href="/files/'+
          p.file_id+'/'+encodeURIComponent(name)+'">打开'+escHtml(title)+' →</a>'):
          '<span class="msg">暂无产物</span>')+'</div>';
    };
    document.getElementById('pipeDetailBox').innerHTML=
      '<div class="pipe-view parse-pair">'+
        card('解析报告','页面图与结构化结果逐项对照','对照报告.html')+
        card('parse.json','标准契约完整产物','parse.json')+
      '</div>';
    return;
  }
  if(pipeSel>=items.length) pipeSel=0;
  var listHtml=items.length?items.map(function(x,i){
    return '<div class="pl-item'+(i===pipeSel?' on':'')+'" data-psi="'+i+'">'+
      escHtml(x.label)+'</div>';
  }).join(''):'<div class="pl-item">暂无条目</div>';
  document.getElementById('pipeDetailBox').innerHTML=
    '<div class="pipe-list" id="pipeList">'+listHtml+'</div>'+
    '<div class="pipe-view" id="pipeViewIn">'+pipeDetail(pipeNode,items[pipeSel],p)+'</div>';
  document.getElementById('pipeList').onclick=function(e){
    var d=e.target.closest?e.target.closest('[data-psi]'):null;
    if(!d) return;
    pipeSel=+d.getAttribute('data-psi'); renderPipeDetail();
  };
}
function renderPipe(){
  var p=pipeData||{};
  document.getElementById('pipeFlow').innerHTML=NODES.map(function(n){
    var st=nodeState(p.state,n[0]);
    return '<button type="button" class="pipe-node '+st+
      (pipeNode===n[0]?' on':'')+'" data-pn="'+n[0]+'">'+
      '<div class="pn-t"><span class="dot"></span>'+n[1]+'</div>'+
      '<div class="pn-d" title="'+escHtml(nodeDesc(n[0],p))+'">'+
      escHtml(nodeDesc(n[0],p))+'</div></button>';
  }).join('');
  document.getElementById('pipeFlow').onclick=function(e){
    var b=e.target.closest?e.target.closest('[data-pn]'):null;
    if(!b) return;
    pipeNode=b.getAttribute('data-pn'); pipeSel=0; renderPipe();
  };
  renderPipeDetail();
}
function openPipe(fileId,name){
  var d=document.getElementById('pipe');
  document.getElementById('pipeTitle').textContent='文件流程追踪 · '+name;
  document.getElementById('pipeBody').innerHTML='<div class="empty">加载中…</div>';
  d.hidden=false;
  fetch('/api/sources/'+fileId+'/pipeline').then(function(r){
    return r.json().then(function(j){return {ok:r.ok,j:j};});
  }).then(function(o){
    if(!o.ok||!o.j.ok){
      document.getElementById('pipeBody').innerHTML=
        '<div class="empty">读取失败：'+escHtml((o.j&&o.j.error)||'平台库不可用')+'</div>';
      return;
    }
    pipeData=o.j.pipeline||{}; pipeNode='parse'; pipeSel=0;
    document.getElementById('pipeBody').innerHTML=
      '<div class="pipe-flow" id="pipeFlow"></div>'+
      '<div class="pipe-detail" id="pipeDetailBox"></div>';
    renderPipe();
  }).catch(function(e){
    document.getElementById('pipeBody').innerHTML=
      '<div class="empty">读取失败：'+escHtml(String(e))+'</div>';
  });
}
document.getElementById('pipeClose').onclick=function(){ document.getElementById('pipe').hidden=true; };
document.getElementById('pipe').addEventListener('click',function(e){ if(e.target===this) this.hidden=true; });
document.addEventListener('keydown',function(e){
  if(e.key==='Escape') document.getElementById('pipe').hidden=true;
});

/* 深链 ?state= 过滤（工作台卡片跳转） */
var qs=new URLSearchParams(location.search);
if(qs.get('state')){ fstate=qs.get('state'); var sel=document.getElementById('fstate'); if(sel) sel.value=fstate; }

bindLightbox();
load();
