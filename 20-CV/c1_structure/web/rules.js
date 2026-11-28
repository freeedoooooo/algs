/* web/rules.js — 业务库、可复用目标表配置、逐抽取结果独立绑定。
   规则是单行抽取定义，不拥有目标表或字段映射；确认与业务写入在结果入库向导中完成。 */
var dss=[],maps=[],bindings=[],results=[],cols=[];
var curDs=null,editDs=null,editLt=null,ltLocked=false;
var editBinding=null,bindingLocked=false,bindingResult=null,resultsLoaded=false,resultsLoading=false;
var mapPage=1,mapSize=getListPer(),bindingPage=1,bindingSize=getListPer();
var pgMap=bindPager(document.getElementById('mappager'),function(d){mapPage+=d;renderMaps();},function(n){mapSize=n;mapPage=1;renderMaps();});
var pgBinding=bindPager(document.getElementById('bindingpager'),function(d){bindingPage+=d;renderBindings();},function(n){bindingSize=n;bindingPage=1;renderBindings();});
var dds=document.getElementById('dds'),dmap=document.getElementById('dmap'),bdrawer=document.getElementById('bdrawer');
function api(method,url,body){
  var opt={method:method,headers:{}};
  if(body!==undefined){opt.headers['Content-Type']='application/json';opt.body=JSON.stringify(body);}
  return fetch(url,opt).then(function(r){return r.json().catch(function(){return {};}).then(function(j){
    if(!r.ok||j.ok===false)throw new Error(j.error||j.message||('HTTP '+r.status));return j;
  });});
}
function showOk(msg){var b=document.getElementById('ok');b.textContent=msg;b.hidden=false;document.getElementById('err').hidden=true;}
function showErr(msg){var b=document.getElementById('err');b.textContent=msg;b.hidden=false;}
function dsById(id){return dss.filter(function(d){return d.id===id;})[0]||null;}
function ltById(id){return maps.filter(function(t){return t.id===id;})[0]||null;}
function bindingById(id){return bindings.filter(function(b){return b.id===id;})[0]||null;}
function fieldMapOf(b){return b&&(b.field_map_json||b.field_map)||{};}
function businessKeysOf(b){return b&&(b.business_keys_json||b.business_keys)||[];}

function renderDs(){
  document.getElementById('dslist').innerHTML=dss.map(function(d,i){
    return '<div class="dsitem'+(d.id===curDs?' active':'')+'" data-ds="'+d.id+'">'+
      '<div class="dsmain"><b>'+(i+1)+'. '+escHtml(d.name)+'</b><span class="badge">'+d.table_count+' 业务表</span></div>'+
      '<div class="dsmeta mono">'+escHtml('ID '+d.id+' · '+d.code+' · '+d.host+':'+d.port+'/'+d.db_name)+'</div>'+
      '<div class="dsops"><button type="button" class="linkbtn" data-test="'+d.id+'">测试</button>'+
      '<button type="button" class="linkbtn" data-editds="'+d.id+'">编辑</button>'+
      '<button type="button" class="linkbtn danger" data-delds="'+d.id+'" data-name="'+escHtml(d.name)+'">删除</button></div></div>';
  }).join('');document.getElementById('dsempty').hidden=dss.length>0;
}
function renderMaps(){
  var d=dsById(curDs);document.getElementById('maptitle').textContent='业务表';
  document.getElementById('newmap').disabled=!d;document.getElementById('newbinding').disabled=!d;
  var d=dsById(curDs),list=d?maps.filter(function(m){return m.datasource_code===d.code;}):[],info=pageSlice(list,mapPage,mapSize);mapPage=info.page;
  document.getElementById('mapnone').hidden=!!d;document.getElementById('maptable').hidden=!d||!list.length;
  document.getElementById('mapempty').hidden=!d||list.length>0;
  document.getElementById('maprows').innerHTML=info.rows.map(function(m,i){
    return '<tr><td class="seq">'+seqNo(info,i)+'</td><td class="mono">'+m.id+'</td>'+
      '<td class="left"><a class="linkbtn" href="/dashboard?ds='+encodeURIComponent(m.datasource_id)+'&table='+encodeURIComponent(m.target_table)+'">'+escHtml(m.target_table)+'</a></td>'+
      '<td class="left mono">'+escHtml(m.code)+'</td>'+
      '<td class="num">'+(m.fields||[]).length+'</td><td class="num">'+bindings.filter(function(b){return b.table_code===m.code;}).length+'</td>'+
      '<td style="white-space:nowrap"><button type="button" class="linkbtn" data-editmap="'+m.id+'">编辑元数据</button>'+
      '<button type="button" class="linkbtn danger" data-delmap="'+m.id+'" data-name="'+escHtml(m.target_table)+'">删除</button></td></tr>';
  }).join('');pgMap.render(info);
}
function renderBindings(){
  var d=dsById(curDs),list=d?bindings.filter(function(b){return b.datasource_code===d.code;}):[],info=pageSlice(list,bindingPage,bindingSize);bindingPage=info.page;
  document.getElementById('bindingtable').hidden=!curDs||!list.length;
  document.getElementById('bindingempty').hidden=!curDs||list.length>0;
  document.getElementById('bindingrows').innerHTML=info.rows.map(function(b){
    var locked=['confirmed','running','ready'].indexOf(b.status)>=0;
    return '<tr><td class="mono">'+b.id+'</td><td>#'+escHtml(b.extract_result_id)+' · '+escHtml(b.rule_name||'规则 #'+b.rule_id)+'</td>'+
      '<td>'+escHtml(b.target_table)+'</td><td class="left mono">'+escHtml(b.table_code||'')+'</td><td>'+escHtml(modeLabel(b.write_mode))+'</td>'+
      '<td class="left mono">'+escHtml(businessKeysOf(b).join(', ')||'—')+'</td><td>'+escHtml(b.status)+'</td>'+
      '<td><button type="button" class="linkbtn" data-editbinding="'+b.id+'"'+(locked?' disabled title="已确认或已入库，不可修改"':'')+'>编辑</button> '+
      '<a class="linkbtn" href="/preview?file='+encodeURIComponent(b.doc_id)+'&amp;result='+encodeURIComponent(b.extract_result_id)+'">结果</a></td></tr>';
  }).join('');pgBinding.render(info);
}
function loadAll(keepSel){
  return Promise.all([
    api('GET','/api/load/datasources'),api('GET','/api/load/tables'),
    api('GET','/api/load/bindings')]).then(function(res){
      dss=res[0].items||[];maps=res[1].items||[];bindings=res[2].items||[];
      if(!keepSel||!dsById(curDs))curDs=dss.length?dss[0].id:null;
      renderDs();renderMaps();renderBindings();document.getElementById('err').hidden=true;
    }).catch(function(e){dss=[];maps=[];bindings=[];results=[];curDs=null;renderDs();renderMaps();renderBindings();showErr('平台库未连接：入库配置暂不可用（'+e.message+'）');});
}
function renderBindingResults(){
  var resultSel=document.getElementById('bdresult');
  resultSel.innerHTML='<option value="">选择已完成的抽取结果</option>'+results.filter(function(r){return r.status==='ready';}).map(function(r){
    return '<option value="'+r.id+'">资料 #'+r.doc_id+' · 结果 #'+r.id+' · '+escHtml(r.rule_name||'规则 #'+r.rule_id)+'</option>';
  }).join('');
  resultSel.disabled=bindingLocked||!!editBinding;
}
function loadBindingResults(){
  if(resultsLoaded)return Promise.resolve();
  if(resultsLoading)return resultsLoading;
  var resultSel=document.getElementById('bdresult');
  resultSel.innerHTML='<option value="">正在加载抽取结果…</option>';resultSel.disabled=true;results=[];
  resultsLoading=api('GET','/api/sources?size=100').then(function(sourceResult){
    var files=sourceResult.items||[];
    return Promise.all(files.map(function(f){
      return api('GET','/api/sources/'+f.id).then(function(detail){
        var file=detail.file||detail;
        (file.results||file.extract_results||[]).forEach(function(r){results.push(Object.assign({},r,{doc_id:f.id,doc_name:f.name}));});
      });
    }));
  }).then(function(){resultsLoaded=true;renderBindingResults();}).catch(function(e){
    resultSel.innerHTML='<option value="">加载失败，请关闭后重试</option>';
    document.getElementById('bdmsg').textContent=e.message;
  }).then(function(){resultsLoading=false;});
  return resultsLoading;
}

/* 业务库 CRUD */
document.getElementById('dslist').addEventListener('click',function(e){
  var t=e.target,test=t.closest?t.closest('[data-test]'):null;
  if(test){var tid=test.getAttribute('data-test');test.disabled=true;api('POST','/api/load/datasources/'+tid+'/test').then(function(j){showOk('连接成功：'+j.detail);}).catch(function(err){showErr('连接失败：'+err.message);}).then(function(){test.disabled=false;});return;}
  var ed=t.closest?t.closest('[data-editds]'):null;if(ed){openDs(dsById(Number(ed.getAttribute('data-editds'))));return;}
  var del=t.closest?t.closest('[data-delds]'):null;
  if(del){var did=del.getAttribute('data-delds'),name=del.getAttribute('data-name');if(!confirm('删除业务库「'+name+'」？已被目标表引用时后端会拒绝。'))return;api('DELETE','/api/load/datasources/'+did).then(function(){showOk('已删除业务库。');loadAll(true);}).catch(function(err){showErr(err.message);});return;}
  var item=t.closest?t.closest('[data-ds]'):null;if(item){curDs=Number(item.getAttribute('data-ds'));mapPage=1;bindingPage=1;renderDs();renderMaps();renderBindings();}
});
var DS_FIELDS=['dsname','dscode','dshost','dsport','dsuser','dspass','dsdb'];
function openDs(d){
  editDs=d||null;document.getElementById('dstitle').textContent=d?'编辑业务库':'新建业务库';
  document.getElementById('dsname').value=d?d.name:'';document.getElementById('dscode').value=d?d.code:'';
  document.getElementById('dshost').value=d?d.host:'';
  document.getElementById('dsport').value=d?d.port:'3306';document.getElementById('dsuser').value=d?d.user:'';
  document.getElementById('dspass').value=d?d.password:'';document.getElementById('dsdb').value=d?d.db_name:'';
  var locked=!!(d&&d.table_count>0);['dscode','dshost','dsport','dsdb'].forEach(function(id){document.getElementById(id).disabled=locked;});
  document.getElementById('dslock').hidden=!locked;dsmsg.textContent='';dds.hidden=false;
}
function closeDs(){dds.hidden=true;}
document.getElementById('newds').onclick=function(){openDs(null);};document.getElementById('dsclose').onclick=closeDs;
dds.addEventListener('click',function(e){if(e.target===dds)closeDs();});
document.getElementById('dssave').onclick=function(){
  dsmsg.textContent='';var v={};DS_FIELDS.forEach(function(id){v[id]=document.getElementById(id).value.trim();});
  if(!v.dsname){dsmsg.textContent='名称不能为空';return;}if(!editDs&&(!v.dshost||!v.dsdb)){dsmsg.textContent='主机与库名不能为空';return;}
  var body={name:v.dsname,user:v.dsuser,password:v.dspass};if(!editDs||!editDs.table_count){body.host=v.dshost;body.port=v.dsport;body.db_name=v.dsdb;if(v.dscode)body.code=v.dscode;}
  (editDs?api('PATCH','/api/load/datasources/'+editDs.id,body):api('POST','/api/load/datasources',body)).then(function(){closeDs();showOk('已保存业务库。');return loadAll(true);}).catch(function(e){dsmsg.textContent=e.message;});
};

/* 目标表配置：只维护物理目标元数据，不保存规则、写入方式或字段映射。 */
function loadTables(){
  mptable.disabled=true;mptable.innerHTML='<option value="">加载中…</option>';document.getElementById('mpthint').textContent='';
  api('GET','/api/load/datasources/'+curDs+'/tables').then(function(j){var ts=j.items||[];mptable.innerHTML='<option value="">选择目标表</option>'+ts.map(function(t){return '<option value="'+escHtml(t)+'">'+escHtml(t)+'</option>';}).join('');mptable.disabled=ltLocked;document.getElementById('mpthint').textContent='共 '+ts.length+' 张已有物理表；仅读取表结构。';}).catch(function(e){mptable.innerHTML='<option value="">加载失败</option>';document.getElementById('mpthint').textContent=e.message;});
}
function loadTableMeta(table,after){
  api('GET','/api/load/datasources/'+curDs+'/columns?table='+encodeURIComponent(table)).then(function(j){cols=j.items||[];if(after)after();}).catch(function(e){document.getElementById('mpthint').textContent='目标列加载失败：'+e.message;});
}
function openMap(lt){
  editLt=lt||null;ltLocked=!!(lt&&(lt.binding_refs||[]).length);var d=dsById(curDs);
  document.getElementById('mptitle').textContent=lt?'编辑业务表':'登记业务表';
  document.getElementById('mpds').value=d?(d.name+' · '+d.code+' · '+d.host+':'+d.port+'/'+d.db_name):'';
  document.getElementById('mplock').hidden=!ltLocked;document.getElementById('mpsave').disabled=ltLocked;
  mpmsg.textContent='';cols=[];document.getElementById('mpmeta').innerHTML='';document.getElementById('mpthint').textContent='';
  if(lt){mptable.innerHTML='<option value="'+escHtml(lt.target_table)+'">'+escHtml(lt.target_table)+'</option>';mptable.disabled=true;loadTableMeta(lt.target_table,function(){renderTableMeta();});}
  else{mptable.innerHTML='<option value="">选择目标表</option>';loadTables();}
  dmap.hidden=false;
}
function renderTableMeta(){
  document.getElementById('mpmeta').innerHTML=cols.length?'<table class="list"><thead><tr><th>目标列</th><th>类型</th><th>主键</th><th>默认值</th></tr></thead><tbody>'+cols.map(function(c){return '<tr><td>'+escHtml(c.name)+'</td><td>'+escHtml(c.type||c.data_type||'')+'</td><td>'+(c.primary||c.is_primary?'是':'否')+'</td><td>'+escHtml(c.default==null?'—':c.default)+'</td></tr>';}).join('')+'</tbody></table>':'<div class="sthint">未读取到目标列。</div>';
}
function closeDmap(){dmap.hidden=true;}
document.getElementById('newmap').onclick=function(){if(curDs)openMap(null);};document.getElementById('mpclose').onclick=closeDmap;
dmap.addEventListener('click',function(e){if(e.target===dmap)closeDmap();});
mptable.onchange=function(){if(mptable.value){cols=[];document.getElementById('mpmeta').innerHTML='';loadTableMeta(mptable.value,renderTableMeta);}};
document.getElementById('mpsave').onclick=function(){
  if(ltLocked){mpmsg.textContent='该目标表已被结果绑定，不能修改';return;}if(!mptable.value){mpmsg.textContent='请选择目标表';return;}if(!cols.length){mpmsg.textContent='目标列尚未加载';return;}
  var fields=cols.map(function(c,i){return {field_name:c.name,data_type:c.type||c.data_type||'text',is_primary:!!(c.primary||c.is_primary),has_default:c.default!=null,sort_order:c.sort_order==null?i:c.sort_order};});
  (editLt?api('PATCH','/api/load/tables/'+editLt.id,{target_table:mptable.value,fields:fields}):api('POST','/api/load/tables',{datasource_code:dsById(curDs).code,target_table:mptable.value,fields:fields}))
    .then(function(){closeDmap();showOk('已保存业务表元数据；结果字段映射请在入库映射中维护。');return loadAll(true);}).catch(function(e){mpmsg.textContent=e.message;});
};
document.getElementById('maprows').addEventListener('click',function(e){
  var ed=e.target.closest?e.target.closest('[data-editmap]'):null;
  if(ed){api('GET','/api/load/tables/'+ed.getAttribute('data-editmap')).then(openMap).catch(showErr);return;}
  var del=e.target.closest?e.target.closest('[data-delmap]'):null;if(!del)return;
  if(!confirm('删除目标表配置「'+del.getAttribute('data-name')+'」？不会删除物理业务表；被绑定时后端会拒绝。'))return;
  api('DELETE','/api/load/tables/'+del.getAttribute('data-delmap')).then(function(){showOk('已删除目标表配置。');loadAll(true);}).catch(showErr);
});

/* 独立结果绑定：只保存映射，不在此页确认或执行入库。 */
function bindingCols(){return cols;}
function bindingRowsHtml(names){
  var by={};bindingCols().forEach(function(c){var k=normKey(c.name);if(!(k in by))by[k]=c.name;});
  document.getElementById('bdrows').innerHTML=names.map(function(name){
    var hit=bindingResult&&fieldMapOf(bindingResult.load_binding)[name]||by[normKey(name)]||'';
    return '<div class="frow"><input class="tin fname" readonly value="'+escHtml(name)+'">'+
      '<select class="tin fcol"><option value="">选择目标列</option>'+bindingCols().map(function(c){return '<option value="'+escHtml(c.name)+'"'+(hit===c.name?' selected':'')+'>'+escHtml(c.name)+'</option>';}).join('')+'</select>'+
      '<span class="mbadge"></span><label class="bklab"><input type="checkbox" class="fbk">去重依据</label></div>';
  }).join('');
  document.getElementById('bdrows').querySelectorAll('.fcol').forEach(function(s){s.onchange=function(){var badge=s.parentNode.querySelector('.mbadge');badge.className='mbadge '+(s.value?'ok':'warn');badge.textContent=s.value?'✓':'？';};});
}
function openBinding(binding){
  editBinding=binding||null;var existing=binding||null;
  bindingLocked=!!(existing&&['confirmed','running','ready'].indexOf(existing.status)>=0);
  bindingResult=existing?Object.assign({},existing,{load_binding:existing}):null;
  document.getElementById('bdtitle').textContent=existing?'编辑入库映射 #'+existing.extract_result_id:'新建入库映射';
  var resultSel=document.getElementById('bdresult');
  renderBindingResults();
  if(!existing)loadBindingResults();
  var tables=maps.filter(function(t){return t.datasource_code===dsById(curDs).code;});
  document.getElementById('bdtable').innerHTML='<option value="">选择业务表</option>'+tables.map(function(t){return '<option value="'+escHtml(t.code)+'"'+(existing&&existing.table_code===t.code?' selected':'')+'>'+escHtml(t.code||t.target_table)+'</option>';}).join('');
  document.getElementById('bdtable').disabled=bindingLocked;
  document.getElementById('bdtable').onchange=function(){
    document.getElementById('bdrows').innerHTML='';
    var code=this.value;
    if(code&&bindingResult&&bindingResult.fieldNames)loadBindingColumns(code,bindingResult.fieldNames);
  };
  document.getElementById('bdmode').value=existing?existing.write_mode:'upsert';document.getElementById('bdmode').disabled=bindingLocked;
  document.getElementById('bdlock').hidden=!bindingLocked;document.getElementById('bdsave').disabled=bindingLocked;
  document.getElementById('bdrows').innerHTML='';document.getElementById('bdmsg').textContent='';
  if(existing)loadBindingResult(existing.extract_result_id);else resultSel.onchange=function(){if(resultSel.value)loadBindingResult(Number(resultSel.value));};
  bdrawer.hidden=false;
}
function loadBindingResult(id){
  api('GET','/api/extract-results/'+id).then(function(j){
    var r=j.result||j;r.load_binding=j.load_binding||r.load_binding;bindingResult=r;
    var snapshot=r.rule_snapshot_json||r.snapshot_json||{};
    var schema=snapshot.output_schema||snapshot.output_schema_json||{};
    var spec=snapshot.extraction_spec||snapshot.extraction_spec_json||{};
    var names=(schema.fields||[]).map(function(f){return f.name;}).filter(Boolean);
    if(!names.length)names=(spec.fields||[]).map(function(f){return f.target;}).filter(Boolean);
    bindingResult.fieldNames=names;
    if(!names.length)throw new Error('结果快照没有固定字段');
    var tableCode=document.getElementById('bdtable').value;if(tableCode)loadBindingColumns(tableCode,names);else document.getElementById('bdrows').innerHTML='<div class="sthint">请先选择业务表。</div>';
  }).catch(function(e){document.getElementById('bdmsg').textContent=e.message;});
}
function loadBindingColumns(tableCode,names){
  var lt=maps.filter(function(t){return t.code===tableCode;})[0];
  if(!lt)throw new Error('业务表配置不存在');
  api('GET','/api/load/datasources/'+curDs+'/columns?table='+encodeURIComponent(lt.target_table)).then(function(j){cols=j.items||[];bindingRowsHtml(names);var b=bindingResult.load_binding;if(b)businessKeysOf(b).forEach(function(key){var row=Array.prototype.find.call(document.getElementById('bdrows').children,function(div){return div.querySelector('.fcol').value===key;});if(row)row.querySelector('.fbk').checked=true;});document.getElementById('bdmode').onchange=function(){document.getElementById('bdrows').querySelectorAll('.fbk').forEach(function(c){c.disabled=document.getElementById('bdmode').value==='insert';if(c.disabled)c.checked=false;});};}).catch(function(e){document.getElementById('bdmsg').textContent=e.message;});
}
function closeBinding(){bdrawer.hidden=true;}
document.getElementById('newbinding').onclick=function(){if(curDs)openBinding(null);};document.getElementById('bdclose').onclick=closeBinding;
bdrawer.addEventListener('click',function(e){if(e.target===bdrawer)closeBinding();});
document.addEventListener('keydown',function(e){if(e.key!=='Escape')return;if(!dds.hidden)closeDs();if(!dmap.hidden)closeDmap();if(!bdrawer.hidden)closeBinding();});
document.getElementById('bdsave').onclick=function(){
  var msg=document.getElementById('bdmsg');msg.textContent='';if(bindingLocked){msg.textContent='已确认或已入库的绑定不可修改';return;}
  var resultId=Number(document.getElementById('bdresult').value),tableCode=document.getElementById('bdtable').value;
  if(!resultId||!tableCode){msg.textContent='请选择抽取结果与业务表';return;}
  var map={},seen={},keys=[],err='';
  document.getElementById('bdrows').querySelectorAll('.frow').forEach(function(div){var f=div.querySelector('.fname').value,c=div.querySelector('.fcol').value;if(c){if(seen[c])err='多个字段指向同一目标列：'+c;seen[c]=1;map[f]=c;if(div.querySelector('.fbk').checked)keys.push(c);}});
  var mode=document.getElementById('bdmode').value;if(!Object.keys(map).length)err='至少映射一个字段';if(!err&&mode!=='insert'&&!keys.length)err=modeLabel(mode)+'须至少选择去重依据';
  if(err){msg.textContent=err;return;}
  var body={extract_result_id:resultId,table_code:tableCode,field_map:map,write_mode:mode,business_keys:keys};
  (editBinding?api('PATCH','/api/load/bindings/'+editBinding.id,body):api('POST','/api/load/bindings',body)).then(function(){closeBinding();showOk('已保存待确认绑定；业务写入仍须在结果入库向导中显式确认。');return loadAll(true);}).catch(function(e){msg.textContent=e.message;});
};
document.getElementById('bindingrows').addEventListener('click',function(e){var b=e.target.closest?e.target.closest('[data-editbinding]'):null;if(b)openBinding(bindingById(Number(b.getAttribute('data-editbinding'))));});
loadAll(false);
