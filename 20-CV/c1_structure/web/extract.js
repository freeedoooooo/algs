/* web/extract.js — 单行抽取规则管理：列表＋编辑抽屉。 */
var items=[], cur=null, origName='', origDesc='', cands=null, pendingTable=null,
    filledFromFile=false, validationReport=null, page=1, size=getListPer();
var rows=document.getElementById('rows');
var pg=bindPager(document.getElementById('pager'),
  function(d){ page+=d; render(); },
  function(n){ size=n; page=1; render(); });
var edit=document.getElementById('edit');
var ename=document.getElementById('ename'), edesc=document.getElementById('edesc');
var refsel=document.getElementById('refsel');
var tblsel=document.getElementById('tblsel'), tmanual=document.getElementById('tmanual');
var tindex=document.getElementById('tindex'), tkw=document.getElementById('tkw');
var frows=document.getElementById('frows'), emsg=document.getElementById('emsg');
var savebtn=document.getElementById('savebtn'), delbtn=document.getElementById('delbtn');
var modeSimple=document.getElementById('modeSimple'), modeJson=document.getElementById('modeJson');
var modeSmart=document.getElementById('modeSmart');
var jsonsec=document.getElementById('jsonsec'), jsonspec=document.getElementById('jsonspec');
var simpleSec=document.getElementById('simpleSec'), smartSec=document.getElementById('smartSec');
var smartRows=document.getElementById('smartRows'), smartAdd=document.getElementById('smartAdd');
var smartScope=document.getElementById('smartScope'), smartPage=document.getElementById('smartPage');
var smartPrompt=document.getElementById('smartPrompt'), smartModel=document.getElementById('smartModel');
var mode='simple';
function setMode(m){
  mode=m;
  modeSimple.className='tab'+(m==='simple'?' on':'');
  modeJson.className='tab'+(m==='json'?' on':'');
  modeSmart.className='tab'+(m==='smart'?' on':'');
  simpleSec.hidden=(m!=='simple');
  jsonsec.hidden=(m!=='json');
  smartSec.hidden=(m!=='smart');
  if(m==='simple') emsg.textContent='';
}
modeSimple.onclick=function(){setMode('simple');};
modeJson.onclick=function(){setMode('json');};
modeSmart.onclick=function(){setMode('smart');};
smartScope.onchange=function(){smartPage.hidden=(smartScope.value!=='page');};
/* ---- 复杂抽取：场景模板 → 生成抽取定义（可继续手动微调） ---- */
var tplKind=document.getElementById('tplKind'), tplForm=document.getElementById('tplForm');
var genJson=document.getElementById('genJson');
function tv(id){var e=document.getElementById(id);return e?e.value.trim():'';}
function colSel(mode,raw){
  if(mode==='index') return {index:Number(raw||0)};
  if(mode==='exact') return {name:raw};
  return {header_contains:raw};
}
/* 简单规则译为 v2：转换下沉到抽取阶段；restrict 限定仅所选表产出记录。 */
function transformOps(apply){
  var pipe=[];
  (apply||[]).forEach(function(name){
    if(name==='trim') pipe.push({op:'trim'});
    else if(name==='number'){
      pipe.push({op:'replace',pattern:'\\s+',repl:''});
      pipe.push({op:'number',strip:','});
    }
  });
  return pipe;
}
function simpleToV2Spec(table,fields,transforms){
  var sel={ref:'main',restrict:true};
  if(table&&typeof table.index==='number') sel.index=table.index;
  else if(table&&table.header_contains) sel.header_contains=table.header_contains;
  var fx={};
  (transforms||[]).forEach(function(t){if(t&&t.target) fx[t.target]=t.apply||[];});
  return {
    spec_version:2,
    origin:'simple',
    tables:[Object.assign({role:'record_source'},sel)],
    records:{strategy:'row',source_ref:'main'},
    fields:(fields||[]).map(function(f){
      var pipe=[{op:'cell',source:'main',column:f.column||{}}];
      return {target:f.target,pipeline:pipe.concat(transformOps(fx[f.target]))};
    })
  };
}
function v2ToSimpleForm(mp){
  var sel=(mp.tables||[])[0]||{}, table={};
  if(typeof sel.index==='number') table.index=sel.index;
  else if(sel.header_contains) table.header_contains=sel.header_contains;
  var fields=(mp.fields||[]).map(function(f){
    var pipe=f.pipeline||[];
    var cell=pipe.filter(function(s){return s&&s.op==='cell';})[0]||{};
    var apply=[];
    pipe.forEach(function(s){
      if(s&&s.op==='trim') apply.push('trim');
      else if(s&&s.op==='number') apply.push('number');
    });
    return {target:f.target,column:cell.column||null,fx:apply.join(',')};
  });
  return {table:table,fields:fields};
}
function tableRow(){
  return '<div class="tplrow">'+
    '<input class="tin tk_col" placeholder="原始列名 / 列序号">'+
    '<input class="tin tk_name" placeholder="中文逻辑字段">'+
    '<select class="tin tk_type" title="字段类型">'+
      '<option value="text">文本</option><option value="amount">金额</option>'+
    '</select>'+
    '<button type="button" class="linkbtn danger tk_del" title="删除该行">×</button>'+
  '</div>';
}
function bindTableEvents(){
  var rows=tplForm.querySelectorAll('#tk_rows .tplrow');
  for(var i=0;i<rows.length;i++){
    rows[i].querySelector('.tk_del').onclick=function(){
      if(tplForm.querySelectorAll('#tk_rows .tplrow').length<=1){
        emsg.textContent='至少保留一个普通字段行'; return;
      }
      this.parentNode.remove(); emsg.textContent='';
    };
  }
  var add=tplForm.querySelector('#tk_add');
  if(add) add.onclick=function(){
    tplForm.querySelector('#tk_rows').insertAdjacentHTML('beforeend',tableRow());
    bindTableEvents();
  };
}
function smartRow(name,desc){
  return '<div class="tplrow">'+
    '<input class="tin sm_desc" placeholder="字段说明（给模型看的提示）" value="'+
      escHtml(desc||'')+'">'+
    '<input class="tin sm_name" placeholder="中文逻辑字段" value="'+
      escHtml(name||'')+'">'+
    '<button type="button" class="linkbtn danger sm_del" title="删除该行">×</button>'+
  '</div>';
}
function bindSmartEvents(){
  var rows=smartRows.querySelectorAll('.tplrow');
  for(var i=0;i<rows.length;i++){
    rows[i].querySelector('.sm_del').onclick=function(){
      if(smartRows.querySelectorAll('.tplrow').length<=1){
        emsg.textContent='至少保留一个字段'; return;
      }
      this.parentNode.remove(); emsg.textContent='';
    };
  }
  smartAdd.onclick=function(){
    smartRows.insertAdjacentHTML('beforeend',smartRow('',''));
    bindSmartEvents();
  };
}
var TPL={
  table:{
    render:function(){
      return '<label>表头关键词<input class="tin" id="tk_table" placeholder="留空则取第一张表"></label>'+
        '<label>列匹配方式<select class="tin" id="tk_mode">'+
        '<option value="contains">表头包含</option><option value="exact">表头原名</option>'+
        '<option value="index">列序号</option></select></label>'+
        '<div class="full tplhead"><span>原始列名</span><span>中文逻辑字段</span>'+
        '<span>类型<span class="hint" tabindex="0" data-tip="金额：自动追加 regex 与 number，去逗号并转数值。&#10;文本：只取原格文本。">?</span></span><span></span></div>'+
        '<div class="full" id="tk_rows">'+tableRow()+tableRow()+'</div>'+
        '<button type="button" class="btn mini ghost" id="tk_add">＋添加字段</button>';
    },
    build:function(){
      var mode=tv('tk_mode')||'contains', fields=[];
      var rows=tplForm.querySelectorAll('#tk_rows .tplrow');
      for(var i=0;i<rows.length;i++){
        var n=rows[i].querySelector('.tk_name').value.trim();
        var c=rows[i].querySelector('.tk_col').value.trim();
        if(!n||!c) continue;
        var pipe=[{op:'cell',source:'main',column:colSel(mode,c)}];
        if(rows[i].querySelector('.tk_type').value==='amount'){
          pipe.push({op:'regex',pattern:'-?[\\d,]+\\.\\d{2}'});
          pipe.push({op:'number',strip:','});
        }
        fields.push({target:n,pipeline:pipe});
      }
      if(!fields.length) return null;
      var spec={spec_version:2,records:{strategy:'row',source_ref:'main'},fields:fields};
      var kw=tv('tk_table');
      spec.tables=[{ref:'main',role:'record_source'}];
      if(kw) spec.tables[0].header_contains=kw;
      return spec;
    }
  },
  kv:{
    render:function(){
      return '<label class="full">中文逻辑字段<input class="tin" id="kv_target" value="信用代码"></label>'+
        '<label class="full">标签文本<input class="tin" id="kv_label" value="统一社会信用代码"></label>'+
        '<label>匹配方式<select class="tin" id="kv_match">'+
        '<option value="contains">包含</option><option value="exact">完全相同</option>'+
        '<option value="regex">正则</option></select></label>'+
        '<label>值方向<select class="tin" id="kv_dir">'+
        '<option value="inline">同一行冒号后</option><option value="right">同行右侧</option>'+
        '<option value="below">下一行</option></select></label>'+
        '<label>值正则<input class="tin" id="kv_regex" value="[0-9A-Z]{18}"></label>'+
        '<label>记录策略<select class="tin" id="kv_strategy">'+
        '<option value="one_per_page">每页一条</option><option value="row">表格行</option></select></label>';
    },
    build:function(){
      var target=tv('kv_target')||'字段', label=tv('kv_label');
      if(!label) return null;
      var value={direction:tv('kv_dir')||'inline'}, re=tv('kv_regex');
      if(re) value.regex=re;
      return {spec_version:2,records:{strategy:tv('kv_strategy')||'one_per_page'},
        fields:[{target:target,pipeline:[{op:'kv',source:'texts',
          label:{text:label,match:tv('kv_match')||'contains'},value:value}]}]};
    }
  },
  page:{
    render:function(){
      return '<label class="full"><span class="lblrow">中文逻辑字段'+
        '<span class="hint" tabindex="0" data-tip="该页正文写入 records 的这个键。&#10;固定行为：取该页 plain_text 全文，每页产出一条记录；不支持选列或正则。">?</span></span>'+
        '<input class="tin" id="pg_target" value="正文"></label>';
    },
    build:function(){
      var target=tv('pg_target')||'正文';
      return {spec_version:2,
        records:{strategy:'one_per_page'},
        fields:[{target:target,pipeline:[{op:'page_text'}]}]};
    }
  }
};
function renderTplForm(){
  var f=TPL[tplKind.value];
  tplForm.innerHTML=f?f.render():'<div class="full sthint">选择模板或直接编辑 JSON。</div>';
  bindTableEvents();
  emsg.textContent='';
}
tplKind.onchange=renderTplForm;
genJson.onclick=function(){
  var f=TPL[tplKind.value];
  if(!f){emsg.textContent='请先选择一个场景模板';return;}
  var spec=f.build();
  if(!spec){emsg.textContent='请至少填写一个字段或标签';return;}
  jsonspec.value=JSON.stringify(spec,null,2);
};

function api(method,url,body){
  var opt={method:method,headers:{}};
  if(body!==undefined){
    opt.headers['Content-Type']='application/json';
    opt.body=JSON.stringify(body);
  }
  return fetch(url,opt).then(function(r){
    return r.json().catch(function(){return {};}).then(function(j){
      if(!r.ok) throw new Error(j.error||('HTTP '+r.status));
      return j;
    });
  });
}
function showOk(msg){
  var b=document.getElementById('ok');
  b.textContent=msg; b.hidden=false;
  document.getElementById('err').hidden=true;
}
function showErr(msg){
  var b=document.getElementById('err');
  b.textContent=msg; b.hidden=false;
}

/* ---- 列表 ---- */
function render(){
  var q=document.getElementById('q').value.trim().toLowerCase();
  var list=items.filter(function(r){
    if(!q) return true;
    return ((r.name||'')+' '+(r.description||'')).toLowerCase().indexOf(q)>=0;
  });
  var info=pageSlice(list,page,size);
  page=info.page;
  rows.innerHTML=info.rows.map(function(r,i){
    return '<tr>'+
      '<td class="seq">'+seqNo(info,i)+'</td>'+
      '<td class="mono">'+r.id+'</td>'+
      '<td class="left">'+escHtml(r.name)+'</td>'+
      '<td class="left"><span class="desc" title="'+escHtml(r.description||'')+'">'+
        escHtml(r.description||'—')+'</span></td>'+
      '<td class="num">'+(((r.output_schema_json||{}).fields||[]).length)+'</td>'+
      '<td class="num">'+fmtTime(r.updated_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-edit="'+r.id+'">编辑</button>'+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  pg.render(info);
}
function load(){
  return api('GET','/api/extract-rules').then(function(j){
    items=j.items||[]; render();
    document.getElementById('err').hidden=true;
  }).catch(function(e){
    items=[]; render();
    showErr('平台库未连接：抽取规则目录暂不可用（'+e.message+'）');
  });
}
document.getElementById('q').addEventListener('input',function(){ page=1; render(); });
rows.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-edit],[data-del]'):null;
  if(!b) return;
  if(b.hasAttribute('data-del')){
    delRule(Number(b.getAttribute('data-del')),b.getAttribute('data-name'));
    return;
  }
  openEditor(Number(b.getAttribute('data-edit')));
});
document.getElementById('newbtn').onclick=function(){openEditor(null);};

/* ---- 候选表 / 键（与 collect._candidate_tables / _keys 同序同规则） ---- */
function candidates(doc){
  var stitched=doc.stitched_tables||[], merged={}, out=[];
  stitched.forEach(function(t){
    (t.parts||[]).forEach(function(p){merged[p.page+':'+p.tbl]=1;});
  });
  (doc.pages||[]).forEach(function(pg){
    (pg.tables||[]).forEach(function(t,ti){
      if(merged[pg.index+':'+ti]) return;
      out.push({t:t,scope:'page',ti:ti});
    });
  });
  stitched.forEach(function(t,si){out.push({t:t,scope:'stitched',ti:si});});
  return out;
}
function keysOf(headers){
  var keys=[], seen={};
  (headers||[]).forEach(function(h,c){
    var k=String(h==null?'':h).trim()||('col_'+c);
    if(seen[k]) k=k+'_'+c;
    seen[k]=1; keys.push(k);
  });
  return keys;
}
function currentKeys(){
  if(!cands||tblsel.disabled) return [];
  var c=cands[Number(tblsel.value)];
  return c?keysOf(c.t.headers):[];
}

/* ---- 字段行 ---- */
function readCol(div){
  var sel=div.querySelector('.fcol'), idx=div.querySelector('.fidx');
  if(sel.value==='__idx'){
    var n=parseInt(idx.value,10);
    return isNaN(n)?null:{index:n};
  }
  return sel.value?{name:sel.value}:null;
}
function syncIdx(div){
  div.querySelector('.fidx').hidden=div.querySelector('.fcol').value!=='__idx';
}
function fillCol(div,col){
  var sel=div.querySelector('.fcol'), idx=div.querySelector('.fidx');
  var keys=currentKeys();
  var html=keys.map(function(k){
    return '<option value="'+escHtml(k)+'">'+escHtml(k)+'</option>';
  }).join('');
  if(!keys.length) html='<option value="">（选参考表后列出源列）</option>'+html;
  html+='<option value="__idx">按列序号…</option>';
  sel.innerHTML=html;
  if(col&&col.name!=null){
    if(keys.indexOf(col.name)<0)
      sel.innerHTML+='<option value="'+escHtml(col.name)+'">'+
        escHtml(col.name)+'（现有）</option>';
    sel.value=col.name; idx.hidden=true;
  }else if(col&&col.index!=null){
    sel.value='__idx'; idx.value=col.index; idx.hidden=false;
  }else{
    sel.value=keys.length?keys[0]:''; idx.hidden=true;
  }
}
function addRow(target,col,fx){
  var div=document.createElement('div');
  div.className='frow';
  div.innerHTML='<select class="tin fcol"></select>'+
    '<input type="number" class="tin fidx" min="0" placeholder="列序号" hidden>'+
    '<input type="text" class="tin fname" placeholder="中文逻辑字段" value="'+
    escHtml(target||'')+'">'+
    '<select class="tin fxform" title="抽取时应用的转换">'+
      '<option value="">无转换</option>'+
      '<option value="trim">trim</option>'+
      '<option value="trim,number">trim+number</option>'+
    '</select>'+
    '<button type="button" class="btn mini danger fdel">删</button>';
  frows.appendChild(div);
  fillCol(div,col);
  div.querySelector('.fxform').value=fx||'';
  div.querySelector('.fcol').onchange=function(){syncIdx(div);};
  div.querySelector('.fdel').onclick=function(){div.remove();};
}
function refreshCols(){
  Array.prototype.forEach.call(frows.children,function(div){
    fillCol(div,readCol(div));
  });
}
function rowsHaveContent(){
  return Array.prototype.some.call(frows.children,function(div){
    return (div.querySelector('.fname').value||'').trim()!=='' ||
      readCol(div)!==null ||
      div.querySelector('.fxform').value!=='';
  });
}
/* 参考文件选表：按文档源列整表填充中文逻辑字段。
   已有配置且从未由参考文件填充时不覆盖；切换参考表时覆盖。 */
function autofillRows(){
  var keys=currentKeys();
  if(!keys.length) return;
  if(!filledFromFile&&rowsHaveContent()) return;
  frows.innerHTML='';
  keys.forEach(function(k){ addRow(k,{name:k}); });
  filledFromFile=true;
}
document.getElementById('addfield').onclick=function(){addRow('',null);};

/* ---- 公共参考：可多选已解析资料，首份用于查看候选表列 ---- */
function selectedRefs(){
  return Array.prototype.map.call(refsel.selectedOptions||[],function(o){
    return Number(o.value);
  }).filter(function(id){return id>0;});
}
function loadRefs(){
  refsel.innerHTML='';
  return api('GET','/api/sources/state').then(function(j){
    (j.items||[]).forEach(function(f){
      if(['ready','to_review','to_load','loading','loaded'].indexOf(f.state)<0) return;
      var o=document.createElement('option');
      o.value=String(f.id);
      o.textContent='#'+f.id+' · '+f.name;
      refsel.appendChild(o);
    });
  }).catch(function(){
    emsg.textContent='参考文件列表暂不可用，可手动填写源表。';
  });
}
function hasOpt(sel,v){
  return Array.prototype.some.call(sel.options,function(o){
    return o.value===String(v);
  });
}
function applyRefs(docIds){
  var ids=Array.isArray(docIds)?docIds:(docIds&&docIds.file_id?[docIds.file_id]:[]);
  Array.prototype.forEach.call(refsel.options,function(o){o.selected=false;});
  ids.slice(0,10).forEach(function(id){
    if(hasOpt(refsel,id)){
      Array.prototype.filter.call(refsel.options,function(o){
        return o.value===String(id);
      })[0].selected=true;
    }
  });
  return refsel.onchange();
}
function manualMode(hint){
  cands=null; tblsel.disabled=true;
  tblsel.innerHTML='<option value="">—</option>';
  tmanual.hidden=false;
  emsg.textContent=hint||'';
  refreshCols();
}
refsel.onchange=function(){
  var id=selectedRefs()[0];
  if(!id){manualMode();return Promise.resolve();}
  return api('GET','/api/sources/'+id+'/parse').then(function(doc){
    cands=candidates(doc);
    if(!cands.length){manualMode('首份参考文件未解析出表格，请手动填写源表。');return;}
    tblsel.innerHTML=cands.map(function(c,i){
      var head=(c.t.headers||[]).slice(0,4).join(' / ');
      return '<option value="'+i+'">#'+i+' · '+c.scope+' · '+
        escHtml(head||'（无表头）')+'</option>';
    }).join('');
    tblsel.disabled=false; tmanual.hidden=true;
    var want=(pendingTable&&typeof pendingTable.index==='number')?pendingTable.index:0;
    tblsel.value=String(want>=0&&want<cands.length?want:0);
    autofillRows(); refreshCols();
  }).catch(function(e){
    manualMode('参考加载失败：'+e.message+'，可手动填写源表。');
  });
};
tblsel.onchange=function(){autofillRows();refreshCols();};
function collectRefs(){return selectedRefs();}

/* ---- 编辑抽屉 ---- */
function closeEditor(){edit.hidden=true;cur=null;}
document.getElementById('eclose').onclick=closeEditor;
edit.addEventListener('click',function(e){if(e.target===edit)closeEditor();});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'&&!edit.hidden) closeEditor();
});

function openEditor(id){
  cur=id; cands=null; pendingTable=null; filledFromFile=false; validationReport=null;
  emsg.textContent=''; frows.innerHTML='';
  aiReset();
  setMode('simple'); jsonspec.value='';
  smartRows.innerHTML=smartRow('',''); bindSmartEvents();
  smartScope.value='all'; smartPage.value=''; smartPage.hidden=true;
  smartPrompt.value=''; smartModel.value='';
  tplKind.value=''; renderTplForm();
  refsel.value=''; tindex.value=''; tkw.value='';
  manualMode();
  document.getElementById('ok').hidden=true;
  if(id==null){
    document.getElementById('etitle').textContent='新建规则';
    document.getElementById('everbadge').innerHTML='';
    ename.value=''; edesc.value=''; origName=''; origDesc='';
    delbtn.hidden=true;
    document.getElementById('versec').hidden=true;
    addRow('',null);
    edit.hidden=false; loadRefs();
    return;
  }
  api('GET','/api/extract-rules/'+id).then(function(j){
    document.getElementById('etitle').textContent='编辑规则 #'+id;
    document.getElementById('everbadge').innerHTML='<span class="badge green">单行规则</span>';
    ename.value=j.name||''; edesc.value=j.description||'';
    origName=j.name||''; origDesc=j.description||'';
    var mp=j.extraction_spec_json||{};
    validationReport=j.validation_report_json||null;
    if(mp.spec_version===3){
      setMode('smart');
      var sfs=mp.fields||[];
      smartRows.innerHTML=sfs.length
        ? sfs.map(function(f){return smartRow(f.target,f.description||'');}).join('')
        : smartRow('','');
      bindSmartEvents();
      smartScope.value=((mp.records||{}).scope)||'all';
      smartPage.value=((mp.records||{}).page)||'';
      smartPage.hidden=(smartScope.value!=='page');
      var sm=mp.smart||{};
      smartPrompt.value=sm.prompt_template||''; smartModel.value=sm.model||'';
    }else if(mp.spec_version===2){
      if(mp.origin==='simple'){
        setMode('simple');
        var sf=v2ToSimpleForm(mp);
        pendingTable=sf.table;
        if(typeof pendingTable.index==='number') tindex.value=pendingTable.index;
        if(pendingTable.header_contains) tkw.value=pendingTable.header_contains;
        sf.fields.forEach(function(f){addRow(f.target,f.column,f.fx);});
        if(!sf.fields.length) addRow('',null);
      }else{
        setMode('json'); jsonspec.value=JSON.stringify(mp,null,2);
      }
    }else{
      setMode('json'); jsonspec.value=JSON.stringify(mp,null,2);
    }
    delbtn.hidden=false;
    document.getElementById('versec').hidden=false;
    edit.hidden=false;
    return loadRefs().then(function(){
      return applyRefs(j.reference_doc_ids_json);
    });
  }).catch(function(e){showErr(e.message);});
}

/* ---- 保存 / 删除 ---- */
savebtn.onclick=function(){
  emsg.textContent='';
  var name=ename.value.trim();
  if(!name){emsg.textContent='规则名不能为空';return;}
  var schema, spec, transform;
  if(mode==='smart'){
    var sfields=[], sseen={}, serr=null;
    var srows=smartRows.querySelectorAll('.tplrow');
    for(var si=0;si<srows.length;si++){
      var sn=srows[si].querySelector('.sm_name').value.trim();
      var sd=srows[si].querySelector('.sm_desc').value.trim();
      if(!sn){serr='中文逻辑字段不能为空';break;}
      if(sseen[sn]){serr='中文逻辑字段重复：'+sn;break;}
      sseen[sn]=1; sfields.push({target:sn,description:sd});
    }
    if(serr){emsg.textContent=serr;return;}
    if(!sfields.length){emsg.textContent='至少需要一个中文逻辑字段';return;}
    var srec={strategy:'all',scope:smartScope.value};
    if(smartScope.value==='page'){
      if(!smartPage.value){emsg.textContent='请填写页码';return;}
      srec.page=Number(smartPage.value);
    }
    var sconf={};
    if(smartPrompt.value.trim()) sconf.prompt_template=smartPrompt.value.trim();
    if(smartModel.value.trim()) sconf.model=smartModel.value.trim();
    spec={spec_version:3,records:srec,fields:sfields,smart:sconf};
    schema={fields:sfields.map(function(f){return {name:f.target,type:'text'};})};
    transform=null;
  }else if(mode==='json'){
    var parsed;
    try{ parsed=JSON.parse(jsonspec.value); }
    catch(e){ emsg.textContent='JSON 语法错误：'+e.message; return; }
    if(!parsed || typeof parsed!=='object' || Array.isArray(parsed)){
      emsg.textContent='抽取定义须为 JSON 对象'; return;
    }
    if(parsed.spec_version!==2&&parsed.spec_version!==3){
      emsg.textContent='高级 JSON 模式要求 spec_version 为 2 或 3'; return;
    }
    schema={fields:(parsed.fields||[]).filter(function(f){
      return f && f.target;
    }).map(function(f){return {name:f.target,type:'text'};})};
    spec=parsed; transform=null;
  }else{
    var fields=[], seen={}, err=null, xf=[];
    Array.prototype.forEach.call(frows.children,function(div){
      if(err) return;
      var t=div.querySelector('.fname').value.trim();
      if(!t){err='中文逻辑字段不能为空';return;}
      if(seen[t]){err='中文逻辑字段重复：'+t;return;}
      seen[t]=1;
      var col=readCol(div);
      if(!col){err='字段「'+t+'」未选源列';return;}
      fields.push({target:t,column:col});
      var fx=div.querySelector('.fxform').value;
      if(fx) xf.push({target:t,apply:fx.split(',')});
    });
    if(err){emsg.textContent=err;return;}
    if(!fields.length){
      emsg.textContent='至少需要一个字段；如需逐行原样输出，请使用内置「原始透传」规则';return;
    }
    var table;
    if(cands&&!tblsel.disabled) table={index:Number(tblsel.value)};
    else if(tindex.value!=='') table={index:Number(tindex.value)};
    else if(tkw.value.trim()) table={header_contains:tkw.value.trim()};
    else{emsg.textContent='请选择源表（选择参考文件，或手动填写序号 / 表头关键词）';return;}
    schema={fields:fields.map(function(f){return {name:f.target,type:'text'};})};
    spec=simpleToV2Spec(table,fields,xf);
    transform=null;
  }
  var referenceIds=collectRefs();
  spec.refs=referenceIds.length?{file_id:referenceIds[0],reference_doc_ids:referenceIds.slice(1)}:{};
  var desc=edesc.value.trim();
  var payload={
    name:name,description:desc||null,
    output_schema_json:schema,extraction_spec_json:spec,
    reference_doc_ids_json:referenceIds,
    validation_report_json:validationReport||{}
  };
  savebtn.disabled=true;
  var p;
  if(cur==null){
    p=api('POST','/api/extract-rules',payload);
  }else{
    p=api('PATCH','/api/extract-rules/'+cur,payload);
  }
  p.then(function(){
    showOk('已保存「'+name+'」。已有抽取结果继续使用各自快照，重抽后使用最新定义。');
    return load();
  }).then(function(){
    if(cur==null){
      var it=items.filter(function(r){return r.name===name;})[0];
      if(it) openEditor(it.id);
    }else{
      origName=name; origDesc=desc;
    }
  }).catch(function(e){emsg.textContent=e.message;})
   .then(function(){savebtn.disabled=false;});
};

function delRule(id,name){
  if(!window.confirm('删除规则「'+name+'」？已有抽取结果会保留自己的快照，但不能再用该规则重抽。')) return;
  api('DELETE','/api/extract-rules/'+id).then(function(){
    if(cur===id) closeEditor();
    showOk('已删除规则「'+name+'」。');
    load();
  }).catch(function(e){
    if(cur===id&&!edit.hidden) emsg.textContent=e.message;
    else showErr(e.message);
  });
}
delbtn.onclick=function(){
  if(cur!=null) delRule(cur,ename.value.trim());
};

/* ---- AI 生成规则：需求描述 / 指定字段 ---- */
var aiGenBtn=document.getElementById('aiGenBtn'), aigen=document.getElementById('aigen');
var aiFields=document.getElementById('aiFields'), aiLog=document.getElementById('aiLog');
var aiMetrics=document.getElementById('aiMetrics'), aiDiff=document.getElementById('aiDiff');
var aiModeNatural=document.getElementById('aiModeNatural'), aiModePrecise=document.getElementById('aiModePrecise');
var aiPromptSec=document.getElementById('aiPromptSec'), aiPrompt=document.getElementById('aiPrompt');
var aiPreciseSec=document.getElementById('aiPreciseSec'), aiFieldRows=document.getElementById('aiFieldRows');
var aiFieldAdd=document.getElementById('aiFieldAdd'), aiInputTitle=document.getElementById('aiInputTitle');
var aiMode='natural', aiPreciseSeeded=false;
function aiSetMode(m){
  aiMode=m;
  aiModeNatural.className='ai-mode'+(m==='natural'?' on':'');
  aiModePrecise.className='ai-mode'+(m==='precise'?' on':'');
  aiModeNatural.setAttribute('aria-selected',m==='natural'?'true':'false');
  aiModePrecise.setAttribute('aria-selected',m==='precise'?'true':'false');
  aiPromptSec.hidden=(m!=='natural');
  aiPreciseSec.hidden=(m!=='precise');
  aiInputTitle.textContent='① 输入';
  if(m==='precise') aiSeedPrecise();
}
function aiAddField(value,description){
  var div=document.createElement('div');
  div.className='ai-field-row';
  var input=document.createElement('input');
  input.type='text'; input.className='tin ai-field-name';
  input.placeholder='中文逻辑字段'; input.setAttribute('aria-label','中文逻辑字段');
  input.value=value||''; input.dataset.description=description||'';
  var del=document.createElement('button');
  del.type='button'; del.className='ai-field-del'; del.textContent='删除';
  del.onclick=function(){
    if(aiFieldRows.children.length===1) input.value='';
    else div.remove();
  };
  div.appendChild(input); div.appendChild(del); aiFieldRows.appendChild(div);
  return input;
}
function aiSeedPrecise(){
  if(aiPreciseSeeded||aiTargets().length){aiPreciseSeeded=true;return;}
  aiPreciseSeeded=true;
  var values=[], descriptions={};
  if(mode==='smart'){
    Array.prototype.forEach.call(smartRows.querySelectorAll('.tplrow'),function(r){
      var n=r.querySelector('.sm_name').value.trim();
      if(n&&values.indexOf(n)<0){values.push(n);descriptions[n]=r.querySelector('.sm_desc').value.trim();}
    });
  }else if(mode==='simple'){
    Array.prototype.forEach.call(frows.children,function(div){
      var n=div.querySelector('.fname').value.trim();
      if(n&&values.indexOf(n)<0) values.push(n);
    });
  }
  if(!values.length) values=[''];
  values.forEach(function(n){aiAddField(n,descriptions[n]);});
}
function aiReset(){
  aiClose(); aiPrompt.value=''; aiFieldRows.innerHTML=''; aiPreciseSeeded=false;
  aiSetMode('natural');
}
aiModeNatural.onclick=function(){aiSetMode('natural');};
aiModePrecise.onclick=function(){aiSetMode('precise');};
aiFieldAdd.onclick=function(){aiAddField('').focus();};
function aiClose(){aigen.hidden=true;aiFields.innerHTML='';aiLog.textContent='';
  aiMetrics.innerHTML='';aiDiff.textContent='';}
function aiTargets(){
  var out=[], seen={};
  Array.prototype.forEach.call(aiFieldRows.querySelectorAll('.ai-field-name'),function(inp){
    var n=inp.value.trim();
    if(n&&!seen[n]){seen[n]=1;out.push({target:n,description:inp.dataset.description||''});}
  });
  return out;
}
function aiMetric(label,val){
  return '<div class="aigen-metric"><span>'+escHtml(label)+'</span><b>'+escHtml(val)+'</b></div>';
}
aiGenBtn.onclick=function(){
  emsg.textContent='';
  var referenceIds=selectedRefs();
  var fid=referenceIds[0];
  if(!fid){showErr('请先选择参考文件（已解析的资料）');return;}
  var isNatural=aiMode==='natural';
  var promptText=aiPrompt.value.trim();
  var fields=isNatural?[]:aiTargets();
  if(isNatural&&!promptText){showErr('请填写要提取的内容（需求提示词）');return;}
  if(!isNatural&&!fields.length){showErr('请至少填写一个中文逻辑字段');return;}
  aigen.hidden=false;
  aiFields.innerHTML=isNatural
    ? '<span class="aigen-chip">'+escHtml(promptText)+'</span>'
    : fields.map(function(f){return '<span class="aigen-chip">'+escHtml(f.target)+'</span>';}).join('');
  aiLog.textContent='正在生成规则草稿…';
  aiMetrics.innerHTML='';aiDiff.textContent='';
  aiGenBtn.disabled=true;
  var payload={file_id:fid,reference_doc_ids:referenceIds.slice(1)};
  if(isNatural) payload.prompt=promptText; else payload.fields=fields;
  api('POST','/api/agent/generate-rule',payload).then(function(j){
    var d=j.diagnostics||{}, cmp=d.compare||{};
    var lines=[];
    lines.push('静态校验：通过');
    lines.push('内存干跑：'+(d.records_n||0)+' 条记录');
    if(j._agent_meta&&j._agent_meta.stub) lines.push('Stub 占位：pipeline 为空，仅联调');
    if(j._agent_meta&&j._agent_meta.repairs) lines.push('JSON 修复：'+j._agent_meta.repairs+' 次');
    aiLog.textContent=lines.join('\n');
    var acc=cmp.field_accuracy==null?'—':(Math.round(cmp.field_accuracy*100)+'%');
    var cov=d.anchor_coverage==null?'—':(Math.round(d.anchor_coverage*100)+'%');
    aiMetrics.innerHTML=aiMetric('字段一致率',acc)+aiMetric('锚点覆盖',cov)+
      aiMetric('置信度',Math.round((j.confidence||0)*100)+'%')+
      aiMetric('对拍样本',cmp.targets_n==null?'—':cmp.targets_n);
    var msgs=[];
    if(d.warning) msgs.push(escHtml(d.warning));
    if(cmp.count_match===false) msgs.push('记录数与已确认样本不一致');
    if(cmp.targets_n&&cmp.field_accuracy==null) msgs.push('暂无可比对字段');
    aiDiff.textContent=msgs.join('；');
    setMode('json');
    jsonspec.value=JSON.stringify(j.spec,null,2);
    validationReport=j.validation_report_json||{};
    showOk('已生成规则草稿，请在「复杂抽取」编辑器中审阅后保存规则。');
  }).catch(function(e){
    aiLog.textContent='生成失败：'+e.message;
    emsg.textContent=e.message;
  }).then(function(){aiGenBtn.disabled=false;});
};

load();
/* 深链 ?rule=<id>：从资料处理页跳来时直接打开右侧编辑栏 */
var deepRule=parseInt(new URLSearchParams(location.search).get('rule'),10);
if(deepRule) openEditor(deepRule);