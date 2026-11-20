/* extract_report/assets/staging.js — 数据预览：records.json 记录表 + 源图回溯框双向血缘。
   右侧复刻对照报告效果：源文件图叠单元格回溯框，点框定位左侧记录行/单元格，
   点行/字段在图上高亮对应框；支持翻页、原图/矫正图切换、放大。
   数据全部来自预生成文件（records.json + extract.json），不依赖平台库。 */
var batch=new URLSearchParams(location.search).get('batch')||'';
var curFile=new URLSearchParams(location.search).get('file')||'';
var runDoc=null, records=[], keys=[], selIdx=-1;
var pageMap={}, selAnchors=[], selPages=[], curPage=null, curView=null, selKey=null;

function showErr(t){
  var e=document.getElementById('err');
  e.hidden=false; e.textContent=t;
}
function imgUrl(rel){
  return '/files/'+encodeURIComponent(curFile)+'/'+
    String(rel).split('/').map(encodeURIComponent).join('/');
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
        return '<td data-key="'+escHtml(k)+'" title="'+escHtml(v)+'">'+
          escHtml(v==null?'':v)+'</td>';
      }).join('')+
      '<td>'+stateBadge((r.review||{}).state||'pending')+'</td></tr>';
  }).join('');
  document.getElementById('empty').hidden=records.length>0;
  document.getElementById('summary').textContent=
    '共 '+records.length+' 条记录 · '+keys.length+' 个字段 · 点行看源图回溯框，点框定位记录';
  hideLineage();
}

/* ---- 右侧：源图 + 回溯框 ---- */
function anchorsOf(i){
  var lin=(records[i]||{}).lineage||{}, out=[];
  keys.forEach(function(k){
    (lin[k]||[]).forEach(function(a){ out.push({key:k, a:a}); });
  });
  return out;
}
function selectRecord(i){
  var r=records[i]; if(!r) return;
  selIdx=i; selKey=null;
  document.querySelectorAll('#recrows tr').forEach(function(tr){
    tr.classList.toggle('sel',+tr.getAttribute('data-i')===i);
  });
  selAnchors=anchorsOf(i);
  var pset={};
  selAnchors.forEach(function(x){ if(x.a.page!=null) pset[x.a.page]=true; });
  selPages=Object.keys(pset).map(Number).sort(function(a,b){return a-b;});
  curPage=selPages.length?selPages[0]:(pagesMetaFirst());
  curView=null;
  document.getElementById('ltitle').textContent=
    '记录 #'+(r.index==null?i:r.index)+' 血缘回溯';
  document.getElementById('lineage').hidden=false;
  renderViewer();
}
function pagesMetaFirst(){
  var ks=Object.keys(pageMap);
  return ks.length?+ks[0]:null;
}
function metaOf(p){ return pageMap[p]||null; }
function viewSize(meta,view){
  if(view==='rect') return meta.rectified_size||meta.size||[0,0];
  return meta.size||[0,0];
}
function defaultView(meta,anchors){
  var hasRect=anchors.some(function(x){return x.a.space==='rectified';});
  if(hasRect&&meta.rectified_image) return 'rect';
  return 'source';
}
function renderViewer(){
  var meta=metaOf(curPage);
  var img=document.getElementById('limg'), svg=document.getElementById('lsvg');
  var hint=document.getElementById('lhint');
  var here=selAnchors.filter(function(x){return x.a.page===curPage;});
  if(!meta||!meta.size){
    img.removeAttribute('src'); svg.innerHTML='';
    document.getElementById('viewbar').innerHTML='';
    document.getElementById('lpager').hidden=true;
    hint.hidden=false; hint.textContent='该页无图像载体（纯文本输入），无法叠框回溯。';
    document.getElementById('lsub').textContent='';
    return;
  }
  if(!curView||(curView==='rect'&&!meta.rectified_image))
    curView=defaultView(meta,here);
  var src=curView==='rect'?meta.rectified_image:meta.image;
  var sz=viewSize(meta,curView), w=sz[0]||0, h=sz[1]||0;
  img.src=imgUrl(src);
  svg.setAttribute('viewBox','0 0 '+w+' '+h);
  var viewSpace=curView==='rect'?'rectified':'source';
  var drawn=0, rects='';
  here.forEach(function(x,ai){
    var a=x.a, b=a.cell_bbox;
    if(a.space!==viewSpace||!b||b.length<4) return;
    var pin=(selKey===x.key)?' pin':'';
    rects+='<rect class="cellbox all'+pin+'" data-key="'+escHtml(x.key)+
      '" data-aid="'+ai+'" x="'+b[0]+'" y="'+b[1]+'" width="'+Math.max(0,b[2]-b[0])+
      '" height="'+Math.max(0,b[3]-b[1])+'"><title>'+escHtml(x.key)+'&#10;'+
      escHtml(a.raw_text||'')+'</title></rect>';
    drawn++;
  });
  svg.innerHTML=rects;
  // 视图切换（原图 / 矫正图）
  var vb=document.getElementById('viewbar');
  if(meta.rectified_image){
    vb.innerHTML='<button type="button" class="viewbtn'+(curView==='source'?' on':'')+
      '" data-view="source">原图</button><button type="button" class="viewbtn'+
      (curView==='rect'?' on':'')+'" data-view="rect">矫正图</button>';
  }else vb.innerHTML='';
  // 翻页（记录跨多页时）
  var pg=document.getElementById('lpager');
  if(selPages.length>1){
    pg.hidden=false;
    pg.innerHTML=selPages.map(function(p){
      return '<button type="button" class="pbtn'+(p===curPage?' on':'')+
        '" data-page="'+p+'">页'+p+'</button>';
    }).join('');
  }else pg.hidden=true;
  // 提示
  if(!selAnchors.length){ hint.hidden=false; hint.textContent='该记录无坐标血缘。'; }
  else if(!drawn){ hint.hidden=false;
    hint.textContent='当前视图无回溯框：坐标在'+(curView==='rect'?'原图':'矫正图')+'空间，切换视图查看。'; }
  else hint.hidden=true;
  document.getElementById('lsub').textContent=
    '页'+curPage+' · '+drawn+' 个回溯框';
}
function pinField(key){
  if(selIdx<0) return;
  selKey=key;
  // 若该字段的框不在当前页/视图，导航过去
  var target=selAnchors.filter(function(x){return x.key===key&&x.a.cell_bbox;})[0];
  if(target&&(target.a.page!==curPage||
      (target.a.space==='rectified'&&curView!=='rect')||
      (target.a.space==='source'&&curView!=='source'))){
    curPage=target.a.page; curView=target.a.space;
  }
  renderViewer();
  // 左侧定位到具体单元格
  document.querySelectorAll('#recrows td.pin').forEach(function(td){
    td.classList.remove('pin');
  });
  var td=document.querySelector('#recrows tr[data-i="'+selIdx+'"] td[data-key="'+
    cssEsc(key)+'"]');
  if(td){ td.classList.add('pin'); td.scrollIntoView({block:'nearest',inline:'nearest'}); }
  syncLbPin();
}
function cssEsc(s){ return String(s).replace(/["\\]/g,'\\$&'); }
function hoverCell(key,on){
  document.querySelectorAll('#lsvg .cellbox').forEach(function(rc){
    if(rc.getAttribute('data-key')===key) rc.classList.toggle('hv',on);
  });
  var td=document.querySelector('#recrows tr[data-i="'+selIdx+'"] td[data-key="'+
    cssEsc(key)+'"]');
  if(td) td.classList.toggle('hv',on);
}
function hideLineage(){
  selIdx=-1; selKey=null; selAnchors=[]; selPages=[];
  document.getElementById('lineage').hidden=true;
  document.querySelectorAll('#recrows tr.sel').forEach(function(tr){
    tr.classList.remove('sel');
  });
  document.querySelectorAll('#recrows td.pin,#recrows td.hv').forEach(function(td){
    td.classList.remove('pin'); td.classList.remove('hv');
  });
  closeLb();
}

/* 左侧表：点行选中；点具体单元格 → 选中并钉住该字段框 */
document.getElementById('recrows').addEventListener('click',function(e){
  var tr=e.target.closest?e.target.closest('tr[data-i]'):null;
  if(!tr) return;
  var i=+tr.getAttribute('data-i');
  var td=e.target.closest?e.target.closest('td[data-key]'):null;
  if(td){ selectRecord(i); pinField(td.getAttribute('data-key')); return; }
  if(i===selIdx) hideLineage(); else selectRecord(i);
});
/* 右侧图：点框定位左侧行/格；悬停同步高亮；点空白放大 */
document.getElementById('lsvg').addEventListener('click',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(!rc) return;
  e.stopPropagation();
  pinField(rc.getAttribute('data-key'));
});
document.getElementById('lsvg').addEventListener('mouseover',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(rc) hoverCell(rc.getAttribute('data-key'),true);
});
document.getElementById('lsvg').addEventListener('mouseout',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(rc) hoverCell(rc.getAttribute('data-key'),false);
});
document.getElementById('limg').addEventListener('click',openLb);
document.getElementById('zoombtn').addEventListener('click',function(e){
  e.stopPropagation(); openLb();
});
document.getElementById('viewbar').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-view]'):null;
  if(!b) return;
  curView=b.getAttribute('data-view'); renderViewer();
});
document.getElementById('lpager').addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-page]'):null;
  if(!b) return;
  curPage=+b.getAttribute('data-page'); curView=null; renderViewer();
});
/* 左侧单元格悬停 → 图上对应框高亮（反向联动，仅选中行有图框） */
document.getElementById('recrows').addEventListener('mouseover',function(e){
  var td=e.target.closest?e.target.closest('td[data-key]'):null;
  if(!td) return;
  var tr=td.closest('tr[data-i]');
  if(!tr||+tr.getAttribute('data-i')!==selIdx) return;
  hoverCell(td.getAttribute('data-key'),true);
});
document.getElementById('recrows').addEventListener('mouseout',function(e){
  var td=e.target.closest?e.target.closest('td[data-key]'):null;
  if(!td) return;
  var tr=td.closest('tr[data-i]');
  if(!tr||+tr.getAttribute('data-i')!==selIdx) return;
  hoverCell(td.getAttribute('data-key'),false);
});
document.getElementById('lclose').onclick=hideLineage;

/* ---- 放大浮层：滚轮缩放 / 拖拽平移 / 框可点 ---- */
var lb={s:1,tx:0,ty:0,drag:null};
function openLb(){
  var meta=metaOf(curPage); if(!meta||!meta.size) return;
  var src=document.getElementById('limg').getAttribute('src');
  if(!src) return;
  document.getElementById('lbimg').src=src;
  var svg=document.getElementById('lbsvg');
  svg.setAttribute('viewBox',document.getElementById('lsvg').getAttribute('viewBox'));
  svg.innerHTML=document.getElementById('lsvg').innerHTML;
  document.getElementById('lbtitle').textContent=
    '记录 #'+((records[selIdx]||{}).index==null?selIdx:(records[selIdx].index))+
    ' · 页'+curPage+' · '+(curView==='rect'?'矫正图':'原图');
  lb.s=1; lb.tx=0; lb.ty=0; applyLb();
  document.getElementById('stglb').hidden=false;
}
function closeLb(){ document.getElementById('stglb').hidden=true; }
function applyLb(){
  document.getElementById('lbwrap').style.transform=
    'translate('+lb.tx+'px,'+lb.ty+'px) scale('+lb.s+')';
}
function syncLbPin(){
  if(document.getElementById('stglb').hidden) return;
  document.querySelectorAll('#lbsvg .cellbox').forEach(function(rc){
    rc.classList.toggle('pin',rc.getAttribute('data-key')===selKey);
  });
}
document.getElementById('lbclose').onclick=closeLb;
document.getElementById('stglb').addEventListener('click',function(e){
  if(e.target===this||e.target.id==='lbstage') closeLb();
});
document.getElementById('lbsvg').addEventListener('click',function(e){
  var rc=e.target.closest?e.target.closest('.cellbox'):null;
  if(!rc) return;
  e.stopPropagation();
  pinField(rc.getAttribute('data-key'));
});
document.getElementById('lbstage').addEventListener('wheel',function(e){
  e.preventDefault();
  var f=e.deltaY<0?1.15:1/1.15;
  var ns=Math.min(8,Math.max(0.4,lb.s*f));
  var r=this.getBoundingClientRect();
  var cx=e.clientX-r.left-r.width/2, cy=e.clientY-r.top-r.height/2;
  lb.tx=cx-(cx-lb.tx)*(ns/lb.s); lb.ty=cy-(cy-lb.ty)*(ns/lb.s);
  lb.s=ns; applyLb();
},{passive:false});
document.getElementById('lbstage').addEventListener('mousedown',function(e){
  if(e.target.closest&&e.target.closest('.cellbox')) return;
  lb.drag={x:e.clientX,y:e.clientY,tx:lb.tx,ty:lb.ty};
  e.preventDefault();
});
window.addEventListener('mousemove',function(e){
  if(!lb.drag) return;
  lb.tx=lb.drag.tx+(e.clientX-lb.drag.x);
  lb.ty=lb.drag.ty+(e.clientY-lb.drag.y); applyLb();
});
window.addEventListener('mouseup',function(){ lb.drag=null; });
document.addEventListener('keydown',function(e){
  if(e.key==='Escape'&&!document.getElementById('stglb').hidden) closeLb();
});

/* ---- 加载 ---- */
function loadStaging(){
  document.getElementById('err').hidden=true;
  var u='/api/runs/'+encodeURIComponent(batch)+'/staging'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  var eu='/api/runs/'+encodeURIComponent(batch)+'/extract'+
    (curFile?('?file='+encodeURIComponent(curFile)):'');
  Promise.all([
    fetch(u).then(function(r){
      if(!r.ok) return r.json().then(function(j){throw new Error(j.error||('HTTP '+r.status));});
      return r.json();
    }),
    fetch(eu).then(function(r){ return r.ok?r.json():null; }).catch(function(){return null;})
  ]).then(function(res){
    var doc=res[0], ex=res[1];
    pageMap={};
    ((ex&&ex.pages)||[]).forEach(function(p){ pageMap[p.index]=p; });
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