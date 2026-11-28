/* web/process.js — 资料处理独立页：左侧纵向四节点，右侧「配置细条 + 产物」
   红线：保存配置只写配置，不自动重跑；执行动作必须显式点击并二次确认。 */
var pfId=null, pfName='', pfNode='parse', pfData=null, pfCfg=null, pfRecords=[];
var pfResultId=null, pfResults=[], pfRules=null, pfRulesLoading=false, pfRulesError='';
var pfPending={}, pfCfgOpen=false, pfPreResult=null, pfPreError='', pfRuleDetail=null, pfRows=null;
var pfFileNames={};
var pfLineageOpen=true, pfLinRidByIndex={}, pfLinFieldMap={};
var pfWizardLoading=null;
var PF_NODES=[['parse','解析'],['extract','抽取'],['review','校验'],['load','入库']];
var PF_TITLE={parse:'解析参数',extract:'抽取规则',review:'校验规则',load:'入库映射'};
var PF_PRODUCT={parse:'解析报告',extract:'数据记录',review:'校验记录',load:'入库表'};
var PF_CFG_TIP={
  parse:'仅对本次资料的解析生效；保存后需显式点击「执行解析」才重放。',
  extract:'选择单行规则后显式执行抽取；同资料同规则覆盖自己的结果，其他结果不受影响。',
  review:'当前校验为逐条人工改值 / 确认 / 拒绝，暂无可调参数；自动化校验规则待实现。',
  load:'入库映射按抽取结果独立绑定；配置、预检与执行均不会影响其他结果。'
};
var PF_RES_TIP={
  parse:'页面图与结构化结果逐项对照。',
  extract:'展示所选抽取结果的暂存记录；编辑与确认请打开数据预览。',
  review:'优先展示所选结果的待审记录；校验与抽取共用同一份暂存记录。',
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
  if(key==='extract') return pfResults.length
    ? (pfResults.length+' 个抽取结果') : '尚无抽取结果';
  if(key==='review'){
    var r=pfCurrentResult(), c=r&&r.review_counts||{};
    var n=Object.keys(c).reduce(function(a,k){return a+(Number(c[k])||0);},0);
    return n?(n+' 条 · 确认 '+(c.confirmed||0)):'暂无记录';
  }
  var b=pfCurrentBinding();
  return b&&b.target_table?b.target_table:'未绑定入库目标';
}
function pfResultNum(r){ return r&&(r.extract_result_id||r.id); }
function pfCurrentResult(){
  if(pfResultId==null) return null;
  return pfResults.filter(function(r){return String(pfResultNum(r))===String(pfResultId);})[0]||null;
}
function pfCurrentBinding(){
  var r=pfCurrentResult();
  return r&&(r.load_binding||r.binding)||null;
}
function pfResultLabel(r){
  return (r.rule_name||'规则 #'+r.rule_id)+' · 结果 #'+pfResultNum(r)+
    ' · '+(r.record_count||0)+' 条';
}
function pfResultPicker(){
  return '<div class="cfg-row"><label>抽取结果</label><span class="hint-spacer"></span>'+
    '<select id="pfResult"'+(pfResults.length?'':' disabled')+'>'+
    (pfResults.length?'':'<option value="">（尚无抽取结果）</option>')+
    pfResults.map(function(r){return '<option value="'+pfResultNum(r)+'"'+
      (String(pfResultNum(r))===String(pfResultId)?' selected':'')+'>'+
      escHtml(pfResultLabel(r))+'</option>';}).join('')+'</select></div>';
}
function pfInit(){
  var qs=new URLSearchParams(location.search);
  pfId=parseInt(qs.get('file'),10);
  var rid=parseInt(qs.get('result'),10);
  if(rid>0) pfResultId=rid;
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
  pfPreResult=null; pfPreError=''; pfCfgOpen=false; pfRows=null; pfRecords=[];
  pfLinRidByIndex={}; pfLinFieldMap={};
  document.getElementById('procBody').innerHTML='<div class="empty">加载中…</div>';
  Promise.all([
    pfApi('GET','/api/sources/'+pfId+'/pipeline'),
    pfApi('GET','/api/sources/'+pfId+'/config'),
    pfApi('GET','/api/sources/'+pfId+'/extract-results'),
    pfApi('GET','/api/sources/state')
  ]).then(function(rs){
    if(!(rs[0].s===200&&rs[0].j&&rs[0].j.ok))
      throw new Error((rs[0].j&&rs[0].j.error)||('HTTP '+rs[0].s));
    if(!(rs[1].s===200&&rs[1].j&&rs[1].j.ok))
      throw new Error((rs[1].j&&rs[1].j.error)||('HTTP '+rs[1].s));
    if(!(rs[2].s===200&&rs[2].j&&rs[2].j.ok))
      throw new Error((rs[2].j&&rs[2].j.error)||('HTTP '+rs[2].s));
    pfData=rs[0].j.pipeline||{};
    pfName=(rs[0].j.file&&rs[0].j.file.name)||('资料 '+pfId);
    pfCfg=rs[1].j;
    pfResults=rs[2].j.items||[];
    var summary={};
    (pfData.results||[]).forEach(function(r){ summary[pfResultNum(r)]=r; });
    pfResults.forEach(function(r){
      var s=summary[pfResultNum(r)];
      if(s&&s.review_counts) r.review_counts=s.review_counts;
    });
    if(pfResultId!=null&&!pfResults.some(function(r){
      return String(pfResultNum(r))===String(pfResultId);})) pfResultId=null;
    if(pfResultId==null&&pfResults.length) pfResultId=pfResultNum(pfResults[0]);
    var resultUrl=new URL(location.href);
    if(pfResultId!=null) resultUrl.searchParams.set('result',String(pfResultId));
    else resultUrl.searchParams.delete('result');
    history.replaceState(null,'',resultUrl.pathname+resultUrl.search);
    pfFileNames={};
    ((rs[3].j||{}).items||[]).forEach(function(f){ pfFileNames[f.id]=f.name; });
    var extra=[];
    if(pfResultId!=null){
      var base='/api/extract-results/'+encodeURIComponent(pfResultId);
      extra=[pfApi('GET',base+'/staging'),pfApi('GET',base+'/record-ids')];
    }
    return Promise.all(extra).then(function(docs){
      var doc=docs[0]&&docs[0].s===200?docs[0].j:{};
      pfRecords=(doc.records||((doc.files||[])[0]||{}).records||[]);
      ((docs[1]&&docs[1].j||{}).items||[]).forEach(function(x){
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
    });
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
    if(pfResultId!=null) u.searchParams.set('result',String(pfResultId));
    else u.searchParams.delete('result');
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
    var current=pfCurrentResult(), bound=current&&String(current.rule_id)||'';
    fields=pfResultPicker()+'<div class="cfg-row"><label>抽取规则</label>'+spacer+
      '<select id="pfRule"'+dis+'><option value="">（请选择规则）</option>';
    (pfRules||[]).forEach(function(v){
      fields+='<option value="'+v.id+'"'+
        (bound===String(v.id)?' selected':'')+'>'+escHtml(v.name||('规则 #'+v.id))+'</option>';
    });
    fields+='</select></div>'+
      '<div class="proc-ruledetail" id="pfRuleDetail">'+
      (pfRules?'选择规则查看定义':(pfRulesError||'加载规则详情…'))+'</div>';
  }else if(pfNode==='review'){
    fields=pfResultPicker()+
      '<div class="msg">逐条人工改值 / 确认 / 拒绝；批量确认仅作用于所选抽取结果。</div>';
  }else{
    var binding=pfCurrentBinding(), result=pfCurrentResult();
    fields=pfResultPicker();
    if(!result){
      fields+='<div class="msg">请先完成抽取，再为该结果配置入库映射。</div>';
    }else if(!binding){
      fields+='<div class="msg">所选结果尚未绑定入库目标。</div>'+
        '<button type="button" class="btn mini" id="pfLoadWizard">配置入库映射</button>';
    }else{
      var map=binding.field_map_json||binding.field_map||{};
      var pairs=Object.keys(map).map(function(k){return k+' → '+map[k];}).join('；')||'—';
      fields+='<div class="cfg-row"><label>业务库</label>'+spacer+
        '<span class="cfg-static">'+escHtml(binding.datasource_name||binding.db_name||('业务库 #'+binding.datasource_id))+'</span></div>'+
        '<div class="cfg-row"><label>目标表</label>'+spacer+
        '<span class="cfg-static">'+escHtml(binding.target_table)+'</span></div>'+
        '<div class="cfg-row"><label>写入方式</label>'+spacer+
        '<span class="cfg-static">'+escHtml(modeLabel(binding.write_mode))+'</span></div>'+
        '<div class="cfg-row"><label>字段映射</label>'+spacer+
        '<span class="cfg-static">'+escHtml(pairs)+'</span></div>'+
        '<button type="button" class="btn mini" id="pfLoadWizard"'+
        (['confirmed','running','ready'].indexOf(binding.status)>=0?' disabled':'')+'>'+
        (binding.status==='failed'?'重新规划入库':'配置入库映射')+'</button>';
    }
  }
  box.innerHTML='<div class="proc-bar">'+
    '<div class="proc-bar-l">'+
      '<b>配置</b>'+pfTip(PF_CFG_TIP[pfNode])+
      '<span class="msg" id="pfCfgMsg"></span>'+
    '</div><div class="proc-bar-r">'+
      '<button type="button" class="proc-toggle" id="pfCfgToggle" '+
        'aria-label="展开或收起配置">'+(pfCfgOpen?'▾':'▸')+'</button>'+
      (pfNode==='parse'?'<button type="button" class="btn mini" id="pfCfgSave">保存配置</button>':'')+
    '</div></div>'+
    '<div class="proc-cfgbody" id="pfCfgBody"'+(pfCfgOpen?'':' hidden')+'>'+fields+'</div>';
  document.getElementById('pfCfgToggle').onclick=function(){
    pfCfgOpen=!pfCfgOpen;
    document.getElementById('pfCfgBody').hidden=!pfCfgOpen;
    this.textContent=pfCfgOpen?'▾':'▸';
  };
  var resultSel=document.getElementById('pfResult');
  if(resultSel) resultSel.onchange=function(){
    pfResultId=this.value?parseInt(this.value,10):null;
    var u=new URL(location.href);
    if(pfResultId!=null) u.searchParams.set('result',String(pfResultId));
    else u.searchParams.delete('result');
    history.replaceState(null,'',u.pathname+u.search);
    pfLoad();
  };
  var mark=function(){ pfCfgMsg('有未保存的修改'); };
  document.querySelectorAll('#procConfig [data-cp]').forEach(function(el){ el.onchange=mark; });
  var ruleSel=document.getElementById('pfRule');
  if(ruleSel) ruleSel.onchange=function(){
    pfLoadRuleDetail();
    pfCfgMsg('规则将在点击「执行抽取」时使用');
  };
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
  var wizard=document.getElementById('pfLoadWizard');
  if(wizard) wizard.onclick=pfOpenLoadWizard;
  if(pfNode==='extract'){
    pfLoadRuleDetail();
    pfEnsureRules().then(pfFillRules);
  }
}
function pfEnsureRules(){
  if(pfRules) return Promise.resolve(pfRules);
  if(pfRulesLoading) return pfRulesLoading;
  pfRulesLoading=pfApi('GET','/api/extract-rules').then(function(o){
    if(!(o.s===200&&o.j&&Array.isArray(o.j.items))){
      throw new Error((o.j&&o.j.error)||('HTTP '+o.s));
    }
    pfRules=o.j.items; pfRulesError=''; return pfRules;
  }).catch(function(e){
    pfRules=[]; pfRulesError='规则读取失败：'+(e.message||e);
    return pfRules;
  }).then(function(rules){
    pfRulesLoading=null; return rules;
  });
  return pfRulesLoading;
}
function pfFillRules(){
  var sel=document.getElementById('pfRule');
  if(!sel||pfNode!=='extract') return;
  var previous=sel.value, current=pfCurrentResult();
  var bound=current&&String(current.rule_id)||'';
  sel.innerHTML='<option value="">（请选择规则）</option>'+pfRules.map(function(r){
    return '<option value="'+r.id+'">'+escHtml(r.name||('规则 #'+r.id))+'</option>';
  }).join('');
  var value=previous&&pfRules.some(function(r){return String(r.id)===previous;})?previous:bound;
  if(value) sel.value=value;
  pfLoadRuleDetail();
}
function pfLoadRuleDetail(){
  var sel=document.getElementById('pfRule');
  if(!sel) return;
  var ruleId=sel.value?parseInt(sel.value,10):null;
  var meta=(pfRules||[]).filter(function(r){return r.id===ruleId;})[0]||null;
  var box=document.getElementById('pfRuleDetail');
  if(!box) return;
  if(!meta){
    pfRuleDetail=null;
    box.innerHTML='<span class="msg'+(pfRulesError?' err':'')+'">'+
      escHtml(pfRulesError||'请选择抽取规则')+'</span>';
    return;
  }
  pfRuleDetail=meta;
  pfRenderRuleDetail(meta);
}
function pfRenderRuleDetail(meta){
  var box=document.getElementById('pfRuleDetail');
  if(!box) return;
  var d=pfRuleDetail||meta, schema=d.output_schema_json||{}, mapping=d.extraction_spec_json||{};
  var fields=(schema.fields||[]).map(function(f){
    return (f.name||'')+(f.type?'（'+f.type+'）':'');
  }).join('、')||(mapping.fields||[]).map(function(f){return f.target||'';}).join('、')||'—';
  var fxLabel={trim:'去空格',replace:'替换',number:'转数字',lower:'小写',upper:'大写'};
  var maps=(mapping.fields||[]).map(function(f){
    var pipe=f.pipeline||[];
    var cell=pipe.filter(function(x){return x.op==='cell';})[0]||{};
    var src=(f.column&&f.column.name)||(cell.column&&cell.column.name)||
      (cell.column&&cell.column.index!=null?('列'+(cell.column.index+1)):'');
    var fx=pipe.filter(function(x){return x.op!=='cell';}).map(function(x){
      return fxLabel[x.op]||x.op;
    }).join('、');
    return (src?'原始列「'+src+'」 → ':'')+'逻辑字段「'+(f.target||'')+'」'+
      (fx?'（'+fx+'）':'');
  }).join('；')||'—';
  var tb=(mapping.tables||[])[0]||mapping.table||{};
  var tbl=(tb.index!=null?('表 '+(Number(tb.index)+1)):'')+
    (tb.header_contains?('表头含 '+tb.header_contains):'')||'—';
  var refs=d.reference_doc_ids_json||mapping.refs||{};
  var refIds=Array.isArray(refs)?refs:(refs.reference_doc_ids||[]).concat(refs.file_id?[refs.file_id]:[]);
  var refFile=refIds.map(function(id){return '#'+id+
    (pfFileNames[id]?' · '+pfFileNames[id]:'');}).join('、')||'—';
  var row=function(label,value){
    return '<div class="cfg-row"><label>'+escHtml(label)+'</label>'+
      '<span class="hint-spacer"></span><span class="cfg-static">'+
      escHtml(value)+'</span></div>';
  };
  box.innerHTML='<div class="msg">只读展示 · '+
    '<a class="linkbtn" target="_blank" rel="noopener" href="/extract?rule='+
    meta.id+'">打开详情编辑 →</a></div>'+
    row('规则名称',d.name||meta.name)+
    row('抽取规格',mapping.spec_version?('v'+mapping.spec_version):'v1（默认）')+
    row('参考文件',refFile)+
    row('表定位',tbl)+
    row('输出字段',fields)+
    row('字段映射',maps);
}
function pfPreviewUrl(){
  var u='/preview?file='+pfId;
  if(pfResultId!=null) u+='&result='+encodeURIComponent(pfResultId);
  if(pfNode==='review') u+='&view=review';
  return u;
}
/* ---- 产物区内联血缘追溯 ---- */
function pfLinBaseSrc(){
  var u='/preview?embed=1&file='+pfId;
  if(pfResultId!=null) u+='&result='+encodeURIComponent(pfResultId);
  return u;
}
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
  if(pfResultId==null) return;
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
      {c1TraceKey:{key:key,index:index,extract_result_id:pfResultId}},'*');
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
        if(String(o.j.extract_result_id)!==String(pfResultId)) return;
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
  if(!e.data.c1PinField||!pfLineageOpen||pfResultId==null) return;
  if(e.data.c1PinField.extract_result_id!=null&&
    String(e.data.c1PinField.extract_result_id)!==String(pfResultId)) return;
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
  var p=pfData||{}, st=String(p.state||''), result=pfCurrentResult(), binding=pfCurrentBinding();
  var busy=st==='parsing'||st==='loading'||(result&&result.status==='running'), label='', dis=false, tip='';
  if(pfNode==='parse'){
    label='执行解析'; dis=busy;
    tip=busy?'正在处理中，请稍候。'
      :(st==='loaded'
        ?'仅重新运行解析并生成 test/ 下的新报告；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
        :'按当前解析参数执行解析；已有全部抽取结果、产物、回执与校验结论会被清除。');
  }else if(pfNode==='extract'){
    label='执行抽取'; dis=busy;
    tip=busy?'正在处理中，请稍候。'
      :'按所选单行规则执行；同资料同规则覆盖自己的结果与绑定，其他结果不变。';
  }else if(pfNode==='review'){
    var c=result&&result.review_counts||{}, pend=(c.pending||0)+(c.edited||0);
    label='执行校验'; dis=busy||!result;
    tip=busy?'正在处理中，请稍候。':(!result?'请先完成抽取。':
      ('将所选结果全部 '+pend+' 条待审记录设为通过。'+
        (c.rejected?'另有 '+c.rejected+' 条已拒绝记录需人工处理。':'')));
  }else{
    var confirmed=binding&&binding.status==='confirmed';
    label='执行入库'; dis=busy||!confirmed;
    tip=busy?'正在处理中，请稍候。':(!binding?'请先为所选结果配置入库映射。':
      (confirmed?('按所选结果已确认的映射写入 '+binding.target_table+'。')
        :'入库绑定尚未显式确认，请通过入库向导完成预检与确认。'));
  }
  return '<button type="button" class="btn mini" id="pfAct" title="'+escHtml(tip)+'"'+
    (dis?' disabled':'')+'>'+label+'</button>';
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
    var l=pfCurrentBinding();
    if(l){
      openLink='<a class="proc-open" target="_blank" rel="noopener" href="/dashboard?ds='+
        encodeURIComponent(l.datasource_id||'')+'&table='+encodeURIComponent(l.target_table)+
        '&lt='+encodeURIComponent(l.load_table_id||'')+'&file='+pfId+
        '&result='+encodeURIComponent(pfResultId)+'">打开数据看板 →</a>';
      tools='<button type="button" class="btn mini" id="pfPreflight">预检</button>'+
        '<button type="button" class="btn mini" id="pfReceipt">回执 / 隔离</button>';
      body='<div class="proc-kv"><span><b>抽取结果</b>#'+pfResultId+'</span>'+
        '<span><b>目标表</b>'+escHtml(l.target_table)+'</span>'+
        '<span><b>写入</b>'+escHtml(modeLabel(l.write_mode))+'</span>'+
        '<span><b>绑定</b>'+escHtml(l.status||'—')+'</span></div>'+
        '<div class="msg" id="pfPreMsg">'+
        escHtml(pfPreResult?('预检 '+pfPreResult.total+' 条 · 新增 '+pfPreResult.insert+
          ' · 覆盖 '+pfPreResult.update+' · 跳过 '+pfPreResult.skip+
          ' · 隔离 '+pfPreResult.quarantine):(pfPreError||''))+'</div>'+
        '<div id="pfRowsBox">加载中…</div>';
    }else{
      body='<div class="empty">尚未绑定入库映射</div>';
    }
  }
  var linPanel=pfNode==='parse'||pfResultId==null?'':
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
    if(rb) rb.onclick=pfOpenReceiptDrawer;
    if(pfCurrentBinding()) pfLoadRows();
  }
  pfBindLinCells();
}
function pfLoadRows(){
  var box=document.getElementById('pfRowsBox');
  if(!box) return;
  var l=pfCurrentBinding()||{};
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
  if(pfResultId==null){ if(m) m.textContent='请先选择抽取结果'; return; }
  var resultId=pfResultId, btn=document.getElementById('pfPreflight');
  if(btn) btn.disabled=true;
  if(m) m.textContent='预检中（只读 · 按所选结果已绑定目标）…';
  pfApi('POST','/api/extract-results/'+encodeURIComponent(resultId)+'/load-preview',{})
    .then(function(o){
      if(String(pfResultId)!==String(resultId)) return;
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
      if(String(pfResultId)!==String(resultId)) return;
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
    var btn=this, msg='', action=pfNode, resultId=pfResultId;
    var result=pfCurrentResult(), binding=pfCurrentBinding();
    var m=document.getElementById('pfActMsg');
    if(action==='parse'){
      msg=st==='loaded'
        ?'确认重新执行解析？\n仅生成 test/ 下的新产物；业务数据、正式产物、暂存、回执和已入库状态全部保留。'
        :'确认按当前解析参数执行解析？\n将清空全部抽取结果、暂存、产物、回执与校验结论。';
    }else if(action==='extract'){
      var rv=document.getElementById('pfRule');
      var ruleId=rv&&rv.value?parseInt(rv.value,10):null;
      if(!ruleId){
        if(m) m.textContent='失败：请先选择抽取规则'; return;
      }
      var same=!!(result&&Number(result.rule_id)===ruleId);
      msg=same?'所选规则已有抽取结果；重新抽取将覆盖该结果的记录、校验结论与未确认绑定。\n已写入业务数据库的数据不会回滚，其他结果不受影响。确认继续？'
        :'确认按所选抽取规则执行抽取？';
    }else if(action==='review'){
      if(!result){ if(m) m.textContent='失败：请先完成抽取'; return; }
      var c=result.review_counts||{}, pend=(c.pending||0)+(c.edited||0);
      msg='确认将抽取结果 #'+resultId+' 的全部 '+pend+' 条待审记录设为通过？\n其他结果不受影响。';
    }else{
      if(!binding||binding.status!=='confirmed'){
        if(m) m.textContent='失败：请先通过入库向导完成映射预检与显式确认'; return;
      }
      msg='确认将抽取结果 #'+resultId+' 按已确认映射写入 '+binding.target_table+'？\n其他结果不受影响。';
    }
    if(!confirm(msg)) return;
    btn.disabled=true;
    var req;
    if(action==='parse') req=pfApi('POST','/api/sources/'+pfId+'/reparse',
      st==='loaded'?{test_mode:true}:{});
    else if(action==='extract'){
      req=pfApi('POST','/api/sources/'+pfId+'/extract',{rule_id:ruleId,force:same});
    }else if(action==='review'){
      req=pfApi('POST','/api/extract-results/'+encodeURIComponent(resultId)+'/approve-all',{});
    }else{
      req=pfApi('POST','/api/extract-results/'+encodeURIComponent(resultId)+'/load',{});
    }
    if(m) m.textContent='执行中…';
    req.then(function(o){
      if(!(o.s===200&&o.j&&o.j.ok)){
        btn.disabled=false;
        if(m) m.textContent='失败：'+((o.j&&o.j.error)||o.s);
        return;
      }
      if(action==='parse'){
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
      if(action==='extract'&&o.j.extract_result_id) pfResultId=o.j.extract_result_id;
      pfLoad();
    }).catch(function(e){
      btn.disabled=false;
      if(m) m.textContent='失败：'+(e&&e.message||'平台库不可用');
    });
  };
}
/* ---- 单结果入库：沿用现有向导，依赖按需加载，HTML 无需改动 ---- */
function pfEnsureWizard(){
  if(typeof window.openLoadWizard==='function') return Promise.resolve();
  if(pfWizardLoading) return pfWizardLoading;
  pfWizardLoading=new Promise(function(resolve,reject){
    if(!document.querySelector('link[href="/static/wizard.css"]')){
      var link=document.createElement('link');
      link.rel='stylesheet'; link.href='/static/wizard.css';
      document.head.appendChild(link);
    }
    var script=document.createElement('script');
    script.src='/static/wizard.js';
    script.onload=function(){ pfWizardLoading=null; resolve(); };
    script.onerror=function(){ pfWizardLoading=null; reject(new Error('入库向导加载失败')); };
    document.body.appendChild(script);
  });
  return pfWizardLoading;
}
function pfOpenLoadWizard(){
  var result=pfCurrentResult(), resultId=pfResultId, btn=document.getElementById('pfLoadWizard');
  if(!result||result.status!=='ready'){
    pfCfgMsg('仅已完成的抽取结果可配置入库',true); return;
  }
  if(btn) btn.disabled=true;
  pfEnsureWizard().then(function(){
    return pfApi('GET','/api/extract-results/'+encodeURIComponent(resultId)+'/gate');
  }).then(function(o){
    if(!(o.s===200&&o.j&&o.j.ok)) throw new Error((o.j&&o.j.error)||('HTTP '+o.s));
    openLoadWizard({fileId:pfId,extractResultId:resultId,result:result,
      gate:o.j,onDone:pfLoad});
  }).catch(function(e){ pfCfgMsg('无法打开入库向导：'+(e.message||e),true); })
    .then(function(){ if(btn&&btn.isConnected) btn.disabled=false; });
}
/* ---- 当前结果专属回执与隔离，避免资料级旧聚合接口 ---- */
function pfOpenReceiptDrawer(){
  if(pfResultId==null) return;
  var resultId=pfResultId, drawer=document.getElementById('receipt');
  if(!drawer) return;
  document.getElementById('rctitle').textContent='抽取结果 #'+resultId+' · 入库回执 / 隔离';
  document.getElementById('rcbody').innerHTML='<div class="empty">加载中…</div>';
  animDrawerOpen(drawer);
  var base='/api/extract-results/'+encodeURIComponent(resultId);
  Promise.all([pfApi('GET',base+'/load-log'),pfApi('GET',base+'/quarantine')])
    .then(function(res){
      if(res[0].s!==200||res[1].s!==200) throw new Error('读取失败');
      var logs=res[0].j.items||[], qs=(res[1].j.items||[]).filter(function(q){
        return q.stage==='load';
      });
      var html='<div class="msg" style="margin-bottom:6px">当前结果回执 '+logs.length+
        ' 条（重新入库时，已有回执的记录将自动跳过）</div>';
      html+=logs.length?
        '<table class="list"><thead><tr><th>记录</th><th>动作</th>'+
        '<th>目标主键</th><th>时间</th></tr></thead><tbody>'+
        logs.map(function(l){
          return '<tr><td class="num">'+(l.record_index+1)+'</td>'+
            '<td>'+escHtml({insert:'新增',update:'覆盖'}[l.action]||l.action)+'</td>'+
            '<td><code class="mono">'+escHtml(l.target_pk)+'</code></td>'+
            '<td class="num">'+fmtTime(l.loaded_at)+'</td></tr>';
        }).join('')+'</tbody></table>':'<div class="empty">暂无回执记录</div>';
      html+='<div class="msg" style="margin:12px 0 6px">当前结果隔离 '+qs.length+
        ' 条（只读；重新入库将重试未写入的记录）</div>';
      html+=qs.length?
        '<table class="list"><thead><tr><th>记录</th><th>原因</th><th>时间</th></tr></thead><tbody>'+
        qs.map(function(q){
          return '<tr><td class="num">'+(q.record_index+1)+'</td>'+
            '<td>'+escHtml(q.reason)+'</td><td class="num">'+fmtTime(q.created_at)+'</td></tr>';
        }).join('')+'</tbody></table>':'<div class="empty">暂无隔离记录</div>';
      document.getElementById('rcbody').innerHTML=html;
    }).catch(function(){
      document.getElementById('rcbody').innerHTML=
        '<div class="empty">读取失败：平台库不可用或结果已变更</div>';
    });
}
pfInit();
