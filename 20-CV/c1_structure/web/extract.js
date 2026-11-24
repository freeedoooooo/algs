/* web/extract.js — 抽取规则管理：列表＋编辑抽屉（结构化字段行
   表单＋参考文件预览辅助选表选列）＋版本历史。 */
var items=[], cur=null, origName='', origDesc='', cands=null, pendingTable=null,
    page=1, size=getListPer();
var rows=document.getElementById('rows');
var pg=bindPager(document.getElementById('pager'),
  function(d){ page+=d; render(); },
  function(n){ size=n; page=1; render(); });
var edit=document.getElementById('edit');
var ename=document.getElementById('ename'), edesc=document.getElementById('edesc');
var refsel=document.getElementById('refsel'), refhint=document.getElementById('refhint');
var tblsel=document.getElementById('tblsel'), tmanual=document.getElementById('tmanual');
var tindex=document.getElementById('tindex'), tkw=document.getElementById('tkw');
var frows=document.getElementById('frows'), emsg=document.getElementById('emsg');
var savebtn=document.getElementById('savebtn'), delbtn=document.getElementById('delbtn');
var modeSimple=document.getElementById('modeSimple'), modeJson=document.getElementById('modeJson');
var jsonsec=document.getElementById('jsonsec'), jsonspec=document.getElementById('jsonspec');
var simpleSec=document.getElementById('simpleSec'), mode='simple';
function setMode(m){
  mode=m;
  modeSimple.className='tab'+(m==='simple'?' on':'');
  modeJson.className='tab'+(m==='json'?' on':'');
  simpleSec.hidden=(m!=='simple');
  jsonsec.hidden=(m!=='json');
  if(m==='simple') emsg.textContent='';
}
modeSimple.onclick=function(){setMode('simple');};
modeJson.onclick=function(){setMode('json');};
var vertoggle=document.getElementById('vertoggle'), verlist=document.getElementById('verlist');
vertoggle.onclick=function(){
  var open=verlist.hidden;
  verlist.hidden=!open;
  vertoggle.textContent=open?'收起':'展开';
};

/* ---- 复杂抽取：场景模板 → 生成 mapping_json（可继续手动微调） ---- */
var tplKind=document.getElementById('tplKind'), tplForm=document.getElementById('tplForm');
var genJson=document.getElementById('genJson');
function tv(id){var e=document.getElementById(id);return e?e.value.trim():'';}
function colSel(mode,raw){
  if(mode==='index') return {index:Number(raw||0)};
  if(mode==='exact') return {name:raw};
  return {header_contains:raw};
}
function tableRow(){
  return '<div class="tplrow">'+
    '<input class="tin tk_col" placeholder="原始列名 / 列序号">'+
    '<input class="tin tk_name" placeholder="目标字段名">'+
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
var TPL={
  table:{
    render:function(){
      return '<label>表头关键词<input class="tin" id="tk_table" placeholder="留空则取第一张表"></label>'+
        '<label>列匹配方式<select class="tin" id="tk_mode">'+
        '<option value="contains">表头包含</option><option value="exact">表头原名</option>'+
        '<option value="index">列序号</option></select></label>'+
        '<div class="full tplhead"><span>原始列名</span><span>目标字段名</span>'+
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
      var spec={spec_version:2,records:{strategy:'row'},fields:fields};
      var kw=tv('tk_table'); if(kw) spec.tables=[{ref:'main',header_contains:kw}];
      return spec;
    }
  },
  kv:{
    render:function(){
      return '<label class="full">目标字段名<input class="tin" id="kv_target" value="信用代码"></label>'+
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
      return '<label class="full">目标字段名'+
        '<span class="hint" tabindex="0" data-tip="固定行为：每页一条记录，值为该页 plain_text 全文；不支持选列或正则。&#10;需要更细的抽取请选其他模板或直接编辑 JSON。">?</span>'+
        '<input class="tin" id="pg_target" value="正文"></label>'+
        '<label class="full checkrow"><input type="checkbox" id="pg_note" checked> 每页一条记录</label>';
    },
    build:function(){
      var target=tv('pg_target')||'正文';
      return {spec_version:2,
        records:{strategy:document.getElementById('pg_note').checked?'one_per_page':'row'},
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
      '<td>'+escHtml(r.name)+'</td>'+
      '<td><span class="desc" title="'+escHtml(r.description||'')+'">'+
        escHtml(r.description||'—')+'</span></td>'+
      '<td class="num">v'+r.current_version+'</td>'+
      '<td class="num">'+(r.version_count==null?'—':r.version_count)+'</td>'+
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
    '<input type="text" class="tin fname" placeholder="目标字段名" value="'+
    escHtml(target||'')+'">'+
    '<select class="tin fxform" title="入库时应用的转换（暂存值保持不变）">'+
      '<option value="">无转换</option>'+
      '<option value="trim">trim</option>'+
      '<option value="trim,number">trim+number</option>'+
    '</select>'+
    '<span class="fdest"></span>'+
    '<button type="button" class="btn mini danger fdel">删</button>';
  frows.appendChild(div);
  fillCol(div,col);
  div.querySelector('.fxform').value=fx||'';
  div.querySelector('.fcol').onchange=function(){syncIdx(div);};
  div.querySelector('.fname').addEventListener('input',updateDestHints);
  div.querySelector('.fdel').onclick=function(){div.remove();};
  updateDestHints();
}
/* ---- 「这些字段去了哪」：编辑抽屉字段行尾部
   显示该字段在入库规则里的目标列。本规则没有任何入库规则时**不显示**
   （避免逐行刷「未配置」噪音）；有规则时按字段显示 去向/未配去向。 ---- */
var destMap=null;   // null=本规则未查/新建；{field:[{表.列}…]}=已加载
var destHasRules=false;
function loadDestHints(id){
  destMap=null; destHasRules=false;
  api('GET','/api/load/tables').then(function(j){
    var rules=(j.items||[]).filter(function(m){return m.rule_id===id;});
    if(!rules.length){ destMap={}; updateDestHints(); return; }
    destHasRules=true;
    Promise.all(rules.map(function(m){
      return api('GET','/api/load/tables/'+m.id).catch(function(){return null;});
    })).then(function(details){
      var map={};
      details.forEach(function(d){
        if(!d) return;
        (d.fields||[]).forEach(function(f){
          (map[f.rule_field]=map[f.rule_field]||[]).push(
            d.target_table+'.'+f.target_column);
        });
      });
      destMap=map; updateDestHints();
    });
  }).catch(function(){});
}
function updateDestHints(){
  if(!destMap) return;
  Array.prototype.forEach.call(frows.children,function(div){
    var h=div.querySelector('.fdest');
    if(!h) return;
    var f=(div.querySelector('.fname').value||'').trim();
    if(!f){ h.textContent=''; h.title=''; return; }
    if(!destHasRules){
      h.textContent='—';
      h.title='本规则尚未配置入库规则；在「入库」页配置后，这里会显示每个字段写入哪张表哪一列';
      h.className='fdest'; return;
    }
    var d=destMap[f]||[];
    if(!d.length){
      h.textContent='未配去向'; h.title='该字段还没有出现在任何入库规则的目标列中';
      h.className='fdest'; return;
    }
    var uniq=[], seen={};
    d.forEach(function(x){ if(!seen[x]){seen[x]=1;uniq.push(x);} });
    h.textContent=uniq.join(' / '); h.title='入库规则中的目标列';
    h.className='fdest has';
  });
}
function refreshCols(){
  Array.prototype.forEach.call(frows.children,function(div){
    fillCol(div,readCol(div));
  });
}
/* 选定参考表后：字段行为空（或仅剩未填过的预置空行）时自动按源列整表
   填充（列名＝字段名＝源列，用户删掉不要的、改名即可）；
   任一行已填过内容时不覆盖手工工作。 */
function autofillRows(){
  var keys=currentKeys();
  if(!keys.length) return;
  var dirty=Array.prototype.some.call(frows.children,function(div){
    return (div.querySelector('.fname').value||'').trim()!=='' ||
      readCol(div)!==null ||
      div.querySelector('.fxform').value!=='';
  });
  if(dirty) return;
  frows.innerHTML='';
  keys.forEach(function(k){ addRow(k,{name:k}); });
}
document.getElementById('addfield').onclick=function(){addRow('',null);};

/* ---- 参考文件 ---- */
function loadRefs(){
  refsel.innerHTML='<option value="">不使用参考（手动填写源表）</option>';
  api('GET','/api/tasks').then(function(j){
    (j.items||[]).forEach(function(t){
      (t.files||[]).forEach(function(f){
        if(!f.task_file_id) return;
        if(['to_review','to_load','loading','loaded'].indexOf(f.state)<0)
          return;
        var o=document.createElement('option');
        o.value=t.task_id+':'+f.task_file_id;
        o.textContent='#'+t.task_id+' · '+f.name;
        refsel.appendChild(o);
      });
    });
  }).catch(function(){
    refhint.textContent='参考列表暂不可用（平台库未连接），可手动填写源表。';
  });
}
function manualMode(hint){
  cands=null; tblsel.disabled=true;
  tblsel.innerHTML='<option value="">—</option>';
  tmanual.hidden=false;
  refhint.textContent=hint||'';
  refreshCols();
}
refsel.onchange=function(){
  var v=refsel.value;
  if(!v){manualMode();return;}
  var p=v.split(':');
  refhint.textContent='正在加载参考…';
  api('GET','/api/tasks/'+p[0]+'/parse?file='+p[1]).then(function(doc){
    cands=candidates(doc);
    if(!cands.length){manualMode('该文件未解析出表格，请手动填写源表。');return;}
    tblsel.innerHTML=cands.map(function(c,i){
      var head=(c.t.headers||[]).slice(0,4).join(' / ');
      return '<option value="'+i+'">#'+i+' · '+c.scope+' · '+
        escHtml(head||'（无表头）')+'</option>';
    }).join('');
    tblsel.disabled=false; tmanual.hidden=true;
    var want=(pendingTable&&typeof pendingTable.index==='number')?pendingTable.index:0;
    tblsel.value=String(want>=0&&want<cands.length?want:0);
    refhint.textContent='共 '+cands.length+' 张候选表。';
    autofillRows(); refreshCols();
  }).catch(function(e){
    manualMode('参考加载失败：'+e.message+'，可手动填写源表。');
  });
};
tblsel.onchange=function(){autofillRows();refreshCols();};

/* ---- 编辑抽屉 ---- */
function closeEditor(){edit.hidden=true;cur=null;}
document.getElementById('eclose').onclick=closeEditor;
edit.addEventListener('click',function(e){if(e.target===edit)closeEditor();});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'&&!edit.hidden) closeEditor();
});

function loadVersions(id){
  api('GET','/api/extract-rules/'+id+'/versions').then(function(j){
    var list=j.items||j.versions||j;
    if(!Array.isArray(list)) list=[];
    document.getElementById('verlist').innerHTML=list.map(function(v){
      return '<div class="vrow"><span class="mono">v'+v.version+'</span>'+
        '<span class="msg">'+fmtTime(v.created_at)+'</span>'+
        '<span class="spacer"></span>'+
        (v.is_current?'<span class="badge green">当前</span>':
          '<button type="button" class="btn mini ghost" data-setcur="'+
          v.version+'">设为当前</button>')+
        '</div>';
    }).join('')||'<div class="sthint">无版本</div>';
  }).catch(function(e){
    document.getElementById('verlist').innerHTML=
      '<div class="sthint">版本历史加载失败：'+escHtml(e.message)+'</div>';
  });
}
document.getElementById('verlist').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-setcur]'):null;
  if(!b||cur==null) return;
  var v=Number(b.getAttribute('data-setcur'));
  api('PATCH','/api/extract-rules/'+cur,{current_version:v}).then(function(){
    document.getElementById('everbadge').innerHTML=
      '<span class="badge green">v'+v+'</span>';
    loadVersions(cur); load();
    showOk('已将 v'+v+' 设为当前版本（旧任务仍引用各自快照，不受影响）。');
  }).catch(function(e2){emsg.textContent=e2.message;});
});

function openEditor(id){
  cur=id; cands=null; pendingTable=null;
  emsg.textContent=''; frows.innerHTML='';
  setMode('simple'); jsonspec.value='';
  tplKind.value=''; renderTplForm();
  refsel.value=''; tindex.value=''; tkw.value='';
  manualMode();
  verlist.hidden=true; vertoggle.textContent='展开';
  document.getElementById('ok').hidden=true;
  if(id==null){
    document.getElementById('etitle').textContent='新建规则';
    document.getElementById('everbadge').innerHTML='';
    ename.value=''; edesc.value=''; origName=''; origDesc='';
    delbtn.hidden=true;
    loadDestHints(null);
    document.getElementById('versec').hidden=true;
    addRow('',null);
    edit.hidden=false; loadRefs();
    return;
  }
  api('GET','/api/extract-rules/'+id).then(function(j){
    document.getElementById('etitle').textContent='编辑规则 #'+id;
    document.getElementById('everbadge').innerHTML=
      '<span class="badge green">v'+j.current_version+'</span>';
    ename.value=j.name||''; edesc.value=j.description||'';
    origName=j.name||''; origDesc=j.description||'';
    var mp=j.mapping_json||{};
    if(mp.spec_version===2){
      setMode('json'); jsonspec.value=JSON.stringify(mp,null,2);
    }else{
      pendingTable=mp.table||null;
      if(pendingTable){
        if(typeof pendingTable.index==='number') tindex.value=pendingTable.index;
        if(pendingTable.header_contains) tkw.value=pendingTable.header_contains;
      }
      var fs=mp.fields||[];
      var fxMap={};
      ((j.transform_json||{}).fields||[]).forEach(function(f){
        fxMap[f.target]=(f.apply||[]).join(',');
      });
      if(fs.length) fs.forEach(function(f){addRow(f.target,f.column,fxMap[f.target]);});
      else addRow('',null);
    }
    delbtn.hidden=false;
    document.getElementById('versec').hidden=false;
    loadVersions(id);
    loadDestHints(id);
    edit.hidden=false; loadRefs();
  }).catch(function(e){showErr(e.message);});
}

/* ---- 保存 / 删除 ---- */
savebtn.onclick=function(){
  emsg.textContent='';
  var name=ename.value.trim();
  if(!name){emsg.textContent='规则名不能为空';return;}
  var schema, mapping, transform;
  if(mode==='json'){
    var parsed;
    try{ parsed=JSON.parse(jsonspec.value); }
    catch(e){ emsg.textContent='JSON 语法错误：'+e.message; return; }
    if(!parsed || typeof parsed!=='object' || Array.isArray(parsed)){
      emsg.textContent='mapping_json 须为 JSON 对象'; return;
    }
    if(parsed.spec_version!==2){
      emsg.textContent='高级 JSON 模式要求 spec_version 为 2'; return;
    }
    schema={fields:(parsed.fields||[]).filter(function(f){
      return f && f.target;
    }).map(function(f){return {name:f.target,type:'text'};})};
    mapping=parsed; transform=null;
  }else{
    var fields=[], seen={}, err=null, xf=[];
    Array.prototype.forEach.call(frows.children,function(div){
      if(err) return;
      var t=div.querySelector('.fname').value.trim();
      if(!t){err='目标字段名不能为空';return;}
      if(seen[t]){err='字段名重复：'+t;return;}
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
    mapping={table:table,fields:fields};
    transform=xf.length?{fields:xf}:null;
  }
  var desc=edesc.value.trim();
  savebtn.disabled=true;
  var p;
  if(cur==null){
    p=api('POST','/api/extract-rules',
          {name:name,description:desc||null,schema:schema,mapping:mapping,
           transform:transform});
  }else{
    var patch={};
    if(name!==origName) patch.name=name;
    if(desc!==origDesc) patch.description=desc;
    p=(Object.keys(patch).length?api('PATCH','/api/extract-rules/'+cur,patch):
        Promise.resolve()).then(function(){
      return api('POST','/api/extract-rules/'+cur+'/versions',
                 {schema:schema,mapping:mapping,transform:transform});
    });
  }
  p.then(function(){
    showOk('已保存「'+name+'」新版本快照（当前版本前移，旧任务不受影响）。');
    return load();
  }).then(function(){
    if(cur==null){
      var it=items.filter(function(r){return r.name===name;})[0];
      if(it) openEditor(it.id);
    }else{
      origName=name; origDesc=desc;
      loadVersions(cur);
      api('GET','/api/extract-rules/'+cur).then(function(j){
        document.getElementById('everbadge').innerHTML=
          '<span class="badge green">v'+j.current_version+'</span>';
      }).catch(function(){});
    }
  }).catch(function(e){emsg.textContent=e.message;})
   .then(function(){savebtn.disabled=false;});
};

function delRule(id,name){
  if(!window.confirm('删除规则「'+name+'」及其全部版本？')) return;
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

load();