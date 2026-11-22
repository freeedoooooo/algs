/* web/templates.js — 模板管理：列表＋编辑抽屉（结构化字段行
   表单＋参考文件预览辅助选表选列）＋版本历史。契约见 design-p1b-templates.md §二。 */
var items=[], cur=null, origName='', origDesc='', cands=null, pendingTable=null, page=1;
var rows=document.getElementById('rows'), empty=document.getElementById('empty');
var pg=bindPager(document.getElementById('pager'),function(d){ page+=d; render(); });
var edit=document.getElementById('edit');
var ename=document.getElementById('ename'), edesc=document.getElementById('edesc');
var refsel=document.getElementById('refsel'), refhint=document.getElementById('refhint');
var tblsel=document.getElementById('tblsel'), tmanual=document.getElementById('tmanual');
var tindex=document.getElementById('tindex'), tkw=document.getElementById('tkw');
var frows=document.getElementById('frows'), emsg=document.getElementById('emsg');
var savebtn=document.getElementById('savebtn'), delbtn=document.getElementById('delbtn');

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
  var info=pageSlice(list,page);
  page=info.page;
  rows.innerHTML=info.rows.map(function(r){
    return '<tr>'+
      '<td><b>'+escHtml(r.name)+'</b></td>'+
      '<td><span class="desc" title="'+escHtml(r.description||'')+'">'+
        escHtml(r.description||'—')+'</span></td>'+
      '<td class="num">v'+r.current_version+'</td>'+
      '<td class="num">'+(r.version_count==null?'—':r.version_count)+'</td>'+
      '<td class="num">'+fmtTime(r.updated_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-edit="'+r.id+'">编辑</button>'+
        '<button type="button" class="linkbtn" data-ver="'+r.id+'">版本</button>'+
        '<button type="button" class="linkbtn danger" data-del="'+r.id+
        '" data-name="'+escHtml(r.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  empty.hidden=list.length>0;
}
function load(){
  return api('GET','/api/templates').then(function(j){
    items=j.items||[]; render();
    document.getElementById('err').hidden=true;
  }).catch(function(e){
    items=[]; render();
    showErr('平台库未连接：模板目录暂不可用（'+e.message+'）');
  });
}
document.getElementById('q').addEventListener('input',function(){ page=1; render(); });
rows.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-edit],[data-ver],[data-del]'):null;
  if(!b) return;
  if(b.hasAttribute('data-del')){
    delTemplate(Number(b.getAttribute('data-del')),b.getAttribute('data-name'));
    return;
  }
  var id=Number(b.getAttribute('data-edit')||b.getAttribute('data-ver'));
  openEditor(id,b.hasAttribute('data-ver'));
});
document.getElementById('newbtn').onclick=function(){openEditor(null,false);};

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
  div.innerHTML='<input type="text" class="tin fname" placeholder="目标字段名" value="'+
    escHtml(target||'')+'">'+
    '<select class="tin fcol"></select>'+
    '<input type="number" class="tin fidx" min="0" placeholder="列序号" hidden>'+
    '<select class="tin fxform" title="入库时转换（暂存值保真不动）">'+
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
document.getElementById('addfield').onclick=function(){addRow('',null);};

/* ---- 参考文件 ---- */
function loadRefs(){
  refsel.innerHTML='<option value="">不用参考（手填源表）</option>';
  api('GET','/api/tasks').then(function(j){
    (j.items||[]).forEach(function(t){
      (t.files||[]).forEach(function(f){
        if(!f.task_file_id) return;
        if(f.state!=='previewed'&&f.state!=='loaded'&&f.state!=='reviewed') return;
        var o=document.createElement('option');
        o.value=t.task_id+':'+f.task_file_id;
        o.textContent='#'+t.task_id+' · '+f.name;
        refsel.appendChild(o);
      });
    });
  }).catch(function(){
    refhint.textContent='参考列表暂不可用（平台库未连接），可手填源表。';
  });
}
function manualMode(hint){
  cands=null; tblsel.disabled=true;
  tblsel.innerHTML='<option value="">—</option>';
  tmanual.hidden=false;
  if(hint) refhint.textContent=hint;
  refreshCols();
}
refsel.onchange=function(){
  var v=refsel.value;
  if(!v){manualMode('选一个已预览任务的文件，列出其候选源表与源列。');return;}
  var p=v.split(':');
  refhint.textContent='加载参考…';
  api('GET','/api/tasks/'+p[0]+'/extract?file='+p[1]).then(function(doc){
    cands=candidates(doc);
    if(!cands.length){manualMode('该文件未抽出表格，请手填源表。');return;}
    tblsel.innerHTML=cands.map(function(c,i){
      var head=(c.t.headers||[]).slice(0,4).join(' / ');
      return '<option value="'+i+'">#'+i+' · '+c.scope+' · '+
        escHtml(head||'（无表头）')+'</option>';
    }).join('');
    tblsel.disabled=false; tmanual.hidden=true;
    var want=(pendingTable&&typeof pendingTable.index==='number')?pendingTable.index:0;
    tblsel.value=String(want>=0&&want<cands.length?want:0);
    refhint.textContent='共 '+cands.length+' 张候选表（合并页表已跳过）。';
    refreshCols();
  }).catch(function(e){
    manualMode('参考加载失败：'+e.message+'，可手填源表。');
  });
};
tblsel.onchange=refreshCols;

/* ---- 编辑抽屉 ---- */
function closeEditor(){edit.hidden=true;cur=null;}
document.getElementById('eclose').onclick=closeEditor;
edit.addEventListener('click',function(e){if(e.target===edit)closeEditor();});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'&&!edit.hidden) closeEditor();
});

function loadVersions(id){
  api('GET','/api/templates/'+id+'/versions').then(function(j){
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
    }).join('')||'<div class="hint">无版本</div>';
  }).catch(function(e){
    document.getElementById('verlist').innerHTML=
      '<div class="hint">版本历史加载失败：'+escHtml(e.message)+'</div>';
  });
}
document.getElementById('verlist').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-setcur]'):null;
  if(!b||cur==null) return;
  var v=Number(b.getAttribute('data-setcur'));
  api('PATCH','/api/templates/'+cur,{current_version:v}).then(function(){
    document.getElementById('everbadge').innerHTML=
      '<span class="badge green">v'+v+'</span>';
    loadVersions(cur); load();
    showOk('已将 v'+v+' 设为当前版本（旧任务仍引用各自快照，不受影响）。');
  }).catch(function(e2){emsg.textContent=e2.message;});
});

function openEditor(id,focusVer){
  cur=id; cands=null; pendingTable=null;
  emsg.textContent=''; frows.innerHTML='';
  refsel.value=''; tindex.value=''; tkw.value='';
  manualMode('选一个已预览任务的文件，列出其候选源表与源列。');
  document.getElementById('ok').hidden=true;
  if(id==null){
    document.getElementById('etitle').textContent='新建模板';
    document.getElementById('everbadge').innerHTML='';
    ename.value=''; edesc.value=''; origName=''; origDesc='';
    delbtn.hidden=true;
    document.getElementById('versec').hidden=true;
    addRow('',null);
    edit.hidden=false; loadRefs();
    return;
  }
  api('GET','/api/templates/'+id).then(function(j){
    document.getElementById('etitle').textContent='编辑模板 #'+id;
    document.getElementById('everbadge').innerHTML=
      '<span class="badge green">v'+j.current_version+'</span>';
    ename.value=j.name||''; edesc.value=j.description||'';
    origName=j.name||''; origDesc=j.description||'';
    var mp=j.mapping_json||{};
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
    delbtn.hidden=false;
    document.getElementById('versec').hidden=false;
    loadVersions(id);
    edit.hidden=false; loadRefs();
    if(focusVer)
      document.getElementById('versec').scrollIntoView({block:'nearest'});
  }).catch(function(e){showErr(e.message);});
}

/* ---- 保存 / 删除 ---- */
savebtn.onclick=function(){
  emsg.textContent='';
  var name=ename.value.trim();
  if(!name){emsg.textContent='模板名不能为空';return;}
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
    emsg.textContent='至少一个字段；无需映射请用内置「原始透传」';return;
  }
  var table;
  if(cands&&!tblsel.disabled) table={index:Number(tblsel.value)};
  else if(tindex.value!=='') table={index:Number(tindex.value)};
  else if(tkw.value.trim()) table={header_contains:tkw.value.trim()};
  else{emsg.textContent='请选源表（参考文件，或手填序号 / 表头关键词）';return;}
  var schema={fields:fields.map(function(f){return {name:f.target,type:'text'};})};
  var mapping={table:table,fields:fields};
  var transform=xf.length?{fields:xf}:null;
  var desc=edesc.value.trim();
  savebtn.disabled=true;
  var p;
  if(cur==null){
    p=api('POST','/api/templates',
          {name:name,description:desc||null,schema:schema,mapping:mapping,
           transform:transform});
  }else{
    var patch={};
    if(name!==origName) patch.name=name;
    if(desc!==origDesc) patch.description=desc;
    p=(Object.keys(patch).length?api('PATCH','/api/templates/'+cur,patch):
        Promise.resolve()).then(function(){
      return api('POST','/api/templates/'+cur+'/versions',
                 {schema:schema,mapping:mapping,transform:transform});
    });
  }
  p.then(function(){
    showOk('已保存「'+name+'」新版本快照（当前版本前移，旧任务不受影响）。');
    return load();
  }).then(function(){
    if(cur==null){
      var it=items.filter(function(r){return r.name===name;})[0];
      if(it) openEditor(it.id,false);
    }else{
      origName=name; origDesc=desc;
      loadVersions(cur);
      api('GET','/api/templates/'+cur).then(function(j){
        document.getElementById('everbadge').innerHTML=
          '<span class="badge green">v'+j.current_version+'</span>';
      }).catch(function(){});
    }
  }).catch(function(e){emsg.textContent=e.message;})
   .then(function(){savebtn.disabled=false;});
};

function delTemplate(id,name){
  if(!window.confirm('删除模板「'+name+'」及其全部版本？')) return;
  api('DELETE','/api/templates/'+id).then(function(){
    if(cur===id) closeEditor();
    showOk('已删除模板「'+name+'」。');
    load();
  }).catch(function(e){
    if(cur===id&&!edit.hidden) emsg.textContent=e.message;
    else showErr(e.message);
  });
}
delbtn.onclick=function(){
  if(cur!=null) delTemplate(cur,ename.value.trim());
};

load();