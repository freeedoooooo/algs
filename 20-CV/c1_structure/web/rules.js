/* web/rules.js — 入库映射：左业务库列表 · 右入库映射列表。
   一个业务库＝一个库（明文配置）；规则＝业务库×表×抽取规则绑定，字段行编辑。
   契约见 （用词改齐）。 */
var dss=[], maps=[], tpls=[], cols=[];
var curDs=null, editDs=null, editLt=null, ltLocked=false, tplVersionId=null;
var mapPage=1, mapSize=getListPer();
var pgMap=bindPager(document.getElementById('mappager'),
  function(d){ mapPage+=d; renderMaps(); },
  function(n){ mapSize=n; mapPage=1; renderMaps(); });
var dds=document.getElementById('dds'), dmap=document.getElementById('dmap');
var mptpl=document.getElementById('mptpl'), mptable=document.getElementById('mptable');
var mpmode=document.getElementById('mpmode'), mprows=document.getElementById('mprows');
var mpmsg=document.getElementById('mpmsg'), dsmsg=document.getElementById('dsmsg');

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
function dsById(id){
  for(var i=0;i<dss.length;i++) if(dss[i].id===id) return dss[i];
  return null;
}

/* ---- 左：业务库列表 ---- */
function renderDs(){
  document.getElementById('dslist').innerHTML=dss.map(function(d,i){
    return '<div class="dsitem'+(d.id===curDs?' active':'')+'" data-ds="'+d.id+'">'+
      '<div class="dsmain"><b>'+(i+1)+'. '+escHtml(d.name)+'</b>'+
        '<span class="badge">'+d.table_count+' 规则</span></div>'+
      '<div class="dsmeta mono">'+escHtml('ID '+d.id+' · '+d.host+':'+d.port+'/'+d.db_name)+'</div>'+
      '<div class="dsops">'+
        '<button type="button" class="linkbtn" data-test="'+d.id+'">测试</button>'+
        '<button type="button" class="linkbtn" data-editds="'+d.id+'">编辑</button>'+
        '<button type="button" class="linkbtn danger" data-delds="'+d.id+
          '" data-name="'+escHtml(d.name)+'">删除</button>'+
      '</div></div>';
  }).join('');
  document.getElementById('dsempty').hidden=dss.length>0;
}
/* ---- 右：所选业务库的入库映射列表 ---- */
function renderMaps(){
  var d=dsById(curDs);
  document.getElementById('maptitle').textContent='业务表';
  document.getElementById('newmap').disabled=!d;
  var list=maps.filter(function(m){return m.datasource_id===curDs;});
  var info=pageSlice(list,mapPage,mapSize);
  mapPage=info.page;
  document.getElementById('mapnone').hidden=!!d;
  document.getElementById('maptable').hidden=!d||!list.length;
  document.getElementById('mapempty').hidden=!d||list.length>0;
  document.getElementById('maprows').innerHTML=info.rows.map(function(m,i){
    var bk=m.business_keys||[];
    return '<tr>'+
      '<td class="seq">'+seqNo(info,i)+'</td>'+
      '<td class="mono">'+m.id+'</td>'+
      '<td class="left"><a class="linkbtn" href="/dashboard?ds='+encodeURIComponent(m.datasource_id)+
        '&table='+encodeURIComponent(m.target_table)+
        '" title="查看该表业务数据">'+escHtml(m.target_table)+'</a></td>'+
      '<td class="left">'+escHtml(m.tpl_name||'—')+'</td>'+
      '<td>'+escHtml(modeLabel(m.write_mode))+'</td>'+
      '<td class="num">'+m.field_count+'</td>'+
      '<td class="left"><span class="mono">'+escHtml(bk.join(', ')||'—')+'</span></td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-editmap="'+m.id+'">编辑</button>'+
        '<button type="button" class="linkbtn danger" data-delmap="'+m.id+
          '" data-name="'+escHtml(m.tpl_name+' → '+m.target_table)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  pgMap.render(info);
}
function loadAll(keepSel){
  return Promise.all([
    api('GET','/api/load/datasources'),
    api('GET','/api/load/tables'),
    api('GET','/api/extract-rules')
  ]).then(function(res){
    dss=res[0].items||[]; maps=res[1].items||[]; tpls=res[2].items||[];
    if(!keepSel||!dsById(curDs)) curDs=dss.length?dss[0].id:null;
    renderDs(); renderMaps();
    document.getElementById('err').hidden=true;
  }).catch(function(e){
    dss=[]; maps=[]; tpls=[]; curDs=null; renderDs(); renderMaps();
    showErr('平台库未连接：入库映射暂不可用（'+e.message+'）');
  });
}

/* ---- 业务库：选中 / 试连 / 编辑 / 删除 ---- */
document.getElementById('dslist').addEventListener('click',function(e){
  var t=e.target;
  var test=t.closest?t.closest('[data-test]'):null;
  if(test){
    var tid=test.getAttribute('data-test');
    test.disabled=true; test.textContent='测试中…';
    api('POST','/api/load/datasources/'+tid+'/test').then(function(j){
      showOk('连接成功：'+j.detail);
    }).catch(function(e2){ showErr('连接失败：'+e2.message); })
     .then(function(){ test.disabled=false; test.textContent='测试'; });
    return;
  }
  var ed=t.closest?t.closest('[data-editds]'):null;
  if(ed){ openDs(dsById(Number(ed.getAttribute('data-editds')))); return; }
  var del=t.closest?t.closest('[data-delds]'):null;
  if(del){
    var did=del.getAttribute('data-delds'), name=del.getAttribute('data-name');
    if(!window.confirm('删除业务库「'+name+'」？')) return;
    api('DELETE','/api/load/datasources/'+did).then(function(){
      showOk('已删除业务库「'+name+'」。');
      if(curDs===Number(did)) curDs=null;
      loadAll(true);
    }).catch(function(e2){ showErr(e2.message); });
    return;
  }
  var item=t.closest?t.closest('[data-ds]'):null;
  if(item){ curDs=Number(item.getAttribute('data-ds')); mapPage=1; renderDs(); renderMaps(); }
});

/* ---- 业务库抽屉 ---- */
var DS_FIELDS=['dsname','dshost','dsport','dsuser','dspass','dsdb'];
function openDs(d){
  editDs=d||null;
  document.getElementById('dstitle').textContent=d?'编辑业务库':'新建业务库';
  document.getElementById('dsname').value=d?d.name:'';
  document.getElementById('dshost').value=d?d.host:'';
  document.getElementById('dsport').value=d?d.port:'3306';
  document.getElementById('dsuser').value=d?d.user:'';
  document.getElementById('dspass').value=d?d.password:'';
  document.getElementById('dsdb').value=d?d.db_name:'';
  var locked=!!(d&&d.table_count>0);
  ['dshost','dsport','dsdb'].forEach(function(id){
    document.getElementById(id).disabled=locked;
  });
  document.getElementById('dslock').hidden=!locked;
  dsmsg.textContent=''; dds.hidden=false;
}
function closeDs(){ dds.hidden=true; }
document.getElementById('newds').onclick=function(){ openDs(null); };
document.getElementById('dsclose').onclick=closeDs;
dds.addEventListener('click',function(e){ if(e.target===dds) closeDs(); });
document.getElementById('dssave').onclick=function(){
  dsmsg.textContent='';
  var v={};
  DS_FIELDS.forEach(function(id){ v[id]=document.getElementById(id).value.trim(); });
  if(!v.dsname){ dsmsg.textContent='名称不能为空'; return; }
  if(!editDs&&(!v.dshost||!v.dsdb)){ dsmsg.textContent='主机与库名不能为空'; return; }
  var body={name:v.dsname,user:v.dsuser,password:v.dspass};
  if(!editDs||!editDs.table_count){
    body.host=v.dshost; body.port=v.dsport; body.db_name=v.dsdb;
  }
  var p=editDs?api('PATCH','/api/load/datasources/'+editDs.id,body)
              :api('POST','/api/load/datasources',body);
  p.then(function(){
    closeDs(); showOk('已保存业务库「'+v.dsname+'」。');
    return loadAll(true);
  }).catch(function(e){ dsmsg.textContent=e.message; });
};

/* ---- 入库映射抽屉 ---- */
/* 字段自动对齐（纯前端）：规范化全等自动选中，
   ✓=已对齐（灰底自动可改），？=待确认；只填当前为空的行，不动手动/预置值。 */
function autoMatchRows(){
  if(ltLocked||!cols.length) return;
  var byNorm={};
  cols.forEach(function(c){ var k=normKey(c.name); if(!(k in byNorm)) byNorm[k]=c.name; });
  Array.prototype.forEach.call(mprows.children,function(div){
    var sel=div.querySelector('.fcol');
    if(!sel||sel.value) return;
    var fname=div.querySelector('.fname').value;
    var hit=byNorm[normKey(fname)];
    if(hit){ sel.value=hit; sel.setAttribute('data-auto','1'); }
  });
}
function recomputeMatchBar(){
  var rows=mprows.querySelectorAll('.frow'), M=rows.length, X=0, A=0;
  Array.prototype.forEach.call(rows,function(div){
    var sel=div.querySelector('.fcol'), badge=div.querySelector('.mbadge');
    if(sel.value){ X++; if(sel.getAttribute('data-auto')==='1') A++; }
    if(badge){
      badge.className='mbadge '+(sel.value?'ok':'warn');
      badge.textContent=sel.value?'✓':'？';
      badge.title=sel.value?(sel.getAttribute('data-auto')==='1'?'已自动对齐，可修改':'已对齐'):'待选择目标列';
    }
  });
  var bar=document.getElementById('mpmatch');
  if(!bar) return;
  if(!M){ bar.textContent=''; return; }
  var K=M-X;
  bar.textContent=A?('已自动匹配 '+A+'/'+M+' 个字段'+(K?'，剩 '+K+' 个待确认':'，全部匹配')):
    (K?('剩 '+K+'/'+M+' 个字段待确认'):(M+' 个字段已全部对齐'));
}
function fillCols(){
  Array.prototype.forEach.call(mprows.children,function(div){
    var sel=div.querySelector('.fcol'), keep=sel.value||sel.getAttribute('data-col')||'';
    sel.innerHTML='<option value="">选择目标列</option>'+
      cols.map(function(c){
        return '<option value="'+escHtml(c.name)+'">'+escHtml(c.name)+
          '（'+escHtml(c.type)+'）</option>';
      }).join('');
    if(keep&&cols.some(function(c){return c.name===keep;})) sel.value=keep;
    sel.disabled=ltLocked;
  });
  autoMatchRows();
  recomputeMatchBar();
}
function syncBk(){
  var ins=mpmode.value==='insert';
  Array.prototype.forEach.call(mprows.querySelectorAll('.fbk'),function(c){
    if(ins) c.checked=false;
    c.disabled=ins||ltLocked;
  });
}
function buildRows(names,preset,editable){
  mprows.innerHTML='';
  names.forEach(function(f){
    var p=(preset||{})[f]||{};
    var div=document.createElement('div');
    div.className='frow';
    div.innerHTML='<input type="text" class="tin fname"'+
      (editable?'':' readonly')+' value="'+escHtml(f)+'">'+
      '<select class="tin fcol" data-col="'+escHtml(p.col||'')+'"></select>'+
      '<span class="mbadge"></span>'+
      '<label class="bklab"><input type="checkbox" class="fbk"'+
      (p.bk?' checked':'')+'>去重依据</label>';
    mprows.appendChild(div);
  });
  fillCols(); syncBk();
  Array.prototype.forEach.call(mprows.querySelectorAll('.fname'),function(i){
    i.disabled=ltLocked;
  });
}
function addManualRow(){
  var div=document.createElement('div');
  div.className='frow';
  div.innerHTML='<input type="text" class="tin fname" placeholder="抽取输出字段名">'+
    '<select class="tin fcol" data-col=""></select>'+
    '<span class="mbadge"></span>'+
    '<label class="bklab"><input type="checkbox" class="fbk">去重依据</label>';
  mprows.appendChild(div);
  fillCols(); syncBk();
  div.querySelector('.fname').focus();
}
document.getElementById('mpaddfield').onclick=function(){
  if(ltLocked) return;
  if(!mptable.value){ mpmsg.textContent='请先选择目标表'; return; }
  mpmsg.textContent=''; addManualRow();
};
function loadTables(){
  cols=[]; mptable.disabled=true;
  mptable.innerHTML='<option value="">加载中…</option>';
  document.getElementById('mpthint').textContent='';
  api('GET','/api/load/datasources/'+curDs+'/tables').then(function(j){
    var ts=j.items||[];
    mptable.innerHTML='<option value="">选择目标表</option>'+
      ts.map(function(t){return '<option value="'+escHtml(t)+'">'+escHtml(t)+'</option>';}).join('');
    mptable.disabled=ltLocked;
    document.getElementById('mpthint').textContent='共 '+ts.length+' 张表（仅读取表结构，不做修改）。';
  }).catch(function(e){
    mptable.innerHTML='<option value="">加载失败</option>';
    document.getElementById('mpthint').textContent='目标表加载失败：'+e.message;
  });
}
function loadColumns(table,after){
  cols=[]; fillCols();
  api('GET','/api/load/datasources/'+curDs+'/columns?table='+
      encodeURIComponent(table)).then(function(j){
    cols=j.items||[]; fillCols();
    if(after) after();
  }).catch(function(e){
    document.getElementById('mpthint').textContent='目标列加载失败：'+e.message;
  });
}
function loadTplFields(){
  mprows.innerHTML=''; recomputeMatchBar(); tplVersionId=null;
  if(!mptpl.value){
    document.getElementById('mpthint').textContent='未选择参考规则；可手动添加字段。';
    return;
  }
  api('GET','/api/extract-rules/'+mptpl.value).then(function(j){
    tplVersionId=j.current_version_id||null;
    var sj=j.schema_json;
    var fs=(sj&&typeof sj==='object'&&!Array.isArray(sj)&&sj.fields)||[];
    var names=fs.map(function(f){return f.name;}).filter(Boolean);
    if(!names.length){
      mprows.innerHTML='<div class="sthint">该规则无固定目标字段（原始透传），不支持入库。请选择固定字段抽取规则。</div>';
      return;
    }
    buildRows(names,null);
  }).catch(function(e){
    mprows.innerHTML='<div class="sthint">规则字段加载失败：'+escHtml(e.message)+'</div>';
  });
}
function openMap(lt){
  editLt=lt||null;
  ltLocked=!!(lt&&lt.file_refs>0);
  var d=dsById(curDs);
  document.getElementById('mptitle').textContent=lt?'编辑映射':'新建映射';
  document.getElementById('mpds').value=d?(d.name+' · '+d.host+':'+d.port+'/'+d.db_name):'';
  tplVersionId=lt?(lt.rule_version_id||null):null;
  mptpl.innerHTML='<option value="">不使用参考规则（手动配置）</option>'+
    tpls.map(function(t){
      return '<option value="'+t.id+'">'+escHtml(t.name)+' v'+t.current_version+'</option>';
    }).join('');
  mpmode.value=lt?lt.write_mode:'upsert';
  mpmode.disabled=ltLocked;
  mptpl.disabled=ltLocked||!!lt;
  document.getElementById('mplock').hidden=!ltLocked;
  document.getElementById('mpsave').disabled=ltLocked;
  mpmsg.textContent=''; cols=[]; mprows.innerHTML=''; recomputeMatchBar();
  document.getElementById('mpthint').textContent='';
  if(lt){
    mptpl.value=lt.rule_id?String(lt.rule_id):'';
    mptable.innerHTML='<option value="'+escHtml(lt.target_table)+'">'+
      escHtml(lt.target_table)+'</option>';
    mptable.disabled=true;
    var preset={};
    (lt.fields||[]).forEach(function(f){
      preset[f.rule_field]={col:f.target_column,bk:!!f.is_business_key};
    });
    var names=(lt.fields||[]).map(function(f){return f.rule_field;});
    loadColumns(lt.target_table,function(){ buildRows(names,preset,!ltLocked); });
  }else{
    mptable.innerHTML='<option value="">选择目标表</option>';
    loadTables(); addManualRow();
  }
  dmap.hidden=false;
}
function closeDmap(){ dmap.hidden=true; }
document.getElementById('newmap').onclick=function(){ if(curDs) openMap(null); };
document.getElementById('mpclose').onclick=closeDmap;
dmap.addEventListener('click',function(e){ if(e.target===dmap) closeDmap(); });
document.addEventListener('keydown',function(e){
  if(e.key!=='Escape') return;
  if(!dds.hidden) closeDs();
  if(!dmap.hidden) closeDmap();
});
mptpl.onchange=loadTplFields;
mptable.onchange=function(){ if(mptable.value) loadColumns(mptable.value); };
mpmode.onchange=syncBk;
/* 手动改选＝取消自动标记，徽标与计数条同步刷新 */
mprows.addEventListener('change',function(e){
  if(e.target&&e.target.classList&&e.target.classList.contains('fcol')){
    e.target.removeAttribute('data-auto');
    recomputeMatchBar();
  }
});

document.getElementById('mpsave').onclick=function(){
  mpmsg.textContent='';
  if(!editLt&&!mptable.value){ mpmsg.textContent='请选择目标表'; return; }
  var rows=mprows.querySelectorAll('.frow');
  if(!rows.length){ mpmsg.textContent='请至少添加一个字段'; return; }
  var fields=[], seen={}, err=null;
  Array.prototype.forEach.call(rows,function(div){
    if(err) return;
    var f=div.querySelector('.fname').value.trim();
    var c=div.querySelector('.fcol').value;
    if(!f){ err='请填写抽取输出字段名'; return; }
    if(!c){ err='字段「'+f+'」尚未选择目标列'; return; }
    if(seen[c]){ err='多个字段指向同一目标列：'+c; return; }
    seen[c]=1;
    fields.push({rule_field:f,target_column:c,
                 is_business_key:div.querySelector('.fbk').checked?1:0});
  });
  if(err){ mpmsg.textContent=err; return; }
  if(mpmode.value!=='insert'&&!fields.some(function(f){return f.is_business_key;})){
    mpmsg.textContent='「'+modeLabel(mpmode.value)+'」须至少选一个去重依据'; return;
  }
  var snapshot={schema_version:1,
    rule_id:mptpl.value?Number(mptpl.value):null,
    rule_version_id:tplVersionId||null,
    fields:fields.map(function(f){return {name:f.rule_field,type:'text'};})};
  var p=editLt
    ?api('PATCH','/api/load/tables/'+editLt.id,
         {write_mode:mpmode.value,fields:fields,
          rule_version_id:tplVersionId||null,snapshot:snapshot})
    :api('POST','/api/load/tables',
         {datasource_id:curDs,rule_id:mptpl.value?Number(mptpl.value):null,
          rule_version_id:tplVersionId||null,
          target_table:mptable.value,write_mode:mpmode.value,
          fields:fields,snapshot:snapshot});
  p.then(function(){
    closeDmap(); showOk('已保存入库映射（'+(editLt?editLt.target_table:mptable.value)+
      ' · '+modeLabel(mpmode.value)+'）。');
    return loadAll(true);
  }).catch(function(e){ mpmsg.textContent=e.message; });
};
document.getElementById('maprows').addEventListener('click',function(e){
  var t=e.target;
  var ed=t.closest?t.closest('[data-editmap]'):null;
  if(ed){
    api('GET','/api/load/tables/'+ed.getAttribute('data-editmap'))
      .then(openMap).catch(function(e2){ showErr(e2.message); });
    return;
  }
  var del=t.closest?t.closest('[data-delmap]'):null;
  if(!del) return;
  var id=del.getAttribute('data-delmap'), name=del.getAttribute('data-name');
  if(!window.confirm('删除入库映射「'+name+'」？')) return;
  api('DELETE','/api/load/tables/'+id).then(function(){
    showOk('已删除入库映射。'); loadAll(true);
  }).catch(function(e2){ showErr(e2.message); });
});

loadAll(false);