/* web/process.js — 资料处理独立页：左侧纵向四节点，右侧「配置细条 + 产物」
   红线：保存配置只写配置，不自动重跑；执行动作必须显式点击并二次确认。 */
var pfId=null, pfName='', pfNode='parse', pfData=null, pfCfg=null, pfRecords=[];
var pfPending={}, pfCfgOpen=false, pfPreResult=null, pfPreError='', pfRuleDetail=null, pfRows=null;
var pfFileNames={};
var pfLineageOpen=true, pfLinRidByIndex={}, pfLinFieldMap={};
var PF_NODES=[['parse','解析'],['extract','抽取'],['review','校验'],['load','入库']];
var PF_TITLE={parse:'解析参数',extract:'抽取规则',review:'校验规则',load:'入库映射'};
var PF_PRODUCT={parse:'解析报告',extract:'数据记录',review:'校验记录',load:'入库表'};
var PF_CFG_TIP={
  parse:'仅对本次资料的解析生效；保存后需显式点击「执行解析」才重放。',
  extract:'执行抽取时按此规则生成暂存记录；保存配置不会重抽已有记录。',
  review:'当前校验为逐条人工改值 / 确认 / 拒绝，暂无可调参数；自动化校验规则待实现。',
  load:'入库映射在执行入库时消费，须与抽取规则匹配；保存配置不会执行入库。'
};
var PF_RES_TIP={
  parse:'页面图与结构化结果逐项对照。',
  extract:'暂存记录内联展示；编辑与确认请打开数据预览。',
  review:'优先展示待审记录；校验与抽取共用同一份暂存记录。',
  load:'预检只读；已有回执的记录在重新入库时自动跳过。'
};
var PF_STATE={pending:'待校验',edited:'已修改',confirmed:'已确认',rejected:'已拒绝'};

function pfApi(method,path,body){
  return fetch(path,{method:method,
    headers:{'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});});
}
function pfCfgMsg(t,bad){
  var e=document.getElementById('pfCfgMsg');
  if(!e) return;
  e.textContent=t||''; e.className='msg'+(bad?' err':'');
}
function pfTip(t){ return '<span class="hint" tabindex="0" data-tip="'+
  escHtml(t||'')+'">?</span>'; }
function pfNodeState(st,key){
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
function pfNodeDesc(key,p){
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
function pfInit(){
  var qs=new URLSearchParams(location.search);
  pfId=parseInt(qs.get('file'),10);
  var n=qs.get('node');
  if(['parse','extract','review','load'].indexOf(n)>=0) pfNode=n;
  if(!pfId){
    document.getElementById('procBody').innerHTML=
      '<div class="empty">缺少资料 ID。请从<a href="/sources">资料台账</a>点击「处理」进入。</div>';
    return;
  }
  window.addEventListener('message',pfOnLinMessage);
  pfLoad();
}
function pfLoad(){
  pfPreResult=null; pfPreError=''; pfCfgOpen=false; pfRows=null;
  document.getElementById('procBody').innerHTML='<div class="empty">加载中…</div>';
  Promise.all([
    pfApi('GET','/api/sources/'+pfId+'/pipeline'),
    pfApi('GET','/api/sources/'+pfId+'/config'),
    pfApi('GET','/api/sources/'+pfId+'/staging'),
    pfApi('GET','/api/sources/state'),
    pfApi('GET','/api/sources/'+pfId+'/record-ids')
  ]).then(function(rs){
    if(!(rs[0].s===200&&rs[0].j&&rs[0].j.ok))
      throw new Error((rs[0].j&&rs[0].j.error)||('HTTP '+rs[0].s));
    if(!(rs[1].s===200&&rs[1].j&&rs[1].j.ok))
      throw new Error((rs[1].j&&rs[1].j.error)||('HTTP '+rs[1].s));
    pfData=rs[0].j.pipeline||{};
    pfName=(rs[0].j.file&&rs[0].j.file.name)||('资料 '+pfId);
    pfCfg=rs[1].j;
    var doc=rs[2].s===200?rs[2].j:{};
    pfRecords=((doc&&doc.files||[])[0]||{}).records||[];
    pfFileNames={};
    ((rs[3].j||{}).items||[]).forEach(function(f){ pfFileNames[f.id]=f.name; });
    pfLinRidByIndex={};
    ((rs[4].j||{}).items||[]).forEach(function(x){
      pfLinRidByIndex[x.index]=x.record_id;
    });
    document.getElementById('procBody').innerHTML=
      '<div class="proc-layout">'+
        '<aside class="proc-side"><div class="proc-side-t">处理流程</div>'+
          '<div class="proc-flow-v" id="procFlow"></div></aside>'+
        '<main class="proc-main">'+
          '<div class="proc-sec" id="procConfig"></div>'+
          '<div class="proc-sec" id="procResult"></div>'+
        '</main>'+
      '</div>';
    pfRender();
  }).catch(function(e){
    document.getElementById('procBody').innerHTML=
      '<div class="empty">读取失败：'+escHtml(String(e&&e.message||e))+
      '。<a href="/sources">返回资料台账</a></div>';
  });
}
function pfRender(){
  var p=pfData||{};
  document.getElementById('procTitle').textContent='资料处理 · '+pfName;
  document.getElementById('procMeta').innerHTML=stateBadge(p.state);
  document.getElementById('procFlow').innerHTML=PF_NODES.map(function(n){
    var st=pfNodeState(p.state,n[0]);
    return '<button type="button" class="pipe-node '+st+(pfNode===n[0]?' on':'')+
      '" data-pn="'+n[0]+'"><div class="pn-t"><span class="dot"></span>'+n[1]+
      '</div><div class="pn-d" title="'+escHtml(pfNodeDesc(n[0],p))+'">'+
      escHtml(pfNodeDesc(n[0],p))+'</div></button>';
  }).join('');
  document.getElementById('procFlow').onclick=function(e){
    var b=e.target.closest?e.target.closest('[data-pn]'):null;
    if(!b||b.getAttribute('data-pn')===pfNode) return;
    pfCollect();
    pfNode=b.getAttribute('data-pn');
    var u=new URL(location.href);
    u.searchParams.set('node',pfNode);
    history.replaceState(null,'',u.pathname+u.search);
    pfRender();
  };
  pfRenderConfig();
  pfRenderResult();
  pfBindAction();
}
function pfCollect(){
  if(!pfCfg) return;
  if(pfNode==='parse'){
    var pv={};
    document.querySelectorAll('#procConfig [data-cp]').forEach(function(el){
      var key=el.getAttribute('data-cp'), v=el.value;
      var s=(pfCfg.schema||[]).filter(function(p){return p.key===key;})[0]||{};
      if(s.type==='int') v=parseInt(v,10);
      else if(s.type==='float') v=parseFloat(v);
      else if(s.type==='bool') v=v==='1';
      pv[key]=v;
    });
    pfPending.params=pv;
  }else if(pfNode==='extract'){
    var rv=document.getElementById('pfRule');
    if(rv) pfPending.rule_version_id=rv.value?parseInt(rv.value,10):null;
  }else if(pfNode==='load'){
    var ds=document.getElementById('pfDs'), lt=document.getElementById('pfLt');
    if(ds&&lt) pfPending.load=(ds.value&&lt.value)
      ?{datasource_id:parseInt(ds.value,10),load_table_id:parseInt(lt.value,10)}
      :{datasource_id:null,load_table_id:null};
  }
}
function pfRenderConfig(){
  var box=document.getElementById('procConfig');
  if(!pfCfg){ box.innerHTML=''; return; }
  var spacer='<span class="hint-spacer"></span>';
  var dis='';   // 配置一律可编辑；写入限制由服务端在保存时反馈
  var fields='';
  if(pfNode==='parse'){
    var basic='', groups={}, order=[];
    var row=function(p){
      var key=p.key, label=p.label||key, val=pfCfg.params[key];
      if(val===undefined||val===null) val=p.default;
      var desc=p.desc||p.help||'';
      var h='<div class="field"><label>'+escHtml(label)+'</label><span class="finput">';
      if(p.type==='bool'){
        h+='<select data-cp="'+escHtml(key)+'"'+dis+'>'+
          '<option value="1"'+(val?' selected':'')+'>开</option>'+
          '<option value="0"'+(!val?' selected':'')+'>关</option></select>';
      }else if(p.options||p.choices){
        var opts=p.options||p.choices;
        h+='<select data-cp="'+escHtml(key)+'"'+dis+'>';
        opts.forEach(function(o){
          var v=(typeof o==='object')?o.value:o, t=(typeof o==='object')?o.label||o.value:o;
          h+='<option value="'+escHtml(v)+'"'+(String(v)===String(val)?' selected':'')+'>'+
            escHtml(t)+'</option>';
        });
        h+='</select>';
      }else{
        h+='<input type="text" data-cp="'+escHtml(key)+'" value="'+escHtml(val)+'"'+
          ' placeholder="'+escHtml(p.default!=null?String(p.default):'')+'"'+dis+'>';
      }
      if(p.unit) h+='<span class="cfg-unit">'+escHtml(p.unit)+'</span>';
      return h+(desc?pfTip(desc):'')+'</span></div>';
    };
    (pfCfg.schema||[]).forEach(function(p){
      if(p.hidden) return;   /* 服务端标记隐藏的参数不生成控件 */
      if(['model','page'].indexOf(p.key)>=0){ basic+=row(p); return; }
      if(!groups[p.group]){ groups[p.group]=[]; order.push(p.group); }
      groups[p.group].push(row(p));
    });
    var advBody=order.map(function(g){
      return '<div class="proc-pgroup"><h4>'+escHtml(g)+'</h4>'+
        groups[g].join('')+'</div>';
    }).join('');
    fields='<div class="proc-pgroup"><h4>基础配置</h4>'+basic+'</div>'+
      '<details class="proc-advanced"><summary>高级配置</summary>'+
      '<div class="proc-advanced-body">'+advBody+'</div></details>';
  }else if(pfNode==='extract'){
    fields='<div class="cfg-row"><label>抽取规则</label>'+spacer+
      '<select id="pfRule"'+dis+'><option value="">（不绑定 · 默认原始透传）</option>';
    (pfCfg.rules||[]).forEach(function(v){
      fields+='<option value="'+v.version_id+'"'+
        (pfCfg.rule_version_id===v.version_id?' selected':'')+'>'+
        escHtml(v.name+' v'+v.version+(v.current?'（当前）':''))+'</option>';
    });
    fields+='</select></div>'+
      '<div class="proc-ruledetail" id="pfRuleDetail">加载规则详情…</div>';
  }else if(pfNode==='review'){
    fields='<div class="msg">自动化校验规则待实现（当前为逐条人工改值 / 确认 / 拒绝）</div>';
  }else{
    fields='<div class="cfg-row"><label>业务库</label>'+spacer+'<select id="pfDs"'+dis+'>'+
      '<option value="">（未选择）</option>';
    (pfCfg.datasources||[]).forEach(function(d){
      fields+='<option value="'+d.id+'"'+
        (pfCfg.load&&pfCfg.load.datasource_id===d.id?' selected':'')+'>'+
        escHtml(d.name+' · '+d.host+'/'+d.db_name)+'</option>';
    });
    fields+='</select></div>'+
      '<div class="cfg-row"><label>入库映射</label>'+spacer+'<select id="pfLt"'+dis+'>'+
      '<option value="">（未选择）</option>';
    (pfCfg.load_tables||[]).forEach(function(t){
      fields+='<option value="'+t.id+'" data-ds="'+t.datasource_id+'"'+
        (pfCfg.load&&pfCfg.load.load_table_id===t.id?' selected':'')+'>'+
        escHtml(t.target_table+' · '+t.write_mode)+'</option>';
    });
    fields+='</select></div>';
  }
  box.innerHTML='<div class="proc-bar">'+
    '<div class="proc-bar-l">'+
      '<b>配置</b>'+pfTip(PF_CFG_TIP[pfNode])+
      '<span class="msg" id="pfCfgMsg"></span>'+
    '</div><div class="proc-bar-r">'+
      '<button type="button" class="proc-toggle" id="pfCfgToggle" '+
        'aria-label="展开或收起配置">'+(pfCfgOpen?'▾':'▸')+'</button>'+
      (pfNode==='review'?'':'<button type="button" class="btn mini" id="pfCfgSave">保存配置</button>')+
    '</div></div>'+
    '<div class="proc-cfgbody" id="pfCfgBody"'+(pfCfgOpen?'':' hidden')+'>'+fields+'</div>';
  document.getElementById('pfCfgToggle').onclick=function(){
    pfCfgOpen=!pfCfgOpen;
    document.getElementById('pfCfgBody').hidden=!pfCfgOpen;
    this.textContent=pfCfgOpen?'▾':'▸';
  };
  var ds=document.getElementById('pfDs'), lt=document.getElementById('pfLt');
  if(ds&&lt){
    ds.onchange=function(keep){
      var did=this.value;
      Array.prototype.forEach.call(lt.options,function(o){
        if(!o.value) return;
        o.hidden=!!did&&o.getAttribute('data-ds')!==did;
      });
      /* 初始化时保留已绑定的入库映射；用户主动换业务库才清空 */
      if(keep&&Array.prototype.some.call(lt.options,function(o){
        return o.value===String(keep)&&!o.hidden;})) lt.value=String(keep);
      else lt.value='';
    };
    if(pfCfg.load&&pfCfg.load.datasource_id)
      ds.onchange(pfCfg.load.load_table_id);
  }
  var dsFilter=ds&&ds.onchange;
  var mark=function(){ pfCfgMsg('有未保存的修改'); };
  document.querySelectorAll('#procConfig [data-cp]').forEach(function(el){ el.onchange=mark; });
  ['pfRule','pfDs','pfLt'].forEach(function(id){
    var el=document.getElementById(id);
    if(!el) return;
    el.onchange=function(){
      mark();
      if(id==='pfRule') pfLoadRuleDetail();
      else if(id==='pfDs'&&dsFilter) dsFilter();
    };
  });
  var save=document.getElementById('pfCfgSave');
  if(save) save.onclick=function(){
    pfCollect();
    if(!Object.keys(pfPending).length){ pfCfgMsg('没有需要保存的修改'); return; }
    var btn=this; btn.disabled=true; pfCfgMsg('保存中…');
    pfApi('POST','/api/sources/'+pfId+'/config',pfPending).then(function(o){
      btn.disabled=false;
      if(!(o.s===200&&o.j&&o.j.ok)){
        pfCfgMsg('保存失败：'+((o.j&&o.j.error)||o.s),true); return;
      }
      pfPending={}; pfLoad();
    }).catch(function(){ btn.disabled=false; pfCfgMsg('保存失败：平台库不可用',true); });
  };
  if(pfNode==='extract') pfLoadRuleDetail();
}
function pfLoadRuleDetail(){
  var sel=document.getElementById('pfRule');
  if(!sel) return;
  var vid=sel.value?parseInt(sel.value,10):null;
  var meta=(pfCfg.rules||[]).filter(function(r){return r.version_id===vid;})[0]||null;
  var box=document.getElementById('pfRuleDetail');
  if(!box) return;
  if(!meta){
    pfRuleDetail=null;
    box.innerHTML='<span class="msg">未绑定抽取规则（执行时使用默认原始透传）</span>';
    return;
  }
  pfApi('GET','/api/extract-rules/'+meta.rule_id+'/versions/'+meta.version_id)
    .then(function(o){
      if(!(o.s===200&&o.j&&o.j.id)){
        box.innerHTML='<span class="msg err">规则详情读取失败</span>';
        return;
      }
      pfRuleDetail=o.j;
      pfRenderRuleDetail(meta);
    }).catch(function(){
      box.innerHTML='<span class="msg err">规则详情读取失败</span>';
    });
}
function pfRenderRuleDetail(meta){
  var box=document.getElementById('pfRuleDetail');
  if(!box) return;
  var d=pfRuleDetail||{}, schema=d.schema_json||{}, mapping=d.mapping_json||{};
  var fields=(schema.fields||[]).map(function(f){
    return (f.name||'')+(f.type?'（'+f.type+'）':'');
  }).join('、')||'—';
  var fxLabel={trim:'去空格',replace:'替换',number:'转数字',lower:'小写',upper:'大写'};
  var maps=(mapping.fields||[]).map(function(f){
    var pipe=f.pipeline||[];
    var cell=pipe.filter(function(x){return x.op==='cell';})[0]||{};
    var src=(f.column&&f.column.name)||(cell.column&&cell.column.name)||
      (cell.column&&cell.column.index!=null?('列'+(cell.column.index+1)):'');
    var fx=pipe.filter(function(x){return x.op!=='cell';}).map(function(x){
      return fxLabel[x.op]||x.op;
    }).join('、');
    return (src?'原始列「'+src+'」 → ':'')+'目标列「'+(f.target||'')+'」'+
      (fx?'（'+fx+'）':'');
  }).join('；')||'—';
  var tb=(mapping.tables||[])[0]||mapping.table||{};
  var tbl=(tb.index!=null?('表 '+(Number(tb.index)+1)):'')+
    (tb.header_contains?('表头含 '+tb.header_contains):'')||'—';
  var trans=((d.transform_json||{}).fields||[]).length;
  var refs=mapping.refs||{};
  var refFile=refs.file_id?('#'+refs.file_id+
    (pfFileNames[refs.file_id]?' · '+pfFileNames[refs.file_id]:'')):'—';
  var ds=(pfCfg.datasources||[]).filter(function(x){
    return x.id===refs.datasource_id;
  })[0];
  var refBiz=(refs.datasource_id||refs.table)
    ?((ds?ds.name:('业务库 '+refs.datasource_id))+
      (refs.table?' / '+refs.table:'')):'—';
  var row=function(label,value){
    return '<div class="cfg-row"><label>'+escHtml(label)+'</label>'+
      '<span class="hint-spacer"></span><span class="cfg-static">'+
      escHtml(value)+'</span></div>';
  };
  box.innerHTML='<div class="msg">只读展示 · '+
    '<a class="linkbtn" target="_blank" rel="noopener" href="/extract?rule='+
    meta.rule_id+'">打开详情编辑 →</a></div>'+
    row('规则名称',d.name||meta.name)+
    row('版本','v'+(d.version||meta.version))+
    row('规格',d.spec_version?('v'+d.spec_version):'v1（默认）')+
    row('参考文件',refFile)+
    row('参考业务表',refBiz)+
    row('表定位',tbl)+
    row('输出字段',fields)+
    row('字段映射',maps)+
    row('转换字段',trans?String(trans)+' 项':'无');
}
function pfPreviewUrl(){
  return pfNode==='review'
    ? '/preview?file='+pfId+'&view=review'
    : '/preview?file='+pfId;
}
/* ---- 产物区内联血缘追溯 ---- */
function pfLinBaseSrc(){ return '/preview?embed=1&file='+pfId; }
function pfLinClear(){
  document.querySelectorAll('#procResult tr.pf-sel').forEach(function(tr){
    tr.classList.remove('pf-sel');});
  document.querySelectorAll('#procResult td.cell.pf-pin').forEach(function(td){
    td.classList.remove('pf-pin');});
}
function pfLinHighlight(key,index,rid,col){
  pfLinClear();
  var tr=null, td=null, i;
  if(index!=null){
    for(i=0;i<document.querySelectorAll('#procResult tr[data-index]').length;i++){
      var x=document.querySelectorAll('#procResult tr[data-index]')[i];
      if(String(x.getAttribute('data-index'))===String(index)){ tr=x; break; }
    }
    if(tr) for(i=0;i<tr.querySelectorAll('td.cell[data-key]').length;i++){
      var y=tr.querySelectorAll('td.cell[data-key]')[i];
      if(y.getAttribute('data-key')===key){ td=y; break; }
    }
  }
  if(!tr&&rid!=null){
    for(i=0;i<document.querySelectorAll('#procResult tr[data-rid]').length;i++){
      var x2=document.querySelectorAll('#procResult tr[data-rid]')[i];
      if(String(x2.getAttribute('data-rid'))===String(rid)){ tr=x2; break; }
    }
    if(tr) Array.prototype.forEach.call(tr.querySelectorAll('td.cell[data-col]'),function(y){
      var c=y.getAttribute('data-col');
      if((col&&c===col)||(!col&&(pfLinFieldMap[c]||c)===key)) td=y;
    });
  }
  if(tr) tr.classList.add('pf-sel');
  if(td) td.classList.add('pf-pin');
}
function pfLinSelect(key,index,rid,col){
  var wasOpen=pfLineageOpen;
  if(!wasOpen){ pfLineageOpen=true; pfRenderResult(); }
  var frame=document.getElementById('pfLinFrame');
  if(!frame) return;
  var base=pfLinBaseSrc();
  var first=base+'&index='+encodeURIComponent(index)+
    '&key='+encodeURIComponent(key);
  if(!wasOpen){
    /* 首次展开：iframe 刚创建，直接带定位参数加载，不能发空窗口消息 */
    frame.src=first;
  }else if(frame.getAttribute('data-src')===base){
    if(frame.contentWindow) frame.contentWindow.postMessage(
      {c1TraceKey:{key:key,index:index}},'*');
  }else{
    frame.setAttribute('data-src',base);
    frame.src=first;
  }
  pfLinHighlight(key,index,rid,col);
}
function pfBindLinCells(){
  document.querySelectorAll('#procResult tr[data-index] td.cell[data-key]').forEach(function(td){
    td.onclick=function(){
      var tr=td.closest('tr[data-index]');
      pfLinSelect(td.getAttribute('data-key'),tr.getAttribute('data-index'),null,null);
    };
  });
  document.querySelectorAll('#procResult tr[data-rid] td.cell[data-col]').forEach(function(td){
    td.onclick=function(){
      var tr=td.closest('tr[data-rid]'), rid=tr.getAttribute('data-rid');
      var col=td.getAttribute('data-col');
      pfApi('GET','/api/staging/locate/'+encodeURIComponent(rid)+
        '?key='+encodeURIComponent(col)).then(function(o){
        if(!(o.s===200&&o.j&&o.j.ok)) return;
        pfLinFieldMap=o.j.field_map||{};
        pfLinSelect(o.j.field||col,o.j.record_index,rid,col);
      });
    };
  });
}
function pfOnLinMessage(e){
  if(!e.data) return;
  if(typeof e.data.c1LineageCollapsed==='boolean'){
    var panel=document.getElementById('pfLineage');
    if(panel) panel.classList.toggle('collapsed',e.data.c1LineageCollapsed);
    return;
  }
  if(!e.data.c1PinField||!pfLineageOpen) return;
  var key=e.data.c1PinField.key, idx=e.data.c1PinField.record_index;
  pfLinHighlight(key,idx,pfLinRidByIndex[idx],null);
}
function pfRecordsHtml(){
  var recs=(pfRecords||[]).slice();
  if(pfNode==='review'){
    var pend=recs.filter(function(r){
      return ((r.review||{}).state||'pending')!=='confirmed';
    });
    if(pend.length) recs=pend;
  }
  if(!recs.length) return '<div class="empty">暂无记录</div>';
  recs=recs.slice(0,20);
  var keys=[];
  recs.forEach(function(r){
    Object.keys(r.values||{}).forEach(function(k){
      if(keys.indexOf(k)<0&&keys.length<8) keys.push(k);
    });
  });
  var withState=pfNode==='review';
  var h='<table class="list proc-records"><thead><tr><th class="seq">#</th>'+
    (withState?'<th>状态</th>':'')+
    keys.map(function(k){ return '<th>'+escHtml(k)+'</th>'; }).join('')+'</tr></thead><tbody>';
  recs.forEach(function(r){
    var st=(r.review||{}).state||'pending';
    h+='<tr data-index="'+escHtml(r.index)+'">'+
      '<td class="seq">'+((r.index||0)+1)+'</td>'+
      (withState?'<td>'+escHtml(PF_STATE[st]||st)+'</td>':'')+
      keys.map(function(k){
        var v=(r.values||{})[k];
        return '<td class="cell" data-key="'+escHtml(k)+'">'+
          escHtml(v==null?'':String(v))+'</td>';
      }).join('')+'</tr>';
  });
  return h+'</tbody></table>';
}
function pfActionHtml(){
  var p=pfData||{}, st=String(p.state||'');
  var busy=st==='parsing'||st==='loading', label='', dis=false, tip='';
  if(pfNode==='parse'){
    label='执行解析'; dis=busy;
    tip=busy?'正在处理中，请稍候。'
      :(st==='loaded'
        ?'仅重新运行解析并生成 test/ 下的新报告；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
        :'按当前解析参数执行解析；已有暂存、产物、回执与校验结论会被覆盖。');
  }else if(pfNode==='extract'){
    label='执行抽取'; dis=busy;
    tip=busy?'正在处理中，请稍候。'
      :'按当前抽取规则执行抽取；已有记录与校验结论会被覆盖。';
  }else if(pfNode==='review'){
    var c=p.review_counts||{}, pend=(c.pending||0)+(c.edited||0);
    label='执行校验'; dis=busy;
    tip=busy?'正在处理中，请稍候。'
      :('将全部 '+pend+' 条待审记录设为通过。'+
        (c.rejected?'另有 '+c.rejected+' 条已拒绝记录需人工处理。':''));
  }else{
    var bound=!!(p.load&&p.load.load_table_id);
    label='执行入库'; dis=busy||!bound;
    tip=busy?'正在处理中，请稍候。':(bound
      ?('按已配置的入库映射写入 '+p.load.target_table+'。')
      :'请先在配置里绑定入库映射。');
  }
  return '<button type="button" class="btn mini" id="pfAct"'+(dis?' disabled':'')+'>'+
    label+'</button>';
}
function pfRenderResult(){
  var p=pfData||{}, box=document.getElementById('procResult');
  var st=String(p.state||''), openLink='', tools='', body='';
  if(pfNode==='parse'){
    var testReport=(p.parse_artifacts||[]).indexOf('test/对照报告.html')>=0;
    var reportName=st==='loaded'&&testReport?'test/对照报告.html':'对照报告.html';
    var reportUrl='/files/'+pfId+'/'+reportName.split('/').map(encodeURIComponent).join('/');
    var has=(p.parse_artifacts||[]).indexOf(reportName)>=0;
    if(has) openLink='<a class="proc-open" target="_blank" rel="noopener" href="'+
      reportUrl+'">'+(testReport&&st==='loaded'?'打开测试报告':'打开对照报告')+' →</a>';
    body=has
      ? '<iframe id="pfReport" class="proc-report" src="'+reportUrl+'" loading="lazy" title="对照报告"></iframe>'
      : '<div class="empty">暂无对照报告</div>';
  }else if(pfNode==='extract'||pfNode==='review'){
    openLink='<a class="proc-open" target="_blank" rel="noopener" href="'+
      pfPreviewUrl()+'">'+(pfNode==='review'?'打开校验视图':'打开数据预览')+' →</a>';
    body=pfRecordsHtml();
  }else{
    var l=p.load||{}, acts=p.load_actions||{};
    if(l.target_table){
      openLink='<a class="proc-open" target="_blank" rel="noopener" href="/dashboard?ds='+
        encodeURIComponent(l.datasource_id||'')+'&table='+encodeURIComponent(l.target_table)+
        '&file='+pfId+'">打开数据看板 →</a>';
      tools='<button type="button" class="btn mini" id="pfPreflight">预检</button>'+
        '<button type="button" class="btn mini" id="pfReceipt">回执</button>';
      body='<div class="proc-kv"><span><b>目标表</b>'+escHtml(l.target_table)+'</span>'+
        '<span><b>写入</b>'+escHtml(l.write_mode||'—')+'</span>'+
        '<span><b>新增</b>'+(acts.insert||0)+'</span>'+
        '<span><b>覆盖</b>'+(acts.update||0)+'</span></div>'+
        '<div class="msg" id="pfPreMsg">'+
        escHtml(pfPreResult?('预检 '+pfPreResult.total+' 条 · 新增 '+pfPreResult.insert+
          ' · 覆盖 '+pfPreResult.update+' · 跳过 '+pfPreResult.skip+
          ' · 隔离 '+pfPreResult.quarantine):(pfPreError||''))+'</div>'+
        '<div id="pfRowsBox">加载中…</div>';
    }else{
      body='<div class="empty">尚未绑定入库映射</div>';
    }
  }
  var linPanel=pfNode==='parse'?'':
    '<div class="proc-lineage" id="pfLineage"'+(pfLineageOpen?'':' hidden')+'>'+
      '<iframe id="pfLinFrame" title="血缘追溯" loading="lazy"></iframe></div>';
  box.innerHTML='<div class="proc-bar"><div class="proc-bar-l">'+
    '<b>产物</b>'+pfTip(PF_RES_TIP[pfNode])+openLink+'</div><div class="proc-bar-r">'+
    tools+pfActionHtml()+'</div></div><div class="proc-result-split">'+
    '<div class="proc-result-body">'+
    '<div class="msg" id="pfActMsg"></div>'+body+'</div>'+linPanel+'</div>';
  if(pfLineageOpen){
    var lf=document.getElementById('pfLinFrame');
    if(lf&&!lf.getAttribute('data-src')){
      lf.setAttribute('data-src',pfLinBaseSrc());
      lf.src=pfLinBaseSrc();
    }
  }
  if(pfNode==='parse'){
    var fr=document.getElementById('pfReport');
    if(fr) fr.onload=function(){
      try{
        var d=fr.contentDocument;
        if(!d||!d.head) return;
        var s=d.createElement('style');
        s.textContent='.imgwrap{max-width:100% !important}';
        d.head.appendChild(s);
      }catch(e){}
    };
  }
  if(pfNode==='load'){
    var pb=document.getElementById('pfPreflight');
    if(pb) pb.onclick=pfRunPreflight;
    var rb=document.getElementById('pfReceipt');
    if(rb) rb.onclick=function(){ openReceiptDrawer(pfId); };
    if((pfData.load||{}).target_table) pfLoadRows();
  }
  pfBindLinCells();
}
function pfLoadRows(){
  var box=document.getElementById('pfRowsBox');
  if(!box) return;
  var l=pfData.load||{};
  if(pfRows){
    box.innerHTML=pfRowsHtml(); pfBindLinCells(); return;
  }
  var url='/api/load/datasources/'+l.datasource_id+'/rows?table='+
    encodeURIComponent(l.target_table)+'&page=1&per_page=20&file_id='+pfId;
  pfApi('GET',url).then(function(o){
    if(!(o.s===200&&o.j&&o.j.ok)){
      box.innerHTML='<div class="msg err">'+
        escHtml((o.j&&o.j.error)||('读取失败 '+o.s))+'</div>';
      return;
    }
    pfRows=o.j; box.innerHTML=pfRowsHtml(); pfBindLinCells();
  }).catch(function(e){
    box.innerHTML='<div class="msg err">读取失败：'+escHtml(e&&e.message||e)+'</div>';
  });
}
function pfRowsHtml(){
  var d=pfRows||{}, hide={file_id:1,record_id:1};
  var cols=(d.columns||[]).filter(function(c){return !hide[c];}).slice(0,8);
  var items=d.items||[];
  var h='<div class="msg">目标表共 '+(d.total||0)+' 行 · 展示前 '+items.length+' 行</div>';
  if(!items.length) return h+'<div class="empty">暂无数据</div>';
  h+='<table class="list proc-records"><thead><tr><th class="seq">序号</th>'+
    cols.map(function(c){return '<th>'+escHtml(c)+'</th>';}).join('')+'</tr></thead><tbody>';
  items.forEach(function(r,i){
    h+='<tr data-rid="'+escHtml(r.record_id)+'"><td class="seq">'+(i+1)+'</td>'+
      cols.map(function(c){
        var v=r[c];
        return '<td class="cell" data-col="'+escHtml(c)+'">'+
          escHtml(v==null?'':String(v))+'</td>';
      }).join('')+'</tr>';
  });
  return h+'</tbody></table>';
}
function pfRunPreflight(){
  var m=document.getElementById('pfPreMsg');
  var sel=document.getElementById('pfLt');
  var bound=pfData.load&&pfData.load.load_table_id;
  var tid=bound||(sel&&sel.value?parseInt(sel.value,10)
    :((pfCfg&&pfCfg.load&&pfCfg.load.load_table_id)||null));
  if(!tid){ if(m) m.textContent='请先选择入库映射'; return; }
  var btn=document.getElementById('pfPreflight');
  if(btn) btn.disabled=true;
  if(m) m.textContent='预检中（只读'+(bound?' · 按已绑定目标':'')+'）…';
  pfApi('POST','/api/sources/'+pfId+'/load-preview',{load_table_id:tid}).then(function(o){
    if(btn) btn.disabled=false;
    if(!(o.s===200&&o.j&&o.j.ok)){
      pfPreResult=null;
      pfPreError='预检失败：'+((o.j&&o.j.error)||o.s);
      if(m) m.textContent=pfPreError;
      return;
    }
    pfPreError=''; pfPreResult=o.j;
    if(m) m.textContent='预检 '+o.j.total+' 条 · 新增 '+o.j.insert+
      ' · 覆盖 '+o.j.update+' · 跳过 '+o.j.skip+' · 隔离 '+o.j.quarantine;
  }).catch(function(e){
    if(btn) btn.disabled=false;
    pfPreResult=null; pfPreError='预检失败：'+(e&&e.message||'平台库不可用');
    if(m) m.textContent=pfPreError;
  });
}
function pfBindAction(){
  var b=document.getElementById('pfAct');
  if(!b) return;
  var st=String((pfData||{}).state||'');
  b.onclick=function(){
    var btn=this, msg='';
    if(pfNode==='parse'){
      msg=st==='loaded'
        ?'确认重新执行解析？\n仅生成 test/ 下的新产物；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
        :'确认按当前解析参数执行解析？\n将清空暂存、产物、回执与校验结论。';
    }else if(pfNode==='extract'){
      msg=(st==='to_review'||st==='to_load')
        ?'已有暂存记录，重新抽取将覆盖校验结论。确认继续？'
        :'确认按当前抽取规则执行抽取？';
    }else if(pfNode==='review'){
      msg='确认将全部待审记录设为通过？';
    }else{
      msg='确认按已配置的入库映射执行入库？';
    }
    if(!confirm(msg)) return;
    btn.disabled=true;
    var req;
    if(pfNode==='parse') req=pfApi('POST','/api/sources/'+pfId+'/reparse',
      st==='loaded'?{test_mode:true}:{});
    else if(pfNode==='extract'){
      var body=(st==='to_review'||st==='to_load')?{force:true}:{};
      var rv=document.getElementById('pfRule');
      /* 配置由 UI 显式传；空体在服务端恒为原始透传 */
      if(rv&&rv.value) body.rule_version_id=parseInt(rv.value,10);
      req=pfApi('POST','/api/sources/'+pfId+'/extract',body);
    }
    else if(pfNode==='review') req=pfApi('POST','/api/sources/'+pfId+'/approve-all',{});
    else req=pfApi('POST','/api/sources/'+pfId+'/load',{});
    var m=document.getElementById('pfActMsg');
    if(m) m.textContent='执行中…';
    req.then(function(o){
      if(!(o.s===200&&o.j&&o.j.ok)){
        btn.disabled=false;
        if(m) m.textContent='失败：'+((o.j&&o.j.error)||o.s);
        return;
      }
      if(pfNode==='parse'){
        if(m){
          m.textContent=st==='loaded'
            ?'已启动解析；正式数据保持不变。':'已启动解析。';
          var progressLink=document.createElement('a');
          progressLink.href='/parse?from_source='+pfId;
          progressLink.textContent='查看解析进度 →';
          progressLink.className='linkbtn';
          m.appendChild(document.createTextNode(' '));
          m.appendChild(progressLink);
        }
        return;
      }
      pfLoad();
    }).catch(function(e){
      btn.disabled=false;
      if(m) m.textContent='失败：'+(e&&e.message||'平台库不可用');
    });
  };
}
pfInit();
