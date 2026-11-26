/* web/sources.js — 资料清单（唯一功能入口）：列表/筛选/分页 + 上传登记 +
   处理/删除；文件名即下载原件。处理入口跳转 /static/process.html?file=<id>。
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
    var st=stateBadge(r.state);
    return '<tr data-id="'+r.id+'">'+
      '<td class="seq">'+((page-1)*size+i+1)+'</td>'+
      '<td class="mono">'+r.id+'</td>'+
      '<td><div class="namecell">'+thumbHtml(r.name,srcUrl(r))+
        '<a class="nm pipe-link" href="'+srcUrl(r)+'?download=1"'+
        ' title="下载原件">'+escHtml(r.name)+'</a></div></td>'+
      '<td>'+(KIND_LABEL[r.kind]||escHtml(r.kind))+'</td>'+
      '<td class="num">'+fmtSize(r.size_bytes)+'</td>'+
      '<td>'+st+'</td>'+
      '<td class="num">'+fmtTime(r.created_at)+'</td>'+
      '<td class="col-act" style="white-space:nowrap">'+
        '<a class="linkbtn" href="/static/process.html?file='+r.id+
        '" title="配置并重新执行解析/抽取/校验/入库">处理</a>'+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  empty.hidden=items.length>0;
  pg.render({page:page,pages:Math.max(1,Math.ceil(total/size)),total:total,per:size});
}
function doSearch(){
  q=document.getElementById('q').value.trim();
  kind=document.getElementById('kind').value;
  fstate=document.getElementById('fstate').value;
  page=1; load();
}
document.getElementById('q').addEventListener('keydown',function(e){
  if(e.key==='Enter'){ e.preventDefault(); clearTimeout(qTimer); doSearch(); }
});
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
  // 先做数组快照再清空 input：this.files 是 FileList 引用，直接 value='' 会把它清空
  var fs=Array.prototype.slice.call(this.files||[]); this.value='';
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

/* ---- 资料详情弹窗：一资料=单链路，四节点，点节点左列表右详情 ---- */
var pipeData=null, pipeNode='parse';
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
      '&file='+encodeURIComponent(p.file_id||'')+
      '&lt='+encodeURIComponent(item.load.load_table_id||'')+
      '" target="_blank" rel="noopener">查看数据看板 →</a>';
  }else{
    h='<h4>'+escHtml(item.label)+'</h4>'+
      '<a class="linkbtn" href="'+escHtml(item.url)+'" target="_blank">打开产物 →</a>';
  }
  return h;
}
/* 节点操作区：每个节点下都有「执行X」按钮，说明走 ? tips，按状态控制可用 */
function nodeActionHtml(key,p){
  var st=String(p.state||''), fid=p.file_id;
  var btn=function(id,label,dis,tip){
    return '<button type="button" class="btn mini" id="'+id+'" data-fid="'+fid+'"'+
      (dis?' disabled':'')+'>'+label+'</button>'+
      '<span class="hint" tabindex="0" data-tip="'+escHtml(tip||'')+'">?</span>';
  };
  var busy=st==='parsing'||st==='loading';
  if(key==='parse'){
    return btn('actParse',st==='loaded'?'测试重解析':'执行解析',busy,
      busy?'正在解析中，请稍候。':(st==='loaded'
        ?'仅重新运行解析并生成 test/ 下的新报告；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
        :'清空该资料的暂存、产物、回执与校验结论，按当前配置原地重新解析。'));
  }
  if(key==='extract'){
    var canE=st==='to_extract'||st==='to_review'||st==='to_load';
    return btn('actExtract','执行抽取',!canE||busy,
      st==='to_extract'?'按已配置的抽取规则，从解析产物生成暂存记录。'
        :(canE?'已有暂存记录，重新抽取将覆盖校验结论。':'请先执行解析，生成解析产物。'));
  }
  if(key==='review'){
    var canR=st==='to_review'||st==='to_load';
    var c=p.review_counts||{}, pend=(c.pending||0)+(c.edited||0);
    return btn('actReview','执行校验',!canR||busy||!pend,
      canR?(pend?('将全部 '+pend+' 条待审记录设为通过。'
        +(c.rejected?'另有 '+c.rejected+' 条已拒绝记录需人工处理。':'')):'暂无待审记录。')
        :'请先执行抽取，生成暂存记录。');
  }
  var canL=st==='to_load' && !!(p.load&&p.load.load_table_id);
  return btn('actLoad','执行入库',!canL||busy,
    st!=='to_load'?'请先完成校验，全部记录通过后才能入库。'
      :(p.load&&p.load.load_table_id
        ?('按已配置的入库映射写入 '+escHtml(p.load.target_table||'')+'。')
        :'请先在「配置」里绑定入库映射。'));
}
function bindNodeActions(p){
  var fid=p&&p.file_id;
  if(!fid) return;
  var refresh=function(){ load(); openPipe(+fid, pipeData.name||('资料 '+fid)); };
  var bind=function(id,fn){
    var b=document.getElementById(id);
    if(b) b.onclick=function(){
      var btn=this; btn.disabled=true;
      Promise.resolve(fn()).then(function(o){
        if(o&&o.cancel){ btn.disabled=false; return; }   // 用户取消确认框，静默
        if(!(o&&o.s===200&&o.j&&o.j.ok)){ alert('操作失败：'+((o&&o.j&&o.j.error)||(o&&o.s)||'未知')); btn.disabled=false; return; }
        refresh();
      }).catch(function(e){ alert('操作失败：'+(e&&e.message)||'平台库不可用'); btn.disabled=false; });
    };
  };
  bind('actParse',function(){
    var test=String(p.state||'')==='loaded';
    if(!confirm(test
      ?'确认测试重解析？\n仅生成 test/ 下的新产物；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
      :'确认执行解析？\n将清空暂存、产物、回执与校验结论，原地重新解析。')) return {cancel:true};
    return api('POST','/api/sources/'+fid+'/reparse',test?{test_mode:true}:{});
  });
  bind('actExtract',function(){
    var force=(String(p.state||'')==='to_review'||String(p.state||'')==='to_load');
    if(force&&!confirm('已有暂存记录，重新抽取将覆盖校验结论。确认继续？')) return {cancel:true};
    return api('POST','/api/sources/'+fid+'/extract',force?{force:true}:{});
  });
  bind('actReview',function(){
    if(!confirm('确认将全部待审记录设为通过？')) return {cancel:true};
    return api('POST','/api/sources/'+fid+'/approve-all',{});
  });
  bind('actLoad',function(){
    if(!confirm('确认按已配置的入库映射执行入库？')) return {cancel:true};
    return api('POST','/api/sources/'+fid+'/load',{});
  });
}
function renderPipeDetail(){
  var p=pipeData||{}, items=pipeItems(pipeNode,p);
  var action='<div class="pipe-actions"><div>'+nodeActionHtml(pipeNode,p)+'</div></div>';
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
      '<div class="pipe-view">'+
        action+
        '<div class="parse-pair">'+
          card('解析报告','页面图与结构化结果逐项对照','对照报告.html')+
          card('parse.json','标准契约完整产物','parse.json')+
        '</div>'+
      '</div>';
    bindNodeActions(p);
    return;
  }
  // 其他节点：与解析节点同构——操作条在上，下面用卡片承载内容
  var cards=items.length
    ? '<div class="parse-pair">'+items.map(function(it){
        return '<div class="parse-card">'+pipeDetail(pipeNode,it,p)+'</div>';
      }).join('')+'</div>'
    : '<div class="empty">暂无内容</div>';
  document.getElementById('pipeDetailBox').innerHTML=
    '<div class="pipe-view">'+action+cards+'</div>';
  bindNodeActions(p);
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
    pipeNode=b.getAttribute('data-pn'); renderPipe();
  };
  renderPipeDetail();
}
function openPipe(fileId,name){
  var d=document.getElementById('pipe');
  document.getElementById('pipeTitle').textContent='资料详情 · '+name;
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
    pipeData=o.j.pipeline||{}; pipeData.name=name; pipeNode='parse';
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
  if(e.key==='Escape'){
    document.getElementById('pipe').hidden=true;
    document.getElementById('cfg').hidden=true;
  }
});

/* ---- 资料配置弹窗：四节点（解析参数/抽取规则/校验规则/入库映射）---- */
var CFG_NODES=[['params','解析参数'],['extract','抽取规则'],
               ['review','校验规则'],['load','入库映射']];
var cfgData=null, cfgFileId=null, cfgNode='params', cfgDirty=false, cfgPending={};

function cfgMsg(t,bad){
  var e=document.getElementById('cfgMsg');
  e.textContent=t||''; e.className='msg'+(bad?' err':'');
}
function openConfig(fileId,name){
  cfgFileId=fileId; cfgNode='params'; cfgDirty=false; cfgPending={};
  document.getElementById('cfgTitle').textContent='资料配置 · '+name;
  document.getElementById('cfgBody').innerHTML='<div class="empty">加载中…</div>';
  document.getElementById('cfgSave').hidden=true;
  cfgMsg('');
  document.getElementById('cfg').hidden=false;
  fetch('/api/sources/'+fileId+'/config').then(function(r){
    return r.json().then(function(j){return {ok:r.ok,j:j};});
  }).then(function(o){
    if(!o.ok||!o.j.ok){
      document.getElementById('cfgBody').innerHTML=
        '<div class="empty">读取失败：'+escHtml((o.j&&o.j.error)||'平台库不可用')+'</div>';
      return;
    }
    cfgData=o.j;
    document.getElementById('cfgBody').innerHTML=
      '<div class="pipe-flow" id="cfgFlow"></div>'+
      '<div class="pipe-detail" id="cfgDetail"></div>';
    document.getElementById('cfgSave').hidden=false;
    renderCfg();
  }).catch(function(e){
    document.getElementById('cfgBody').innerHTML=
      '<div class="empty">读取失败：'+escHtml(String(e))+'</div>';
  });
}
function collectCfgNode(){
  if(!cfgData) return;
  if(cfgNode==='params'){
    var pv={};
    document.querySelectorAll('#cfgDetail [data-cp]').forEach(function(el){
      var key=el.getAttribute('data-cp'), v=el.value;
      var s=(cfgData.schema||[]).filter(function(p){return p.key===key;})[0]||{};
      if(s.type==='int') v=parseInt(v,10);
      else if(s.type==='float') v=parseFloat(v);
      else if(s.type==='bool') v=v==='1';
      pv[key]=v;
    });
    cfgPending.params=pv;
  }else if(cfgNode==='extract'){
    var rv=document.getElementById('cfgRule');
    if(rv) cfgPending.rule_version_id=rv.value?parseInt(rv.value,10):null;
  }else if(cfgNode==='load'){
    var ds=document.getElementById('cfgDs'),lt=document.getElementById('cfgLt');
    if(ds&&lt) cfgPending.load=(ds.value&&lt.value)
      ?{datasource_id:parseInt(ds.value,10),load_table_id:parseInt(lt.value,10)}
      :{datasource_id:null,load_table_id:null};
  }
}
function renderCfg(){
  if(!cfgData) return;
  // 节点条（复用 pipe-node 样式）
  var done={params:!!(cfgData.schema&&cfgData.schema.length),
            extract:!!cfgData.rule_version_id, review:false,
            load:!!(cfgData.load&&cfgData.load.load_table_id)};
  document.getElementById('cfgFlow').innerHTML=CFG_NODES.map(function(n){
    var d=done[n[0]]?' done':'';
    return '<button type="button" class="pipe-node '+d+(cfgNode===n[0]?' on':'')+
      '" data-cn="'+n[0]+'"><div class="pn-t"><span class="dot"></span>'+
      n[1]+'</div><div class="pn-d">'+(d?'已配置':'未配置')+'</div></button>';
  }).join('');
  document.getElementById('cfgFlow').onclick=function(e){
    var b=e.target.closest?e.target.closest('[data-cn]'):null;
    if(!b||b.getAttribute('data-cn')===cfgNode) return;
    collectCfgNode();                 // 切节点前先收集当前节点的编辑
    cfgNode=b.getAttribute('data-cn'); renderCfg();
  };
  var box=document.getElementById('cfgDetail'), h='<div class="pipe-view">';
  // tips 小图标（复用页面已引入的 hint 组件）
  var tip=function(t){ return '<span class="hint" tabindex="0" data-tip="'+
    escHtml(t||'')+'">?</span>'; };
  var spacer='<span class="hint-spacer"></span>';   // 无 tips 的行也占位，保证对齐
  var head=function(title,t){ return '<h4>'+escHtml(title)+tip(t)+'</h4>'; };
  if(cfgNode==='params'){
    h+=head('解析参数','对本次资料生效，重放解析时使用。参数定义与默认值来自服务端 schema，保存时同样经服务端校验。');
    (cfgData.schema||[]).forEach(function(p){
      if(p.hidden) return;   /* 服务端标记隐藏的参数不生成控件 */
      var key=p.key, label=p.label||key, val=cfgData.params[key];
      if(val===undefined||val===null) val=p.default;
      var desc=p.desc||p.help||'';
      h+='<div class="cfg-row"><label>'+escHtml(label)+'</label>'+
        (desc?tip(desc):spacer);
      if(p.type==='bool'){
        h+='<select data-cp="'+escHtml(key)+'">'+
          '<option value="1"'+(val?' selected':'')+'>开</option>'+
          '<option value="0"'+(!val?' selected':'')+'>关</option></select>';
      }else if(p.options||p.choices){
        var opts=p.options||p.choices;
        h+='<select data-cp="'+escHtml(key)+'">';
        opts.forEach(function(o){
          var v=(typeof o==='object')?o.value:o, t=(typeof o==='object')?o.label||o.value:o;
          h+='<option value="'+escHtml(v)+'"'+(String(v)===String(val)?' selected':'')+'>'+
            escHtml(t)+'</option>';
        });
        h+='</select>';
      }else{
        h+='<input type="text" data-cp="'+escHtml(key)+'" value="'+escHtml(val)+'"'+
          ' placeholder="'+escHtml(p.default!=null?String(p.default):'')+'">';
      }
      if(p.unit) h+='<span class="cfg-unit">'+escHtml(p.unit)+'</span>';
      h+='</div>';
    });
  }else if(cfgNode==='extract'){
    h+=head('抽取规则','在「执行抽取」时按此规则生成记录；改配置不会重抽已有记录。');
    h+='<div class="cfg-row"><label>规则版本</label>'+spacer+
      '<select id="cfgRule"><option value="">（不绑定 · 执行抽取时用默认原始透传）</option>';
    (cfgData.rules||[]).forEach(function(v){
      h+='<option value="'+v.version_id+'"'+
        (cfgData.rule_version_id===v.version_id?' selected':'')+'>'+
        escHtml(v.name+' v'+v.version+(v.current?'（当前）':''))+'</option>';
    });
    h+='</select></div>';
  }else if(cfgNode==='review'){
    h+=head('校验规则','当前校验为逐条人工改值 / 确认 / 拒绝；详情的「执行校验」可一键将全部待审记录设为通过。');
    h+='<div class="empty" style="padding:20px"><b>自动化校验规则：待实现</b></div>';
  }else{
    h+=head('入库映射','目标在「执行入库」时消费；入库映射须与资料的抽取规则匹配，配置仅登记目标，真正写入在执行入库时。');
    h+='<div class="cfg-row"><label>业务库</label>'+spacer+'<select id="cfgDs">'+
      '<option value="">（未选择）</option>';
    (cfgData.datasources||[]).forEach(function(d){
      h+='<option value="'+d.id+'"'+
        (cfgData.load&&cfgData.load.datasource_id===d.id?' selected':'')+'>'+
        escHtml(d.name+' · '+d.host+'/'+d.db_name)+'</option>';
    });
    h+='</select></div>'+
      '<div class="cfg-row"><label>入库映射</label>'+spacer+'<select id="cfgLt">'+
      '<option value="">（未选择）</option>';
    (cfgData.load_tables||[]).forEach(function(t){
      h+='<option value="'+t.id+'" data-ds="'+t.datasource_id+'"'+
        (cfgData.load&&cfgData.load.load_table_id===t.id?' selected':'')+'>'+
        escHtml(t.target_table+' · '+t.write_mode)+'</option>';
    });
    h+='</select></div>';
  }
  h+='</div>';
  box.innerHTML=h;
  // 数据源变化时过滤入库映射
  var ds=document.getElementById('cfgDs'), lt=document.getElementById('cfgLt');
  if(ds&&lt){
    ds.onchange=function(){
      var did=this.value;
      Array.prototype.forEach.call(lt.options,function(o){
        if(!o.value) return;
        o.hidden=!!did&&o.getAttribute('data-ds')!==did;
      });
      lt.value='';
    };
    if(cfgData.load&&cfgData.load.datasource_id) ds.onchange();
  }
  document.querySelectorAll('#cfgDetail [data-cp]').forEach(function(el){
    el.onchange=function(){ cfgDirty=true; cfgMsg('有未保存的修改'); };
  });
  ['cfgRule','cfgDs','cfgLt'].forEach(function(id){
    var el=document.getElementById(id);
    if(el) el.onchange=function(){ cfgDirty=true; cfgMsg('有未保存的修改'); };
  });
}
document.getElementById('cfgSave').onclick=function(){
  if(!cfgData){ return; }
  collectCfgNode();                       // 收集当前节点
  var body=cfgPending;
  if(!Object.keys(body).length){ cfgMsg('没有需要保存的修改'); return; }
  var btn=this; btn.disabled=true; cfgMsg('保存中…');
  api('POST','/api/sources/'+cfgFileId+'/config',body).then(function(o){
    btn.disabled=false;
    if(!(o.s===200&&o.j.ok)){ cfgMsg('保存失败：'+((o.j&&o.j.error)||o.s),true); return; }
    cfgDirty=false; cfgPending={}; cfgMsg('已保存',false);
    // 重新拉配置刷新节点状态
    fetch('/api/sources/'+cfgFileId+'/config').then(function(r){return r.json();}).then(function(j){
      cfgData=j; renderCfg(); load();
    });
  }).catch(function(){ btn.disabled=false; cfgMsg('保存失败：平台库不可用',true); });
};
document.getElementById('cfgClose').onclick=function(){ document.getElementById('cfg').hidden=true; };
document.getElementById('cfg').addEventListener('click',function(e){ if(e.target===this) this.hidden=true; });

/* 深链 ?state= 过滤（工作台卡片跳转） */
var qs=new URLSearchParams(location.search);
if(qs.get('state')){ fstate=qs.get('state'); var sel=document.getElementById('fstate'); if(sel) sel.value=fstate; }

bindLightbox();
load();
