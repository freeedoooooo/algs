/* extract_report/assets/staging.js — 暂存只读视图：records.json 渲染 + 逐格血缘侧栏。
   数据全部来自预生成文件（经 /api/runs/{batch}/staging），不依赖平台库。 */
var batch=new URLSearchParams(location.search).get('batch')||'';
var curFile=new URLSearchParams(location.search).get('file')||'';
var runDoc=null, records=[], keys=[], selIdx=-1;

function showErr(t){
  var e=document.getElementById('err');
  e.hidden=false; e.textContent=t;
}
function renderTabs(){
  var tabs=document.getElementById('filetabs');
  var files=(runDoc&&runDoc.files||[]).filter(function(f){return f.case;});
  if(files.length<2){ tabs.hidden=true; return; }
  tabs.hidden=false;
  tabs.innerHTML=files.map(function(f){
    return '<button type="button" class="ftab'+(f.case===curFile?' on':'')+
      '" data-case="'+escHtml(f.case)+'" title="'+escHtml(f.name)+'">'+
      escHtml(shortName(f.name))+'</button>';
  }).join('');
}
document.getElementById('filetabs').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-case]'):null;
  if(!b) return;
  curFile=b.getAttribute('data-case');
  history.replaceState(null,'','/staging?batch='+encodeURIComponent(batch)+
    '&file='+encodeURIComponent(curFile));
  renderTabs(); loadStaging();
});

function collectKeys(){
  var seen={}, out=[];
  records.forEach(function(r){
    Object.keys(r.values||{}).forEach(function(k){
      if(!seen[k]){ seen[k]=true; out.push(k); }
    });
  });
  return out;
}
function renderTable(){
  keys=collectKeys();
  document.getElementById('rechead').innerHTML='<tr><th>#</th>'+
    keys.map(function(k){return '<th>'+escHtml(k)+'</th>';}).join('')+
    '<th>状态</th></tr>';
  document.getElementById('recrows').innerHTML=records.map(function(r,i){
    return '<tr data-i="'+i+'"><td class="idx">'+(r.index==null?i:r.index)+'</td>'+
      keys.map(function(k){
        var v=(r.values||{})[k];
        return '<td title="'+escHtml(v)+'">'+escHtml(v==null?'':v)+'</td>';
      }).join('')+
      '<td>'+stateBadge((r.review||{}).state||'pending')+'</td></tr>';
  }).join('');
  document.getElementById('empty').hidden=records.length>0;
  document.getElementById('summary').textContent=
    '共 '+records.length+' 条记录 · '+keys.length+' 个字段 · 点行查看逐格血缘';
  hideLineage();
}
function anchorText(a){
  var parts=[];
  parts.push(a.page!=null?('页 '+a.page):'页 ?');
  parts.push(a.table_scope==='stitched'?('合并表 #'+a.table_index):('页内表 #'+a.table_index));
  if(a.cell_bbox&&a.cell_bbox.length>=4)
    parts.push('bbox ['+a.cell_bbox.map(function(x){return Math.round(x*10)/10;}).join(', ')+']');
  else parts.push('无坐标');
  if(a.space) parts.push('空间 '+a.space);
  return parts.join(' · ');
}
function showLineage(i){
  var r=records[i]; if(!r) return;
  selIdx=i;
  document.querySelectorAll('#recrows tr').forEach(function(tr){
    tr.classList.toggle('sel',+tr.getAttribute('data-i')===i);
  });
  var lin=r.lineage||{};
  var html=keys.map(function(k){
    var anchors=lin[k]||[];
    var v=(r.values||{})[k];
    return '<div class="litem"><span class="k">'+escHtml(k)+'</span>'+
      '<div class="v">'+escHtml(v==null?'':v)+'</div>'+
      anchors.map(function(a){
        return '<div class="a">'+escHtml(anchorText(a))+'</div>';
      }).join('')+'</div>';
  }).join('');
  document.getElementById('ltitle').textContent='记录 #'+(r.index==null?i:r.index)+' 血缘';
  document.getElementById('lbody').innerHTML=html||'<div class="empty">无血缘信息</div>';
  document.getElementById('lineage').hidden=false;
}
function hideLineage(){
  selIdx=-1;
  document.getElementById('lineage').hidden=true;
  document.querySelectorAll('#recrows tr.sel').forEach(function(tr){
    tr.classList.remove('sel');
  });
}
document.getElementById('recrows').addEventListener('click',function(e){
  var tr=e.target.closest?e.target.closest('tr[data-i]'):null;
  if(!tr) return;
  var i=+tr.getAttribute('data-i');
  if(i===selIdx) hideLineage(); else showLineage(i);
});
document.getElementById('lclose').onclick=hideLineage;

function loadStaging(){
  document.getElementById('err').hidden=true;
  var u='/api/runs/'+encodeURIComponent(batch)+'/staging'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  fetch(u).then(function(r){
    if(!r.ok) return r.json().then(function(j){throw new Error(j.error||('HTTP '+r.status));});
    return r.json();
  }).then(function(doc){
    var f=(doc.files||[])[0]||{};
    records=f.records||[];
    renderTable();
    var links=document.getElementById('filelinks');
    if(curFile){
      links.innerHTML='<a class="linkbtn" target="_blank" href="'+
        fileUrl(curFile,'对照报告.html')+'">对照报告</a>'+
        '<a class="linkbtn" target="_blank" href="'+
        fileUrl(curFile,'records.json')+'">records.json</a>';
    }else links.innerHTML='';
    var t=doc.template||{};
    document.getElementById('tplbadge').innerHTML=
      '<span class="badge blue">'+escHtml((t.name||'原始透传')+' v'+(t.version||1))+'</span>';
  }).catch(function(e){
    records=[]; renderTable(); showErr('读取预览数据失败：'+e.message);
  });
}

document.getElementById('batchtag').textContent=batch||'（未指定批次）';
document.getElementById('runlink').href=batch?('/runs?batch='+encodeURIComponent(batch)):'/runs';
if(!batch){
  showErr('缺少批次参数。请从记录详情或提取完成提示进入。');
}else{
  fetch('/api/runs/'+encodeURIComponent(batch)).then(function(r){
    if(!r.ok) throw new Error('批次不存在');
    return r.json();
  }).then(function(j){
    runDoc=j.run;
    if(!curFile){
      var f=(runDoc.files||[]).find(function(x){return x.case;});
      curFile=f?f.case:'';
    }
    renderTabs(); loadStaging();
  }).catch(function(e){ showErr(e.message); });
}