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
        '<a class="nm pipe-link" href="#" data-pipe="'+r.id+
        '" data-name="'+escHtml(r.name)+
        '" title="查看该文件流程">'+escHtml(r.name)+'</a></div></td>'+
      '<td>'+(KIND_LABEL[r.kind]||escHtml(r.kind))+'</td>'+
      '<td class="num">'+fmtSize(r.size_bytes)+'</td>'+
      '<td><code class="mono" title="'+escHtml(sha)+'">'+escHtml(sha.slice(0,8))+'</code></td>'+
      '<td>'+escHtml(r.tags||'—')+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-pipe="'+r.id+
        '" data-name="'+escHtml(r.name)+'" title="查看该文件流程">查看</button>'+
        '<a class="linkbtn" href="'+srcUrl(r)+'?download=1" title="下载原件">下载</a>'+
        '<a class="linkbtn" href="/parse?from_source='+r.id+'" title="在解析页使用此文件">解析</a>'+
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
  var a=e.target.closest?e.target.closest('[data-pipe]'):null;
  if(a){ e.preventDefault(); openPipe(a.getAttribute('data-pipe'),
    a.getAttribute('data-name')||a.textContent); return; }
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

/* 上传 = 只登记不解析；逐个 POST，哈希命中提示复用（b64 在 shell.js） */
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
/* ---- 文件流程追踪弹窗：顶部切 task，四节点流程，点节点左列表右详情 ---- */
var pipeData=null, pipeCur=0, pipeNode='parse', pipeSel=0;
var NODES=[['parse','解析'],['extract','抽取'],['review','校验'],['load','入库']];

function nodeState(s,key){
  var st=String(s||'');
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
function nodeDesc(key,it){
  var t=it.task||{}, tf=it.task_file_id;
  if(key==='parse') return (it.parse_artifacts||[]).indexOf('对照报告.html')>=0
    ? '对照报告已生成' : (tf?'暂无报告':'尚未解析');
  if(key==='extract') return t.rule?((t.rule.name||'规则')+' v'+(t.rule.version||1)):'未绑定规则';
  if(key==='review'){
    var c=it.review_counts||{}, n=Object.keys(c).reduce(function(a,k){return a+c[k];},0);
    return n?(n+' 条 · 确认 '+(c.confirmed||0)):(tf?'暂无记录':'尚未抽取');
  }
  var l=t.load||{}, acts=it.load_actions||{};
  return l.target_table?((l.target_table)+' · '+((acts.insert||0)+(acts.update||0))+' 条')
    :(t.state==='loaded'?'已入库':'未入库');
}

function pipeItems(key,it){
  var t=it.task||{}, tf=it.task_file_id, out=[];
  if(key==='parse'){
    (it.parse_artifacts||[]).forEach(function(n){
      out.push({label:n, kind:n, url:'/files/'+tf+'/'+encodeURIComponent(n)});
    });
  }else if(key==='extract'){
    if(t.rule){
      out.push({label:(t.rule.name||'规则')+' v'+(t.rule.version||1),
                kind:'version', rule_id:t.rule.rule_id, version_id:t.rule.version_id});
    }
  }else if(key==='review'){
    var c=it.review_counts||{};
    ['confirmed','edited','rejected','pending'].forEach(function(k){
      if(c[k]) out.push({label:k, kind:'review', state:k, n:c[k]});
    });
  }else if(key==='load'){
    var l=t.load||{};
    if(l.target_table) out.push({label:l.target_table,kind:'table',load:l,
      actions:it.load_actions||{}});
  }
  return out;
}

function pipeDetail(key,item,it){
  if(!item) return '<div class="empty">暂无内容</div>';
  var t=it.task||{}, h='';
  if(item.kind==='version'){
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<div class="kv"><b>规则 ID</b>'+escHtml(item.rule_id)+'</div>'+
      '<div class="kv"><b>版本 ID</b>'+escHtml(item.version_id)+'</div>'+
      '<p class="msg">字段映射与转换定义在抽取规则页查看。</p>'+
      '<a class="linkbtn" href="/extract?rule='+encodeURIComponent(item.rule_id)+
      '" target="_blank" rel="noopener">打开抽取规则 →</a>';
  }else if(item.kind==='review'){
    var label={confirmed:'已确认',edited:'已修改',rejected:'已拒绝',pending:'待校验'}[item.state]||item.state;
    h='<h4>'+escHtml(label)+' · '+item.n+' 条</h4>'+
      '<p class="msg">逐条核对请到数据预览页。</p>'+
      '<a class="linkbtn" href="/preview?task='+encodeURIComponent(t.task_id)+
      (it.task_file_id?('&file='+encodeURIComponent(it.task_file_id)):'')+
      '" target="_blank" rel="noopener">打开数据预览 →</a>';
  }else if(item.kind==='table'){
    var acts=item.actions||{};
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<div class="kv"><b>业务库</b>'+escHtml(item.load.db_name||'—')+'（'+escHtml(item.load.datasource_name||'—')+'）</div>'+
      '<div class="kv"><b>写入方式</b>'+escHtml(item.load.write_mode||'—')+'</div>'+
      '<div class="kv"><b>新增/覆盖</b>'+(acts.insert||0)+' / '+(acts.update||0)+'</div>'+
      '<a class="linkbtn" href="/dashboard?ds='+encodeURIComponent(item.load.datasource_id)+
      '&table='+encodeURIComponent(item.label)+
      '" target="_blank" rel="noopener">查看数据看板 →</a>';
  }else{
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<p class="msg">点击打开产物（新窗口）。</p>'+
      '<a class="linkbtn" href="'+escHtml(item.url)+'" target="_blank">打开产物 →</a>';
  }
  return h;
}

function renderPipeDetail(){
  var it=pipeData[pipeCur]||{}, items=pipeItems(pipeNode,it);
  /* 解析节点特殊：左侧解析报告、右侧 parse.json 并排，不走列表+详情 */
  if(pipeNode==='parse'){
    var tf=it.task_file_id, arts=it.parse_artifacts||[];
    var card=function(title,desc,name){
      var ok=arts.indexOf(name)>=0;
      return '<div class="parse-card"><h4>'+escHtml(title)+'</h4>'+
        '<p class="msg">'+escHtml(desc)+'</p>'+
        (ok&&tf?('<a class="linkbtn" target="_blank" rel="noopener" href="/files/'+
          tf+'/'+encodeURIComponent(name)+'">打开'+escHtml(title)+' →</a>'):
          '<span class="msg">暂无产物</span>')+'</div>';
    };
    document.getElementById('pipeDetailBox').innerHTML=
      '<div class="pipe-view parse-pair">'+
        card('解析报告','页面图与结构化结果逐项对照','对照报告.html')+
        card('parse.json','c1-structure/1 标准契约完整产物','parse.json')+
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
    '<div class="pipe-view" id="pipeViewIn">'+pipeDetail(pipeNode,items[pipeSel],it)+'</div>';
  document.getElementById('pipeList').onclick=function(e){
    var d=e.target.closest?e.target.closest('[data-psi]'):null;
    if(!d) return;
    pipeSel=+d.getAttribute('data-psi'); renderPipeDetail();
  };
}

function renderPipe(){
  var its=pipeData||[];
  var sel=document.getElementById('pipeTask');
  sel.innerHTML=its.map(function(it,i){
    var t=it.task||{};
    return '<option value="'+i+'">任务 #'+escHtml(t.task_id)+
      ' · '+escHtml(t.state||'')+' · '+escHtml((t.created_at||''))+'</option>';
  }).join('')||'<option value="">无关联任务</option>';
  sel.value=String(pipeCur);
  var it=its[pipeCur]||{}, t=it.task||{};
  document.getElementById('pipeFlow').innerHTML=NODES.map(function(n){
    var st=nodeState(t.state,n[0]);
    return '<button type="button" class="pipe-node '+st+
      (pipeNode===n[0]?' on':'')+'" data-pn="'+n[0]+'">'+
      '<div class="pn-t"><span class="dot"></span>'+n[1]+'</div>'+
      '<div class="pn-d" title="'+escHtml(nodeDesc(n[0],it))+'">'+
      escHtml(nodeDesc(n[0],it))+'</div></button>';
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
    pipeData=o.j.tasks||[]; pipeCur=0; pipeNode='parse'; pipeSel=0;
    if(!pipeData.length){
      document.getElementById('pipeBody').innerHTML=
        '<div class="empty">该文件尚未关联任何任务。可先在解析页使用它。</div>';
      return;
    }
    document.getElementById('pipeBody').innerHTML=
      '<div class="pipe-switch"><span>任务</span>'+
      '<select id="pipeTask"></select>'+
      '<span>共 '+pipeData.length+' 条处理记录（最近在前）</span></div>'+
      '<div class="pipe-flow" id="pipeFlow"></div>'+
      '<div class="pipe-detail" id="pipeDetailBox"></div>';
    document.getElementById('pipeTask').onchange=function(){
      pipeCur=+this.value; pipeNode='parse'; pipeSel=0; renderPipe();
    };
    renderPipe();
  }).catch(function(e){
    document.getElementById('pipeBody').innerHTML=
      '<div class="empty">读取失败：'+escHtml(String(e))+'</div>';
  });
}

document.getElementById('pipeClose').onclick=function(){
  document.getElementById('pipe').hidden=true;
};
document.getElementById('pipe').addEventListener('click',function(e){
  if(e.target===this) this.hidden=true;
});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape') document.getElementById('pipe').hidden=true;
});

bindLightbox();
load();