/* web/wizard.js — 单抽取结果四步入库向导：目标表配置 → 字段映射 → 预检 → 显式确认。
   规则与结果快照不拥有目标表；目标表可复用，映射绑定到 extract_result_id。
   预检前只保存待确认绑定；只有第 4 步用户确认后才确认 binding 并调用 /load。 */
var wz=null;
var wzTraceColumns={file_id:true,record_id:true};
function wzReserved(name){return Object.prototype.hasOwnProperty.call(wzTraceColumns,String(name||'').toLowerCase());}
function wzBindingMap(binding){
  var raw=binding&&(binding.field_map_json||binding.field_map)||{},out={};
  Object.keys(raw).forEach(function(k){if(!wzReserved(raw[k]))out[k]=raw[k];});return out;
}
function wzBindingKeys(binding){
  var map=wzBindingMap(binding),used={};
  Object.keys(map).forEach(function(k){used[map[k]]=true;});
  return ((binding&&(binding.business_keys_json||binding.business_keys))||[]).filter(function(k){return used[k]&&!wzReserved(k);});
}
function wzApi(method,url,body){
  var opt={method:method,headers:{}};
  if(body!==undefined){
    opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(body);
  }
  return fetch(url,opt).then(function(r){
    return r.json().catch(function(){return {};}).then(function(j){
      if(!r.ok||j.ok===false)throw new Error(j.error||j.message||('HTTP '+r.status));
      return j;
    });
  });
}
function wzMsg(t,bad){
  var e=document.getElementById('wzmsg');if(!e)return;
  e.textContent=t||'';e.className=bad?'msg err':'msg';
}
function wzUi(){
  var m=document.getElementById('wzmask');
  if(m)return m;
  m=document.createElement('div');m.className='wzmask';m.id='wzmask';
  m.innerHTML='<div class="wzpanel">'+
    '<div class="wzhead"><h2 id="wztitle">入库向导</h2><span class="spacer"></span>'+
    '<button type="button" class="dclose" id="wzclose">关闭 (Esc)</button></div>'+
    '<div class="wzsteps" id="wzsteps"></div><div class="wzbody" id="wzbody"></div>'+
    '<div class="wzfoot"><span class="msg" id="wzmsg"></span><span class="spacer"></span>'+
    '<button type="button" class="btn ghost" id="wzprev">上一步</button>'+
    '<button type="button" class="btn" id="wznext">下一步</button></div></div>';
  document.body.appendChild(m);
  document.getElementById('wzclose').onclick=closeLoadWizard;
  m.addEventListener('click',function(e){if(e.target===m)closeLoadWizard();});
  document.addEventListener('keydown',function(e){if(e.key==='Escape'&&wz&&!m.hidden)closeLoadWizard();});
  document.getElementById('wzprev').onclick=function(){if(wz&&!wz.busy)wzGo(wz.step-1);};
  document.getElementById('wznext').onclick=wzAdvance;
  return m;
}
function openLoadWizard(opts){
  if(!opts.extractResultId)throw new Error('缺少抽取结果 ID，不能入库');
  var binding=opts.result&&(opts.result.load_binding||opts.result.binding);
  wz={fileId:opts.fileId,resultId:Number(opts.extractResultId),result:opts.result||{},
    onDone:opts.onDone,gate:opts.gate||null,step:1,dsList:null,tables:null,
    dsId:binding?String(binding.datasource_id||''):'',dsCode:binding?String(binding.datasource_code||''):'',
    tableCode:binding?String(binding.table_code||''):'',
    newTable:'',fieldMap:wzBindingMap(binding),
    writeMode:binding&&binding.write_mode||'upsert',businessKeys:wzBindingKeys(binding),
    binding:binding||null,fields:[],cols:[],preview:null,previewErr:'',approvePending:false,busy:false};
  var m=wzUi();
  document.getElementById('wztitle').textContent='抽取结果 #'+wz.resultId+' · 入库向导';
  m.hidden=false;wzRender(true);
}
function closeLoadWizard(){var m=document.getElementById('wzmask');if(m)m.hidden=true;wz=null;}
function wzRender(first){
  if(!wz)return;
  document.getElementById('wzsteps').innerHTML=['① 选目标','② 字段对齐','③ 过目','④ 执行'].map(function(n,i){
    var s=i+1;return '<span class="wst'+(s===wz.step?' on':(s<wz.step?' done':''))+'">'+n+'</span>';
  }).join('');
  var prev=document.getElementById('wzprev'),next=document.getElementById('wznext');
  prev.hidden=wz.step<=1||wz.busy;
  next.textContent=wz.step===3?'确认并写入':'下一步';
  next.disabled=!!wz.busy||wz.step===4||(wz.step===3&&!!wz.previewErr);
  if(!first)wzMsg('');
  var b=document.getElementById('wzbody');
  if(wz.step===1)wzStep1(b);else if(wz.step===2)wzStep2(b);else if(wz.step===3)wzStep3(b);
  else b.innerHTML='<div class="empty">正在确认绑定并写入所选结果…</div>';
}
function wzGo(step){if(!wz)return;wz.step=step;wz.preview=null;wz.previewErr='';wzRender();}
function wzDsOpt(d){return '<option value="'+d.id+'">'+escHtml(d.name+' · '+d.code+' · '+d.host+'/'+d.db_name)+'</option>';}
function wzStep1(b){
  if(!wz.dsList){
    b.innerHTML='<div class="empty">加载业务库与目标表配置…</div>';
    Promise.all([wzApi('GET','/api/load/datasources'),wzApi('GET','/api/load/tables')]).then(function(res){
      if(!wz||wz.step!==1)return;wz.dsList=res[0].items||[];wz.tables=res[1].items||[];wzRender();
    }).catch(function(e){if(wz&&wz.step===1)b.innerHTML='<div class="empty">读取失败：'+escHtml(e.message)+'</div>';});
    return;
  }
  b.innerHTML='<div class="wzsec">选择此结果的目标表</div>'+
    '<p class="hint">目标表配置只描述业务库、物理表与列，可被多个结果复用；本结果的映射在下一步独立维护。</p>'+
    '<div class="wzrow"><label>业务库</label><select id="wzds"><option value="">选择业务库</option>'+wz.dsList.map(wzDsOpt).join('')+'</select></div>'+
    '<div class="wzrow"><label>已有表配置</label><select id="wztable"><option value="">选择已配置目标表</option></select></div>'+
    '<div class="wzrow"><label>或物理表名</label><input class="tin" id="wznewtable" placeholder="已有业务表名；保存绑定时登记列元数据"></div>'+
    '<div class="hint">新业务库请在 <a href="/rules" target="_blank">业务库与目标表</a> 页维护。这里不会创建或删除物理表。</div>';
  var ds=b.querySelector('#wzds'),tb=b.querySelector('#wztable'),nt=b.querySelector('#wznewtable');
  function selectedDs(){return (wz.dsList||[]).filter(function(d){return String(d.id)===ds.value;})[0]||null;}
  function fillTables(){
    var d=selectedDs(),code=d?d.code:'';
    var list=wz.tables.filter(function(t){return String(t.datasource_code)===String(code);});
    tb.innerHTML='<option value="">选择已配置目标表</option>'+list.map(function(t){
      return '<option value="'+escHtml(t.code)+'">'+escHtml(t.code||t.target_table)+'</option>';
    }).join('');
    if(wz.tableCode&&list.some(function(t){return t.code===wz.tableCode;}))tb.value=wz.tableCode;
  }
  ds.value=wz.dsId;nt.value=wz.newTable;fillTables();
  ds.onchange=function(){wz.dsId=ds.value;var d=selectedDs();wz.dsCode=d?d.code:'';wz.tableCode='';wz.newTable='';nt.value='';fillTables();};
  tb.onchange=function(){wz.tableCode=tb.value;wz.newTable='';nt.value='';};
  nt.oninput=function(){wz.newTable=nt.value.trim();if(wz.newTable)tb.value='';};
  if(wz.dsId)fillTables();
}
function wzSelectedTable(){
  var ds=(wz.dsList||[]).filter(function(d){return String(d.id)===String(wz.dsId);})[0]||null;
  var datasourceCode=wz.dsCode||(ds&&ds.code)||'';
  var t=(wz.tables||[]).filter(function(x){return x.code===wz.tableCode;})[0]||null;
  return t?{id:t.id,datasource_id:t.datasource_id,datasource_code:t.datasource_code,target_table:t.target_table,table_code:t.code}:
    {id:null,datasource_id:Number(wz.dsId),datasource_code:datasourceCode,target_table:wz.newTable,
      table_code:datasourceCode?datasourceCode+'.'+wz.newTable:''};
}
function wzSaveBinding(){
  var chain=Promise.resolve();
  if(!wz.target.id){
    chain=chain.then(function(){
      return wzApi('POST','/api/load/tables',{datasource_code:wz.target.datasource_code,target_table:wz.target.target_table,
        fields:wz.cols.map(function(c,i){return {field_name:c.name,data_type:c.type||c.data_type||'text',is_primary:!!(c.primary||c.is_primary),has_default:c.default!=null,sort_order:c.sort_order==null?i:c.sort_order};})});
    }).then(function(j){if(!j.id)throw new Error('目标表配置保存失败');wz.target.id=j.id;});
  }
  return chain.then(function(){
    var body={extract_result_id:wz.resultId,table_code:wz.target.table_code,field_map:wz.fieldMap,write_mode:wz.writeMode,business_keys:wz.businessKeys};
    var request=wz.binding&&wz.binding.id?wzApi('PATCH','/api/load/bindings/'+wz.binding.id,body):wzApi('POST','/api/load/bindings',body);
    return request.then(function(j){
      var id=wz.binding&&wz.binding.id?wz.binding.id:(j.id||j.load_binding_id);
      if(!id)throw new Error('入库绑定保存失败');
      wz.binding=Object.assign({},wz.binding,body,{id:id,status:'pending'});
    });
  });
}
function wzAdvance(){
  if(!wz||wz.busy)return;
  if(wz.step===1){
    var target=wzSelectedTable();
    if(!target.datasource_code||!target.target_table){wzMsg('请选择业务库与目标表',true);return;}
    wz.target=target;
    wz.fields=[];wz.cols=[];wzGo(2);return;
  }
  if(wz.step===2){
    if(!wzCollect())return;
    wz.busy=true;document.getElementById('wznext').disabled=true;wzMsg('正在保存待确认绑定…');
    wzSaveBinding().then(function(){if(!wz)return;wz.busy=false;wzGo(3);})
      .catch(function(e){if(!wz)return;wz.busy=false;document.getElementById('wznext').disabled=false;wzMsg(e.message,true);});
    return;
  }
  if(wz.step===3)wzExecute();
}
function wzStep2(b){
  if(!wz.fields.length){
    b.innerHTML='<div class="empty">加载结果字段与目标列…</div>';
    var intent={datasource_id:wz.target.datasource_id,datasource_code:wz.target.datasource_code,
      table_code:wz.target.table_code,target_table:wz.target.target_table,
      field_map:wz.fieldMap,write_mode:wz.writeMode,business_keys:wz.businessKeys};
    wzApi('POST','/api/extract-results/'+wz.resultId+'/load-plan',{intent:intent}).then(function(plan){
      if(!wz||wz.step!==2)return;
      var mapping=plan.mapping;
      if(!mapping)throw new Error(plan.message||'无法规划该结果的目标表与字段');
      var names=(mapping.fields||[]).map(function(f){return f.name;}).filter(function(n){return n&&!wzReserved(n);});
      if(!names.length)throw new Error('该结果没有可映射的抽取字段');
      wz.fields=names.filter(function(n,i){return names.indexOf(n)===i;});
      wz.cols=(mapping.available_columns||[]).filter(function(c){return !!c.name;});
      if(!wz.cols.some(function(c){return !wzReserved(c.name);}))throw new Error('目标表没有可映射的业务列');
      wzRender();
    }).catch(function(e){if(wz&&wz.step===2)b.innerHTML='<div class="empty">加载失败：'+escHtml(e.message)+'</div>';});
    return;
  }
  var html='<div class="wzrow"><label>写入方式</label><select id="wzwm">'+
    ['upsert','insert','update'].map(function(v){return '<option value="'+v+'"'+(v===wz.writeMode?' selected':'')+'>'+escHtml(modeLabel(v))+'</option>';}).join('')+'</select></div>'+
    '<div class="hint" id="wzmatch2"></div><div id="wzrows">';
  var cols=wz.cols.filter(function(c){return !wzReserved(c.name);});
  var colBy={};cols.forEach(function(c){var k=normKey(c.name);if(!(k in colBy))colBy[k]=c.name;});
  wz.fields.forEach(function(f){
    var hit=wz.fieldMap[f]||colBy[normKey(f)]||'';
    html+='<div class="wzfr"><span class="wzfn">'+escHtml(f)+'</span>'+
      '<select class="wzfc"><option value="">选择目标列</option>'+cols.map(function(c){
        return '<option value="'+escHtml(c.name)+'"'+(c.name===hit?' selected':'')+'>'+escHtml(c.name)+'（'+escHtml(c.type||c.data_type||'')+'）</option>';
      }).join('')+'</select><span class="mbadge"></span>'+
      '<label class="bklab"><input type="checkbox" class="wzfbk"'+(wz.businessKeys.indexOf(hit)>=0?' checked':'')+'>去重依据</label></div>';
  });
  html+='</div><div class="hint">至少映射一个字段，其余可留空；同一目标列不能重复使用。file_id / record_id 由平台写入，不可映射。update / upsert 必须选择去重依据列。</div>';
  b.innerHTML=html;
  var wm=b.querySelector('#wzwm');
  function syncKeys(){Array.prototype.forEach.call(b.querySelectorAll('.wzfbk'),function(c){c.disabled=wm.value==='insert';if(c.disabled)c.checked=false;});}
  wm.value=wz.writeMode;wm.onchange=function(){wz.writeMode=wm.value;syncKeys();};syncKeys();
  b.addEventListener('change',function(e){
    if(e.target.classList.contains('wzfc')||e.target.classList.contains('wzfbk'))wzMatchBar();
  });wzMatchBar();
}
function wzMatchBar(){
  var rows=document.querySelectorAll('#wzrows .wzfr'),mapped=0;
  Array.prototype.forEach.call(rows,function(div){var ok=!!div.querySelector('.wzfc').value;if(ok)mapped++;var badge=div.querySelector('.mbadge');badge.className='mbadge '+(ok?'ok':'warn');badge.textContent=ok?'✓':'？';});
  var bar=document.getElementById('wzmatch2');if(bar)bar.textContent='已映射 '+mapped+'/'+rows.length+' 个字段';
}
function wzCollect(){
  var rows=document.querySelectorAll('#wzrows .wzfr'),map={},seen={},keys=[],err='';
  Array.prototype.forEach.call(rows,function(div){
    var field=div.querySelector('.wzfn').textContent,col=div.querySelector('.wzfc').value;
    if(col){if(seen[col])err='多个字段指向同一目标列：'+col;seen[col]=1;map[field]=col;if(div.querySelector('.wzfbk').checked)keys.push(col);}
  });
  if(!Object.keys(map).length)err='至少选择一个字段映射';
  if(!err&&wz.writeMode!=='insert'&&!keys.length)err=modeLabel(wz.writeMode)+'须至少勾选一个去重依据';
  if(err){wzMsg(err,true);return false;}
  wz.fieldMap=map;wz.businessKeys=keys;return true;
}
function wzSummary(){
  var rows=[['抽取结果','#'+wz.resultId],['业务库',wzDsName(wz.target.datasource_id)+' · '+wz.target.datasource_code],
    ['目标表',wz.target.target_table+' · '+wz.target.table_code],['写入方式',modeLabel(wz.writeMode)],['去重依据',wz.businessKeys.join('、')||'—']];
  return '<div class="wzsum">'+rows.map(function(r){return '<div class="wzsr"><span>'+escHtml(r[0])+'</span><b>'+escHtml(r[1])+'</b></div>';}).join('')+'</div>';
}
function wzDsName(id){var hit='';(wz.dsList||[]).forEach(function(d){if(String(d.id)===String(id))hit=d.name;});return hit||('业务库 #'+id);}
function wzStep3(b){
  wz.previewErr='';
  var pending=wz.gate?Number(wz.gate.pending||0)+Number(wz.gate.edited||0):0;
  var rejected=wz.gate?Number(wz.gate.rejected||0):0;
  b.innerHTML=wzSummary()+'<div class="wzsec">将发生什么</div>'+
    '<div class="wzcnt" id="wzcnt"><span class="wzb">正在只读预检…</span></div>'+
    (pending?'<div class="banner warn">当前结果有 '+pending+' 条待审 / 已修改记录。不会自动通过；只有勾选下方选项并最终确认后才会执行确认。</div>':'')+
    (rejected?'<div class="banner err">当前结果有 '+rejected+' 条已拒绝记录，请返回预览页处理后再入库。</div>':'')+
    (pending?'<label><input type="checkbox" id="wzapprove"> 我显式确认将当前结果 '+pending+' 条待审 / 已修改记录设为通过</label>':'')+
    '<div class="wzsec">记录样例（前 3 条）</div><div id="wzsamp"><div class="empty">加载样例…</div></div>';
  var approve=b.querySelector('#wzapprove');if(approve)approve.onchange=function(){wz.approvePending=approve.checked;};
  wzApi('POST','/api/extract-results/'+wz.resultId+'/load-preview',{}).then(function(j){
    if(!wz||wz.step!==3)return;wz.preview=j;
    document.getElementById('wzcnt').innerHTML='<span class="wzb ok">总 '+escHtml(j.total||0)+'</span>'+
      '<span class="wzb">新增 '+escHtml(j.insert||0)+'</span><span class="wzb">覆盖 '+escHtml(j.update||0)+'</span>'+
      '<span class="wzb">跳过 '+escHtml(j.skip||0)+'</span><span class="wzb'+(j.quarantine?' warn':'')+'">隔离 '+escHtml(j.quarantine||0)+'</span>';
  }).catch(function(e){if(!wz||wz.step!==3)return;wz.previewErr=e.message;document.getElementById('wzcnt').innerHTML='<span class="wzb warn">检查未通过：'+escHtml(e.message)+'</span>';document.getElementById('wznext').disabled=true;});
  wzApi('GET','/api/extract-results/'+wz.resultId+'/staging').then(function(d){
    if(!wz||wz.step!==3)return;var recs=[],first=((d.files||[])[0]||{}).records||[];
    first.forEach(function(r){if(recs.length<3)recs.push(r);});
    var el=document.getElementById('wzsamp');if(!recs.length){el.innerHTML='<div class="empty">没有可显示的记录</div>';return;}
    el.innerHTML='<table class="wzsample"><thead><tr><th>#</th>'+wz.fields.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+'</tr></thead><tbody>'+
      recs.map(function(r,i){return '<tr><td>'+((r.index==null?i:r.index)+1)+'</td>'+wz.fields.map(function(k){var v=(r.values||{})[k];return '<td>'+escHtml(v==null?'':v)+'</td>';}).join('')+'</tr>';}).join('')+'</tbody></table>';
  }).catch(function(){});
}
/* 唯一写入点：先显式确认（可选逐条审批），再确认 binding，最后启动单结果入库。 */
function wzExecute(){
  var pending=wz.gate?Number(wz.gate.pending||0)+Number(wz.gate.edited||0):0;
  var rejected=wz.gate?Number(wz.gate.rejected||0):0;
  if(rejected){wzMsg('存在已拒绝记录，不能入库',true);return;}
  if(pending&&!wz.approvePending){wzMsg('请显式勾选待审记录审批选项',true);return;}
  if(!wz.preview||wz.previewErr){wzMsg('预检尚未通过',true);return;}
  if(!window.confirm('仅将抽取结果 #'+wz.resultId+' 写入 '+wz.target.target_table+'？\n写入方式：'+modeLabel(wz.writeMode)+'。此操作会修改业务数据库，其他结果不受影响。'))return;
  wz.busy=true;wz.step=4;wzRender();wzMsg('正在提交…');
  var chain=Promise.resolve();
  if(pending)chain=chain.then(function(){return wzApi('POST','/api/extract-results/'+wz.resultId+'/approve-all',{}).then(function(){if(wz.gate){wz.gate.pending=0;wz.gate.edited=0;}});});
  chain=chain.then(function(){
    if(wz.binding&&wz.binding.status==='confirmed')return;
    var body={table_code:wz.target.table_code,field_map:wz.fieldMap,write_mode:wz.writeMode,business_keys:wz.businessKeys};
    return wzApi('PATCH','/api/load/bindings/'+wz.binding.id,body);
  }).then(function(){
    if(wz.binding&&wz.binding.status==='confirmed')return;
    return wzApi('PATCH','/api/load/bindings/'+wz.binding.id,{confirmed:true}).then(function(){wz.binding.status='confirmed';});
  }).then(function(){return wzApi('POST','/api/extract-results/'+wz.resultId+'/load',{});})
    .then(function(){var done=wz&&wz.onDone;closeLoadWizard();if(done)done();})
    .catch(function(e){
      if(!wz)return;wz.busy=false;wz.step=3;wzRender();wzMsg('入库未完成：'+e.message+'。请检查预检、绑定状态与回执后重试。',true);
    });
}
