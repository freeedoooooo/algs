/* extract_report/assets/load.js — 入库配置（P2）：目的地/映射双 panel＋抽屉。
   映射编辑器：选目的地→introspection 列目标表；选模板→字段行；目标列下拉
   来自 information_schema；业务键＝行勾选。契约见 design-p2-load.md §二/四。 */
var dests=[], maps=[], tpls=[], cols=[];
var ddest=document.getElementById('ddest'), dmap=document.getElementById('dmap');
var dmdest=document.getElementById('dmdest'), dmtpl=document.getElementById('dmtpl');
var dmtable=document.getElementById('dmtable'), dmmode=document.getElementById('dmmode');
var dmrows=document.getElementById('dmrows'), dmmsg=document.getElementById('dmmsg');
var ddmsg=document.getElementById('ddmsg');

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
var MODE_LABEL={upsert:'upsert',insert:'insert',update:'update'};

/* ---- 列表 ---- */
function renderDests(){
  document.getElementById('destrows').innerHTML=dests.map(function(d){
    return '<tr>'+
      '<td><b>'+escHtml(d.name)+'</b></td>'+
      '<td>'+escHtml(d.db_type)+'</td>'+
      '<td><code class="mono">'+escHtml(d.conn_ref)+'</code></td>'+
      '<td class="num">'+fmtTime(d.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn" data-test="'+d.id+'">测试连接</button>'+
        '<button type="button" class="linkbtn danger" data-deldest="'+d.id+
        '" data-name="'+escHtml(d.name)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  document.getElementById('destempty').hidden=dests.length>0;
}
function renderMaps(){
  document.getElementById('maprows').innerHTML=maps.map(function(m){
    var bk=m.business_key_json||[];
    return '<tr>'+
      '<td>'+escHtml(m.dest_name||'—')+'</td>'+
      '<td>'+escHtml(m.tpl_name||'—')+'</td>'+
      '<td><code class="mono">'+escHtml(m.target_table)+'</code></td>'+
      '<td>'+(MODE_LABEL[m.write_mode]||escHtml(m.write_mode))+'</td>'+
      '<td><span class="mono">'+escHtml(bk.join(', ')||'—')+'</span></td>'+
      '<td class="num">'+fmtTime(m.created_at)+'</td>'+
      '<td style="white-space:nowrap">'+
        '<button type="button" class="linkbtn danger" data-delmap="'+m.id+
        '" data-name="'+escHtml(m.tpl_name+' → '+m.target_table)+'">删除</button>'+
      '</td></tr>';
  }).join('');
  document.getElementById('mapempty').hidden=maps.length>0;
}
function loadAll(){
  return Promise.all([
    api('GET','/api/load/dests'),
    api('GET','/api/load/mappings'),
    api('GET','/api/templates')
  ]).then(function(res){
    dests=res[0].items||[]; maps=res[1].items||[]; tpls=res[2].items||[];
    renderDests(); renderMaps();
    document.getElementById('err').hidden=true;
  }).catch(function(e){
    dests=[]; maps=[]; tpls=[]; renderDests(); renderMaps();
    showErr('平台库未连接：入库配置暂不可用（'+e.message+'）');
  });
}

/* ---- 目的地 ---- */
document.getElementById('destrows').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-test],[data-deldest]'):null;
  if(!b) return;
  if(b.hasAttribute('data-test')){
    var id=b.getAttribute('data-test');
    b.disabled=true; b.textContent='测试中…';
    api('POST','/api/load/dests/'+id+'/test').then(function(j){
      showOk('连接成功：'+j.detail);
    }).catch(function(e2){ showErr('连接失败：'+e2.message); })
     .then(function(){ b.disabled=false; b.textContent='测试连接'; });
    return;
  }
  var did=b.getAttribute('data-deldest'), name=b.getAttribute('data-name');
  if(!window.confirm('删除目的地「'+name+'」？')) return;
  api('DELETE','/api/load/dests/'+did).then(function(){
    showOk('已删除目的地「'+name+'」。'); loadAll();
  }).catch(function(e2){ showErr(e2.message); });
});
document.getElementById('newdest').onclick=function(){
  document.getElementById('ddname').value='';
  document.getElementById('ddref').value='';
  ddmsg.textContent=''; ddest.hidden=false;
};
function closeDdest(){ ddest.hidden=true; }
document.getElementById('ddclose').onclick=closeDdest;
ddest.addEventListener('click',function(e){ if(e.target===ddest) closeDdest(); });
document.getElementById('ddsave').onclick=function(){
  ddmsg.textContent='';
  var name=document.getElementById('ddname').value.trim();
  var ref=document.getElementById('ddref').value.trim();
  if(!name){ ddmsg.textContent='名称不能为空'; return; }
  if(!ref){ ddmsg.textContent='凭据引用名不能为空'; return; }
  api('POST','/api/load/dests',{name:name,conn_ref:ref}).then(function(){
    closeDdest(); showOk('已登记目的地「'+name+'」（凭据只存引用名）。');
    return loadAll();
  }).catch(function(e){ ddmsg.textContent=e.message; });
};

/* ---- 映射抽屉 ---- */
function fillCols(){
  Array.prototype.forEach.call(dmrows.children,function(div){
    var sel=div.querySelector('.fcol'), keep=sel.value;
    sel.innerHTML='<option value="">选择目标列</option>'+
      cols.map(function(c){
        return '<option value="'+escHtml(c.name)+'">'+escHtml(c.name)+
          '（'+escHtml(c.type)+'）</option>';
      }).join('');
    if(keep&&cols.some(function(c){return c.name===keep;})) sel.value=keep;
  });
}
function syncBk(){
  var ins=dmmode.value==='insert';
  Array.prototype.forEach.call(dmrows.querySelectorAll('.fbk'),function(c){
    if(ins) c.checked=false;
    c.disabled=ins;
  });
}
function buildRows(fields){
  dmrows.innerHTML='';
  fields.forEach(function(f){
    var div=document.createElement('div');
    div.className='frow';
    div.innerHTML='<input type="text" class="tin fname" readonly value="'+
      escHtml(f)+'">'+
      '<select class="tin fcol"></select>'+
      '<label class="bklab"><input type="checkbox" class="fbk">业务键</label>';
    dmrows.appendChild(div);
  });
  fillCols(); syncBk();
}
function loadTables(){
  cols=[]; dmtable.disabled=true;
  dmtable.innerHTML='<option value="">加载中…</option>';
  document.getElementById('dmthint').textContent='';
  if(!dmdest.value){ dmtable.innerHTML='<option value="">先选目的地</option>'; return; }
  api('GET','/api/load/dests/'+dmdest.value+'/tables').then(function(j){
    var ts=j.items||[];
    dmtable.innerHTML='<option value="">选择目标表</option>'+
      ts.map(function(t){return '<option value="'+escHtml(t)+'">'+escHtml(t)+'</option>';}).join('');
    dmtable.disabled=false;
    document.getElementById('dmthint').textContent='共 '+ts.length+' 张表（只读 introspection）。';
  }).catch(function(e){
    dmtable.innerHTML='<option value="">加载失败</option>';
    document.getElementById('dmthint').textContent='目标表加载失败：'+e.message;
  });
}
function loadColumns(){
  cols=[]; fillCols();
  if(!dmdest.value||!dmtable.value) return;
  api('GET','/api/load/dests/'+dmdest.value+'/columns?table='+
      encodeURIComponent(dmtable.value)).then(function(j){
    cols=j.items||[]; fillCols();
  }).catch(function(e){
    document.getElementById('dmthint').textContent='目标列加载失败：'+e.message;
  });
}
function loadTplFields(){
  dmrows.innerHTML='';
  if(!dmtpl.value) return;
  api('GET','/api/templates/'+dmtpl.value).then(function(j){
    var sj=j.schema_json;
    var fs=(sj&&typeof sj==='object'&&!Array.isArray(sj)&&sj.fields)||[];
    var names=fs.map(function(f){return f.name;}).filter(Boolean);
    if(!names.length){
      dmrows.innerHTML='<div class="hint">该模板无固定目标字段（透传），不可入库。请选映射模板。</div>';
      return;
    }
    buildRows(names);
  }).catch(function(e){
    dmrows.innerHTML='<div class="hint">模板字段加载失败：'+escHtml(e.message)+'</div>';
  });
}
dmdest.onchange=function(){ loadTables(); };
dmtable.onchange=loadColumns;
dmtpl.onchange=loadTplFields;
dmmode.onchange=syncBk;

document.getElementById('newmap').onclick=function(){
  dmmsg.textContent=''; cols=[];
  dmdest.innerHTML='<option value="">选择目的地</option>'+
    dests.map(function(d){
      return '<option value="'+d.id+'">'+escHtml(d.name)+'</option>';
    }).join('');
  dmtpl.innerHTML='<option value="">选择模板</option>'+
    tpls.map(function(t){
      return '<option value="'+t.id+'">'+escHtml(t.name)+' v'+t.current_version+'</option>';
    }).join('');
  dmtable.innerHTML='<option value="">先选目的地</option>'; dmtable.disabled=true;
  document.getElementById('dmthint').textContent='';
  dmmode.value='upsert'; dmrows.innerHTML='';
  dmap.hidden=false;
};
function closeDmap(){ dmap.hidden=true; }
document.getElementById('dmclose').onclick=closeDmap;
dmap.addEventListener('click',function(e){ if(e.target===dmap) closeDmap(); });
document.addEventListener('keydown',function(e){
  if(e.key!=='Escape') return;
  if(!ddest.hidden) closeDdest();
  if(!dmap.hidden) closeDmap();
});

document.getElementById('dmsave').onclick=function(){
  dmmsg.textContent='';
  if(!dmdest.value){ dmmsg.textContent='请选目的地'; return; }
  if(!dmtpl.value){ dmmsg.textContent='请选模板'; return; }
  if(!dmtable.value){ dmmsg.textContent='请选目标表'; return; }
  var rows=dmrows.querySelectorAll('.frow');
  if(!rows.length){ dmmsg.textContent='该模板无固定目标字段，不可入库'; return; }
  var cm={}, bk=[], seen={}, err=null;
  Array.prototype.forEach.call(rows,function(div){
    if(err) return;
    var f=div.querySelector('.fname').value;
    var c=div.querySelector('.fcol').value;
    if(!c){ err='字段「'+f+'」未选目标列'; return; }
    if(seen[c]){ err='多个字段映射到同一目标列：'+c; return; }
    seen[c]=1; cm[f]=c;
    if(div.querySelector('.fbk').checked) bk.push(c);
  });
  if(err){ dmmsg.textContent=err; return; }
  if(dmmode.value!=='insert'&&!bk.length){
    dmmsg.textContent=dmmode.value+' 模式须勾选至少一个业务键'; return;
  }
  api('POST','/api/load/mappings',{
    load_dest_id:Number(dmdest.value), template_id:Number(dmtpl.value),
    target_table:dmtable.value, column_map:cm, write_mode:dmmode.value,
    business_key:bk.length?bk:null
  }).then(function(){
    closeDmap(); showOk('已保存映射（'+dmtable.value+' · '+dmmode.value+'）。');
    return loadAll();
  }).catch(function(e){ dmmsg.textContent=e.message; });
};
document.getElementById('maprows').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-delmap]'):null;
  if(!b) return;
  var id=b.getAttribute('data-delmap'), name=b.getAttribute('data-name');
  if(!window.confirm('删除映射「'+name+'」？')) return;
  api('DELETE','/api/load/mappings/'+id).then(function(){
    showOk('已删除映射。'); loadAll();
  }).catch(function(e2){ showErr(e2.message); });
});

loadAll();