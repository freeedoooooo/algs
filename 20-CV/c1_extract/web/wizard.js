/* web/wizard.js — 四步入库向导（design-ux-load-wizard §2，tasks/staging 共用）：
   ① 选目标（已有规则直达③／新建＝业务库＋表）→ ② 字段对齐（自动匹配，仅新建）
   → ③ 过目（前 3 条样例＋load-preview dry-run 计数）→ ④ 执行。
   红线：④ 前不落库；新建规则在执行瞬间 POST /api/load/tables 落库，
   /load 失败则补偿 DELETE，不留孤儿；绑定/门禁/预检语义仍由服务端把关。 */
var wz=null;
function wzApi(method,url,body){
  var opt={method:method,headers:{}};
  if(body!==undefined){
    opt.headers['Content-Type']='application/json';
    opt.body=JSON.stringify(body);
  }
  return fetch(url,opt).then(function(r){
    return r.json().catch(function(){return {};}).then(function(j){
      if(!r.ok||j.ok===false) throw new Error(j.error||('HTTP '+r.status));
      return j;
    });
  });
}
function wzMsg(t,bad){
  var e=document.getElementById('wzmsg');
  if(!e) return;
  e.textContent=t||''; e.className=bad?'msg err':'msg';
}
function wzUi(){
  var m=document.getElementById('wzmask');
  if(m) return m;
  m=document.createElement('div');
  m.className='wzmask'; m.id='wzmask';
  m.innerHTML='<div class="wzpanel">'+
    '<div class="wzhead"><h2 id="wztitle">入库向导</h2><span class="spacer"></span>'+
    '<button type="button" class="dclose" id="wzclose">关闭 (Esc)</button></div>'+
    '<div class="wzsteps" id="wzsteps"></div>'+
    '<div class="wzbody" id="wzbody"></div>'+
    '<div class="wzfoot"><span class="msg" id="wzmsg"></span><span class="spacer"></span>'+
    '<button type="button" class="btn ghost" id="wzprev">上一步</button>'+
    '<button type="button" class="btn" id="wznext">下一步</button></div>'+
    '</div>';
  document.body.appendChild(m);
  document.getElementById('wzclose').onclick=closeLoadWizard;
  m.addEventListener('click',function(e){ if(e.target===m) closeLoadWizard(); });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&wz&&!m.hidden) closeLoadWizard();
  });
  document.getElementById('wzprev').onclick=function(){
    if(!wz||wz.busy) return;
    wzGo(wz.step===3&&wz.mode==='exist'?1:wz.step-1);
  };
  document.getElementById('wznext').onclick=function(){ wzAdvance(); };
  return m;
}
function openLoadWizard(opts){
  wz={taskId:opts.taskId, templateId:opts.templateId,
      onDone:opts.onDone, getSample:opts.getSample||null,
      step:1, mode:'', ds1:'', rule1:'', ds2:'', table2:'',
      dsList:null, ruleList:null, tables2:null,
      tfields:null, cols:null, fields:null,
      wm:'upsert', busy:false, createdRule:null, previewErr:''};
  var m=wzUi();
  document.getElementById('wztitle').textContent=
    '任务 #'+opts.taskId+' · 入库向导';
  m.hidden=false;
  wzRender(true);
}
function closeLoadWizard(){
  var m=document.getElementById('wzmask');
  if(m) m.hidden=true;
  wz=null;
}
function wzChips(){
  var names=['① 选目标','② 字段对齐','③ 过目','④ 执行'];
  var skip2=(wz.mode==='exist');
  document.getElementById('wzsteps').innerHTML=names.map(function(n,i){
    var s=i+1, cls='wst';
    if(s===wz.step) cls+=' on';
    else if(s<wz.step||(skip2&&s===2&&wz.step>=3)) cls+=' done';
    return '<span class="'+cls+'">'+n+'</span>';
  }).join('');
}
function wzFooter(){
  var prev=document.getElementById('wzprev'),next=document.getElementById('wznext');
  prev.hidden=wz.step<=1||wz.busy;
  next.textContent=wz.step===3?'执行入库':'下一步';
  next.disabled=!!wz.busy||wz.step===4||(wz.step===3&&!!wz.previewErr);
}
function wzGo(step){ wz.step=step; wzRender(); }
function wzRender(first){
  if(!wz) return;
  wzChips(); wzFooter();
  if(!first) wzMsg('');
  var b=document.getElementById('wzbody');
  if(wz.step===1){ wzStep1(b); }
  else if(wz.step===2){ wzStep2(b); }
  else if(wz.step===3){ wzStep3(b); }
  else{ b.innerHTML='<div class="empty">正在绑定并写入…</div>'; }
}
/* ---- step1 选目标 ---- */
function wzDsOpt(d){
  return '<option value="'+d.id+'">'+escHtml(d.name+' · '+d.host+'/'+d.db_name)+'</option>';
}
function wzStep1(b){
  if(!wz.dsList){
    b.innerHTML='<div class="empty">加载业务库与规则…</div>';
    Promise.all([
      wzApi('GET','/api/load/datasources'),
      wzApi('GET','/api/load/tables')
    ]).then(function(res){
      if(!wz||wz.step!==1) return;
      wz.dsList=res[0].items||[];
      wz.ruleList=(res[1].items||[]).filter(function(m){
        return String(m.template_id)===String(wz.templateId);});
      wzRender();
    }).catch(function(e){
      if(!wz||wz.step!==1) return;
      b.innerHTML='<div class="empty">读取失败：'+escHtml(e.message)+
        '（平台库不可用？）</div>';
    });
    return;
  }
  var rules=wz.ruleList||[];
  var dsWithRules=wz.dsList.filter(function(d){
    return rules.some(function(m){return m.datasource_id===d.id;});});
  var html='<div class="wzsec">用已有入库规则</div>';
  if(rules.length){
    html+='<div class="wzrow"><label>业务库</label><select id="wzds1">'+
      '<option value="">选择业务库</option>'+
      dsWithRules.map(wzDsOpt).join('')+'</select></div>'+
      '<div class="wzrow"><label>入库规则</label><select id="wzrule1"></select></div>';
  }else{
    html+='<div class="hint">这个模板还没有已配好的规则，用下方「新建」。</div>';
  }
  html+='<div class="wzsec">新建入库规则</div>'+
    '<div class="wzrow"><label>业务库</label><select id="wzds2">'+
    '<option value="">选择业务库</option>'+
    wz.dsList.map(wzDsOpt).join('')+'</select></div>'+
    '<div class="wzrow"><label>目标表</label><select id="wztable2" disabled>'+
    '<option value="">先选业务库</option></select></div>'+
    '<div class="hint">没有合适的业务库？到 <a href="/rules" target="_blank">入库规则</a> '+
    '页新建（新窗口打开，不丢这里的进度）。字段对齐下一步做。</div>';
  b.innerHTML=html;
  var ds1=b.querySelector('#wzds1'), rule1=b.querySelector('#wzrule1');
  var ds2=b.querySelector('#wzds2'), tb2=b.querySelector('#wztable2');
  function fillRule1(){
    if(!rule1) return;
    var list=rules.filter(function(m){
      return String(m.datasource_id)===String(ds1.value);});
    rule1.innerHTML='<option value="">选择规则</option>'+list.map(function(m){
      return '<option value="'+m.id+'">'+escHtml(
        m.target_table+' · '+modeLabel(m.write_mode))+'</option>';}).join('');
    if(wz.rule1&&list.some(function(m){return String(m.id)===wz.rule1;}))
      rule1.value=wz.rule1;
    if(ds1.value&&wz.ds1!==ds1.value){ wz.rule1=''; }
    wz.ds1=ds1?ds1.value:'';
    wzClearNewIfChosen();
  }
  function fillTable2(){
    var ts=wz.tables2||[];
    tb2.innerHTML='<option value="">选择目标表</option>'+ts.map(function(t){
      return '<option value="'+escHtml(t)+'">'+escHtml(t)+'</option>';}).join('');
    if(wz.table2&&ts.indexOf(wz.table2)>=0) tb2.value=wz.table2;
  }
  function wzClearNewIfChosen(){
    if(rule1&&rule1.value){ wz.mode='exist'; wz.rule1=rule1.value; }
  }
  if(ds1){
    ds1.value=wz.ds1||'';
    ds1.onchange=fillRule1; fillRule1();
    rule1.onchange=function(){
      wz.rule1=rule1.value; wz.ds1=ds1.value;
      if(rule1.value) wzMsg('已选规则：下一步直接「过目」');
    };
  }
  ds2.value=wz.ds2||'';
  ds2.onchange=function(){
    wz.ds2=ds2.value; wz.table2=''; wz.tables2=null;
    tb2.disabled=!ds2.value;
    tb2.innerHTML='<option value="">加载中…</option>';
    if(!ds2.value){ tb2.innerHTML='<option value="">先选业务库</option>'; return; }
    wzApi('GET','/api/load/datasources/'+ds2.value+'/tables').then(function(j){
      if(!wz||wz.step!==1) return;
      wz.tables2=j.items||[]; fillTable2();
    }).catch(function(e){
      if(!wz||wz.step!==1) return;
      tb2.innerHTML='<option value="">加载失败</option>';
      wzMsg('目标表加载失败：'+e.message,true);
    });
  };
  tb2.onchange=function(){ wz.table2=tb2.value; };
  if(wz.ds2&&ds2.value===String(wz.ds2)) ds2.onchange();
}
function wzRule(){
  var id=String(wz.rule1), hit=null;
  (wz.ruleList||[]).forEach(function(m){ if(String(m.id)===id) hit=m; });
  return hit;
}
function wzAdvance(){
  if(!wz||wz.busy) return;
  if(wz.step===1){
    if(wz.rule1&&wz.ds1===String(wzRule().datasource_id)){
      var r=wzRule();
      wz.mode='exist'; wz.dsId=r.datasource_id; wz.table=r.target_table;
      wzGo(3); return;
    }
    if(wz.ds2&&wz.table2){
      wz.mode='new'; wz.dsId=Number(wz.ds2); wz.table=wz.table2;
      wz.tfields=null; wzGo(2); return;  /* step2 拉字段+列 */
    }
    if(wz.rule1){ wzMsg('规则与业务库不一致，请重选',true); return; }
    wzMsg('请先选一条已有规则，或选业务库＋目标表新建',true);
    return;
  }
  if(wz.step===2){ if(wzCollect()) wzGo(3); return; }
  if(wz.step===3){ wzExecute(); return; }
}
/* ---- step2 字段对齐（新建规则草稿，复用 §1.3 自动匹配口径） ---- */
function wzStep2(b){
  if(!wz.tfields){
    b.innerHTML='<div class="empty">加载模板字段与目标列…</div>';
    Promise.all([
      wzApi('GET','/api/templates/'+wz.templateId).then(function(j){
        var sj=j.schema_json;
        var fs=(sj&&typeof sj==='object'&&!Array.isArray(sj)&&sj.fields)||[];
        return fs.map(function(f){return f.name;}).filter(Boolean);
      }),
      wzApi('GET','/api/load/datasources/'+wz.dsId+'/columns?table='+
            encodeURIComponent(wz.table)).then(function(j){return j.items||[];})
    ]).then(function(res){
      if(!wz||wz.step!==2) return;
      wz.tfields=res[0]; wz.cols=res[1];
      wzRender();
    }).catch(function(e){
      if(!wz||wz.step!==2) return;
      b.innerHTML='<div class="empty">加载失败：'+escHtml(e.message)+'</div>';
    });
    return;
  }
  if(!wz.tfields.length){
    b.innerHTML='<div class="empty">该模板无固定字段（透传），不能入库。'+
      '请关闭向导，用有固定字段的模板重新提取。</div>';
    return;
  }
  var html='<div class="wzrow"><label>写入方式</label><select id="wzwm">'+
    ['upsert','insert','update'].map(function(v){
      return '<option value="'+v+'"'+(v===wz.wm?' selected':'')+'>'+
        escHtml(modeLabel(v))+'</option>';}).join('')+'</select></div>'+
    '<div class="hint" id="wzmatch2"></div><div id="wzrows">';
  var colBy={};
  wz.cols.forEach(function(c){ var k=normKey(c.name);
    if(!(k in colBy)) colBy[k]=c.name; });
  wz.tfields.forEach(function(f){
    var hit=colBy[normKey(f)];
    html+='<div class="wzfr"><span class="wzfn">'+escHtml(f)+'</span>'+
      '<select class="wzfc"'+(hit?' data-auto="1"':'')+'>'+
      '<option value="">选择目标列</option>'+
      wz.cols.map(function(c){
        return '<option value="'+escHtml(c.name)+'"'+
          (c.name===hit?' selected':'')+'>'+escHtml(c.name)+
          '（'+escHtml(c.type)+'）</option>';}).join('')+
      '</select><span class="mbadge"></span>'+
      '<label class="bklab"><input type="checkbox" class="wzfbk">'+
      '去重依据</label></div>';
  });
  html+='</div><div class="hint">系统按名字自动对齐（忽略大小写/空格/下划线），'+
    '✓=已对齐可改，？=待你确认；去重依据请勾选业务上唯一的列（例如：发票号）。</div>';
  b.innerHTML=html;
  var wm=b.querySelector('#wzwm');
  function applyInsertMode(){
    Array.prototype.forEach.call(b.querySelectorAll('.wzfbk'),function(c){
      if(wm.value==='insert') c.checked=false;
      c.disabled=wm.value==='insert';
    });
  }
  wm.onchange=function(){ wz.wm=wm.value; applyInsertMode(); wzMatchBar(); };
  applyInsertMode();
  b.addEventListener('change',function(e){
    if(e.target&&e.target.classList.contains('wzfc')){
      e.target.removeAttribute('data-auto'); wzMatchBar();
    }
  });
  wzMatchBar();
}
function wzMatchBar(){
  if(!wz) return;
  var rows=document.querySelectorAll('#wzrows .wzfr'), M=rows.length, X=0, A=0;
  Array.prototype.forEach.call(rows,function(div){
    var sel=div.querySelector('.wzfc'), badge=div.querySelector('.mbadge');
    if(sel.value){ X++; if(sel.getAttribute('data-auto')==='1') A++; }
    badge.className='mbadge '+(sel.value?'ok':'warn');
    badge.textContent=sel.value?'✓':'？';
  });
  var bar=document.getElementById('wzmatch2');
  var K=M-X;
  bar.textContent=A?('已自动匹配 '+A+'/'+M+' 个字段'+(K?'，剩 '+K+' 个待确认':'，全部对上')):
    (K?('剩 '+K+'/'+M+' 个字段待确认'):(M+' 个字段已全部对齐'));
}
function wzCollect(){
  if(!wz.tfields||!wz.tfields.length){
    wzMsg('该模板无固定字段，不能入库',true); return false;
  }
  var rows=document.querySelectorAll('#wzrows .wzfr');
  var fields=[], seen={}, err=null;
  Array.prototype.forEach.call(rows,function(div){
    if(err) return;
    var f=div.querySelector('.wzfn').textContent;
    var c=div.querySelector('.wzfc').value;
    if(!c){ err='字段「'+f+'」还没对上目标列'; return; }
    if(seen[c]){ err='多个字段指向同一目标列：'+c; return; }
    seen[c]=1;
    fields.push({template_field:f,target_column:c,
      is_business_key:div.querySelector('.wzfbk').checked?1:0});
  });
  if(err){ wzMsg(err,true); return false; }
  if(wz.wm!=='insert'&&!fields.some(function(f){return f.is_business_key;})){
    wzMsg('「'+modeLabel(wz.wm)+'」须至少勾选一个去重依据',true); return false;
  }
  wz.fields=fields;
  return true;
}
/* ---- step3 过目（样例＋dry-run） ---- */
function wzSummary(){
  var bkCols=[];
  if(wz.fields) wz.fields.forEach(function(f){ if(f.is_business_key) bkCols.push(f.target_column); });
  var wm=wz.mode==='exist'?(wzRule()||{}).write_mode:wz.wm;
  var rows=[['业务库',wz.mode==='exist'?(wzDsName((wzRule()||{}).datasource_id)):wzDsName(wz.dsId)],
            ['目标表',wz.table],
            ['写入方式',modeLabel(wm||'')],
            ['去重依据',wz.mode==='exist'?'（在规则里配好）':(bkCols.join('、')||'—')]];
  return '<div class="wzsum">'+rows.map(function(r){
    return '<div class="wzsr"><span>'+escHtml(r[0])+'</span><b>'+escHtml(r[1]||'—')+'</b></div>';
  }).join('')+'</div>';
}
function wzDsName(id){
  var hit='';
  (wz.dsList||[]).forEach(function(d){ if(String(d.id)===String(id)) hit=d.name; });
  return hit||('业务库 #'+id);
}
function wzStep3(b){
  wz.previewErr='';
  b.innerHTML=wzSummary()+
    '<div class="wzsec">将发生什么</div>'+
    '<div class="wzcnt" id="wzcnt"><span class="wzb">计数计算中…</span></div>'+
    '<div class="wzsec">记录样例（前 3 条）</div>'+
    '<div id="wzsamp"><div class="empty">加载样例…</div></div>';
  wzFooter();
  var body=wz.mode==='exist'?{load_table_id:Number(wz.rule1)}:
    {draft:{datasource_id:wz.dsId,target_table:wz.table,
            write_mode:wz.wm,fields:wz.fields}};
  wzApi('POST','/api/tasks/'+wz.taskId+'/load-preview',body).then(function(j){
    if(!wz||wz.step!==3) return;
    document.getElementById('wzcnt').innerHTML=
      '<span class="wzb ok">总 '+j.total+'</span>'+
      '<span class="wzb">新增 '+j.insert+'</span>'+
      '<span class="wzb">覆盖 '+j.update+'</span>'+
      '<span class="wzb">跳过（已有回执） '+j.skip+'</span>'+
      '<span class="wzb'+(j.quarantine?' warn':'')+'">隔离 '+j.quarantine+'</span>';
  }).catch(function(e){
    if(!wz||wz.step!==3) return;
    wz.previewErr=e.message;
    document.getElementById('wzcnt').innerHTML=
      '<span class="wzb warn">检查未通过：'+escHtml(e.message)+'</span>';
    wzFooter();
  });
  var sp=wz.getSample?wz.getSample():
    wzApi('GET','/api/tasks/'+wz.taskId+'/staging').then(function(d){
      var out=[];
      (d.files||[]).forEach(function(f){
        (f.records||[]).forEach(function(r){ if(out.length<3) out.push(r); });});
      return out;
    });
  Promise.resolve(sp).then(function(recs){
    if(!wz||wz.step!==3) return;
    var el=document.getElementById('wzsamp');
    recs=(recs||[]).slice(0,3);
    if(!recs.length){ el.innerHTML='<div class="empty">没有可显示的记录</div>'; return; }
    var ks=wz.tfields&&wz.tfields.length?wz.tfields:
      Object.keys(recs[0].values||{});
    el.innerHTML='<table class="wzsample"><thead><tr><th>#</th>'+
      ks.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+
      '</tr></thead><tbody>'+recs.map(function(r,i){
        return '<tr><td>'+((r.index==null?i:r.index)+1)+'</td>'+
          ks.map(function(k){
            var v=(r.values||{})[k];
            return '<td title="'+escHtml(v)+'">'+escHtml(v==null?'':String(v))+'</td>';
          }).join('')+'</tr>';
      }).join('')+'</tbody></table>';
  }).catch(function(){
    if(!wz||wz.step!==3) return;
    document.getElementById('wzsamp').innerHTML='<div class="empty">样例加载失败</div>';
  });
}
/* ---- step4 执行（唯一落库点；失败补偿删除新建规则） ---- */
function wzExecute(){
  wz.busy=true; wz.step=4; wzRender(); wzMsg('提交中…');
  var p=Promise.resolve();
  if(wz.mode==='new'){
    p=wzApi('POST','/api/load/tables',{
      datasource_id:wz.dsId, template_id:wz.templateId,
      target_table:wz.table, write_mode:wz.wm, fields:wz.fields
    }).then(function(j){ wz.createdRule=j.id; });
  }
  p.then(function(){
    var r=wz.mode==='exist'?wzRule():null;
    return wzApi('POST','/api/tasks/'+wz.taskId+'/load',{
      load_datasource_id:r?r.datasource_id:wz.dsId,
      load_table_id:r?Number(r.id):wz.createdRule
    });
  }).then(function(){
    var done=wz&&wz.onDone;
    closeLoadWizard();
    if(done) done();
  }).catch(function(e){
    if(!wz) return;
    var comp=Promise.resolve(), recycled=false;
    if(wz.createdRule){
      var id=wz.createdRule; wz.createdRule=null; recycled=true;
      comp=wzApi('DELETE','/api/load/tables/'+id).catch(function(){});
    }
    comp.then(function(){
      if(!wz) return;
      wz.busy=false; wz.step=3; wzRender();
      wzMsg('入库失败：'+e.message+
        (recycled?'（新建的规则已回收，未写入业务库）':'')+'，可返回调整后重试',true);
    });
  });
}
