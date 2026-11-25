/* web/process.js — 资料处理独立页：四节点 + 当前节点配置 / 结果 / 显式执行
   数据源：/api/sources/{id}/pipeline + /config（只读拉取）；写操作仍走原 API。
   红线：保存配置只写配置，不自动重跑；执行动作必须用户显式点击。 */
var pfId=null, pfName='', pfNode='parse', pfData=null, pfCfg=null, pfPending={};
var pfPreResult=null, pfPreError='';
var PF_NODES=[['parse','解析'],['extract','抽取'],['review','校验'],['load','入库']];
var PF_TITLE={parse:'解析参数',extract:'抽取规则',review:'校验规则',load:'入库映射'};

function pfApi(method,path,body){
  return fetch(path,{method:method,
    headers:{'Content-Type':'application/json'},
    body:body===undefined?undefined:JSON.stringify(body)})
    .then(function(r){return r.json().then(function(j){return {s:r.status,j:j};});});
}
function pfMsg(t,bad){
  var e=document.getElementById('pfCfgMsg');
  if(!e) return;
  e.textContent=t||''; e.className='msg'+(bad?' err':'');
}
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
  pfLoad();
}
function pfLoad(){
  pfPreResult=null; pfPreError='';
  document.getElementById('procBody').innerHTML='<div class="empty">加载中…</div>';
  Promise.all([
    pfApi('GET','/api/sources/'+pfId+'/pipeline'),
    pfApi('GET','/api/sources/'+pfId+'/config')
  ]).then(function(rs){
    if(!(rs[0].s===200&&rs[0].j&&rs[0].j.ok))
      throw new Error((rs[0].j&&rs[0].j.error)||('HTTP '+rs[0].s));
    if(!(rs[1].s===200&&rs[1].j&&rs[1].j.ok))
      throw new Error((rs[1].j&&rs[1].j.error)||('HTTP '+rs[1].s));
    pfData=rs[0].j.pipeline||{};
    pfName=(rs[0].j.file&&rs[0].j.file.name)||('资料 '+pfId);
    pfCfg=rs[1].j;
    document.getElementById('procBody').innerHTML=
      '<div class="proc-wrap">'+
        '<div class="pipe-flow proc-flow" id="procFlow"></div>'+
        '<div class="proc-sec" id="procConfig"></div>'+
        '<div class="proc-sec proc-result" id="procResult"></div>'+
        '<div class="proc-actions" id="procActions"></div>'+
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
  pfRenderActions();
}
function pfCollect(){
  if(!pfCfg) return;
  if(pfNode==='params'){
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
  var tip=function(t){ return '<span class="hint" tabindex="0" data-tip="'+
    escHtml(t||'')+'">?</span>'; };
  var head=function(title,t){ return '<h4>'+escHtml(title)+tip(t)+'</h4>'; };
  var ro=['parsing','loading','loaded'].indexOf(String((pfData||{}).state||''))>=0;
  var dis=ro?' disabled':'';
  var h='<div class="proc-sechd"><b>配置 · '+PF_TITLE[pfNode]+'</b>'+
    '<span class="msg" id="pfCfgMsg">'+(ro?'当前状态配置只读':'')+'</span>'+
    (pfNode==='review'||ro?'':'<button type="button" class="btn mini" id="pfCfgSave">保存配置</button>')+
    '</div><details id="pfCfgFold" open><summary>配置内容（点击收起 / 展开）</summary>'+
    '<div class="proc-cfgbody">';
  if(pfNode==='params'){
    h+=head('解析参数','对本次资料生效，重放解析时使用。保存只写配置，需显式点击「执行解析 / 重新解析」才会生效。');
    (pfCfg.schema||[]).forEach(function(p){
      var key=p.key, label=p.label||key, val=pfCfg.params[key];
      if(val===undefined||val===null) val=p.default;
      var desc=p.desc||p.help||'';
      h+='<div class="cfg-row"><label>'+escHtml(label)+'</label>'+(desc?tip(desc):spacer);
      if(p.type==='bool'){
        h+='<select data-cp="'+escHtml(key)+'"'+dis+'>'+
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
          ' placeholder="'+escHtml(p.default!=null?String(p.default):'')+'"'+dis+'>';
      }
      if(p.unit) h+='<span class="cfg-unit">'+escHtml(p.unit)+'</span>';
      h+='</div>';
    });
  }else if(pfNode==='extract'){
    h+=head('抽取规则','在「执行抽取」时按此规则生成记录；保存配置不会重抽已有记录。');
    h+='<div class="cfg-row"><label>抽取规则版本</label>'+spacer+
      '<select id="pfRule"'+dis+'><option value="">（不绑定 · 执行抽取时用默认原始透传）</option>';
    (pfCfg.rules||[]).forEach(function(v){
      h+='<option value="'+v.version_id+'"'+
        (pfCfg.rule_version_id===v.version_id?' selected':'')+'>'+
        escHtml(v.name+' v'+v.version+(v.current?'（当前）':''))+'</option>';
    });
    h+='</select></div>';
  }else if(pfNode==='review'){
    h+=head('校验规则','当前校验为逐条人工改值 / 确认 / 拒绝；「执行校验」可一键将全部待审记录设为通过。');
    h+='<div class="empty" style="padding:20px"><b>自动化校验规则：待实现</b></div>';
  }else{
    h+=head('入库映射','目标在「执行入库」时消费；映射须与资料的抽取规则匹配，保存配置不会执行入库。');
    h+='<div class="cfg-row"><label>业务库</label>'+spacer+'<select id="pfDs"'+dis+'>'+
      '<option value="">（未选择）</option>';
    (pfCfg.datasources||[]).forEach(function(d){
      h+='<option value="'+d.id+'"'+
        (pfCfg.load&&pfCfg.load.datasource_id===d.id?' selected':'')+'>'+
        escHtml(d.name+' · '+d.host+'/'+d.db_name)+'</option>';
    });
    h+='</select></div>'+
      '<div class="cfg-row"><label>入库映射</label>'+spacer+'<select id="pfLt"'+dis+'>'+
      '<option value="">（未选择）</option>';
    (pfCfg.load_tables||[]).forEach(function(t){
      h+='<option value="'+t.id+'" data-ds="'+t.datasource_id+'"'+
        (pfCfg.load&&pfCfg.load.load_table_id===t.id?' selected':'')+'>'+
        escHtml(t.target_table+' · '+t.write_mode)+'</option>';
    });
    h+='</select></div>';
  }
  h+='</div></details>';
  box.innerHTML=h;
  var ds=document.getElementById('pfDs'), lt=document.getElementById('pfLt');
  if(ds&&lt){
    ds.onchange=function(){
      var did=this.value;
      Array.prototype.forEach.call(lt.options,function(o){
        if(!o.value) return;
        o.hidden=!!did&&o.getAttribute('data-ds')!==did;
      });
      lt.value='';
    };
    if(pfCfg.load&&pfCfg.load.datasource_id) ds.onchange();
  }
  var mark=function(){ if(ro) return; pfMsg('有未保存的修改，需点击「保存配置」'); };
  document.querySelectorAll('#procConfig [data-cp]').forEach(function(el){
    el.onchange=mark;
  });
  ['pfRule','pfDs','pfLt'].forEach(function(id){
    var el=document.getElementById(id);
    if(el) el.onchange=mark;
  });
  var save=document.getElementById('pfCfgSave');
  if(save) save.onclick=function(){
    pfCollect();
    if(!Object.keys(pfPending).length){ pfMsg('没有需要保存的修改'); return; }
    var btn=this; btn.disabled=true; pfMsg('保存中…');
    pfApi('POST','/api/sources/'+pfId+'/config',pfPending).then(function(o){
      btn.disabled=false;
      if(!(o.s===200&&o.j&&o.j.ok)){
        pfMsg('保存失败：'+((o.j&&o.j.error)||o.s),true); return;
      }
      pfPending={}; pfLoad();
    }).catch(function(){ btn.disabled=false; pfMsg('保存失败：平台库不可用',true); });
  };
}
function pfResultCard(title,desc,href,label){
  return '<div class="parse-card"><h4>'+escHtml(title)+'</h4>'+
    '<p class="msg">'+escHtml(desc)+'</p>'+
    (href?'<a class="linkbtn" target="_blank" rel="noopener" href="'+escHtml(href)+
      '">'+escHtml(label)+' →</a>':'<span class="msg">暂无产物</span>')+'</div>';
}
function pfRenderResult(){
  var p=pfData||{}, box=document.getElementById('procResult'), h='', extra='';
  if(pfNode==='parse'){
    var arts=p.parse_artifacts||[], has=arts.indexOf('对照报告.html')>=0;
    var reportUrl='/files/'+pfId+'/'+encodeURIComponent('对照报告.html');
    h=pfResultCard('解析报告','页面图与结构化结果逐项对照',
      has?reportUrl:'','打开解析报告');
    h+=pfResultCard('parse.json','标准契约完整产物',
      arts.indexOf('parse.json')>=0?'/files/'+pfId+'/parse.json':'','打开 parse.json');
    extra=has
      ? '<details id="pfReportFold" open><summary>内联查看对照报告（点击收起）</summary>'+
        '<iframe class="proc-report" src="'+escHtml(reportUrl)+'" loading="lazy"'+
        ' title="对照报告"></iframe></details>'
      : '';
  }else if(pfNode==='extract'){
    var c=p.review_counts||{}, n=Object.keys(c).reduce(function(a,k){return a+c[k];},0);
    h=pfResultCard('数据预览','暂存记录 '+n+' 条 · 规则 '+
      (p.rule?(p.rule.name+' v'+p.rule.version):'未绑定'),'/preview?file='+pfId,'打开数据预览');
    extra='<div class="msg">双击单元格改值 / ✓确认 / ✗拒绝；单击或悬停可回溯源图。'+
      '校验结论会直接作用于这里的记录。</div>';
  }else if(pfNode==='review'){
    var r=p.review_counts||{};
    h=pfResultCard('校验视图','待校验 '+(r.pending||0)+' · 已修改 '+(r.edited||0)+
      ' · 已拒绝 '+(r.rejected||0)+' · 已确认 '+(r.confirmed||0),
      '/preview?file='+pfId+'&view=review','打开校验视图');
    extra='<div class="msg">进入校验视图后优先定位到待审记录；校验与抽取共用同一份暂存记录，无需切换页面。</div>';
  }else{
    var l=p.load||{}, acts=p.load_actions||{};
    if(l.target_table){
      h=pfResultCard('数据看板','目标表 '+l.target_table+' · 新增 '+(acts.insert||0)+
        ' / 覆盖 '+(acts.update||0),'/dashboard?ds='+encodeURIComponent(l.datasource_id||'')+
        '&table='+encodeURIComponent(l.target_table),'打开数据看板');
    }else{
      h='<div class="empty">尚未绑定入库映射。请在上方配置中选择业务库与映射，再显式执行入库。</div>';
    }
    var pre=pfPreResult
      ? ('预检：共 '+pfPreResult.total+' 条 · 新增 '+pfPreResult.insert+
         ' · 覆盖 '+pfPreResult.update+' · 跳过 '+pfPreResult.skip+
         ' · 隔离 '+pfPreResult.quarantine)
      : (pfPreError||'预检只读，不写库、不绑定目标。');
    extra='<div class="proc-toolrow">'+
      '<button type="button" class="btn mini" id="pfPreflight">运行入库预检</button>'+
      '<button type="button" class="btn mini" id="pfReceipt">回执 / 隔离</button>'+
      '<span class="msg" id="pfPreMsg">'+escHtml(pre)+'</span></div>';
  }
  box.innerHTML='<div class="proc-sechd"><b>结果 · '+PF_TITLE[pfNode]+
    '</b></div><div class="parse-pair">'+h+'</div>'+extra;
  if(pfNode==='load'){
    var pb=document.getElementById('pfPreflight');
    if(pb) pb.onclick=pfRunPreflight;
    var rb=document.getElementById('pfReceipt');
    if(rb) rb.onclick=function(){ openReceiptDrawer(pfId); };
  }
}
function pfRunPreflight(){
  var m=document.getElementById('pfPreMsg');
  var sel=document.getElementById('pfLt');
  var bound=pfData.load&&pfData.load.load_table_id;
  var tid=bound||(sel&&sel.value?parseInt(sel.value,10)
    :((pfCfg&&pfCfg.load&&pfCfg.load.load_table_id)||null));
  if(!tid){
    if(m) m.textContent='请先在上方配置中选择入库映射';
    return;
  }
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
    if(m) m.textContent='预检：共 '+o.j.total+' 条 · 新增 '+o.j.insert+
      ' · 覆盖 '+o.j.update+' · 跳过 '+o.j.skip+' · 隔离 '+o.j.quarantine;
  }).catch(function(e){
    if(btn) btn.disabled=false;
    pfPreResult=null; pfPreError='预检失败：'+(e&&e.message||'平台库不可用');
    if(m) m.textContent=pfPreError;
  });
}
function pfActionHtml(){
  var p=pfData||{}, st=String(p.state||'');
  var busy=st==='parsing'||st==='loading', label='', dis=false, tip='';
  if(pfNode==='parse'){
    var can=!busy&&st!=='loaded';
    label=st==='pending'?'执行解析':'重新解析';
    dis=!can;
    tip=busy?'正在处理中，请稍候。':(st==='loaded'
      ?'资料已入库，记录只读，不能重新解析。'
      :'按当前解析参数原地重放；会清空暂存、产物、回执与校验结论。');
  }else if(pfNode==='extract'){
    var canE=st==='to_extract'||st==='to_review'||st==='to_load';
    label='执行抽取'; dis=!canE||busy;
    tip=st==='to_extract'?'按当前抽取规则生成暂存记录。'
      :(canE?'已有暂存记录，重新抽取将覆盖校验结论。':'请先执行解析，生成解析产物。');
  }else if(pfNode==='review'){
    var c=p.review_counts||{}, pend=(c.pending||0)+(c.edited||0);
    var canR=st==='to_review'||st==='to_load';
    label='执行校验'; dis=!canR||busy||!pend;
    tip=canR?(pend?('将全部 '+pend+' 条待审记录设为通过。'+
      (c.rejected?'另有 '+c.rejected+' 条已拒绝记录需人工处理。':'')):'暂无待审记录。')
      :'请先执行抽取，生成暂存记录。';
  }else{
    var canL=st==='to_load'&&!!(p.load&&p.load.load_table_id);
    label='执行入库'; dis=!canL||busy;
    tip=st!=='to_load'?'请先完成校验，全部记录通过后才能入库。'
      :(p.load&&p.load.load_table_id
        ?('按已配置的入库映射写入 '+(p.load.target_table||'')+'。')
        :'请先在「配置」里绑定入库映射。');
  }
  return '<button type="button" class="btn" id="pfAct"'+(dis?' disabled':'')+'>'+
    label+'</button><span class="hint" tabindex="0" data-tip="'+escHtml(tip)+'">?</span>'+
    '<span class="msg" id="pfActMsg"></span>';
}
function pfRenderActions(){
  document.getElementById('procActions').innerHTML=pfActionHtml();
  var b=document.getElementById('pfAct');
  if(!b) return;
  var st=String((pfData||{}).state||'');
  b.onclick=function(){
    var btn=this, msg='';
    if(pfNode==='parse'){
      msg='确认按当前解析参数重新解析？\n将清空暂存、产物、回执与校验结论。';
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
    if(pfNode==='parse') req=pfApi('POST','/api/sources/'+pfId+'/reparse',{});
    else if(pfNode==='extract') req=pfApi('POST','/api/sources/'+pfId+'/extract',
      (st==='to_review'||st==='to_load')?{force:true}:{});
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
      pfLoad();
    }).catch(function(e){
      btn.disabled=false;
      if(m) m.textContent='失败：'+(e&&e.message||'平台库不可用');
    });
  };
}
pfInit();
