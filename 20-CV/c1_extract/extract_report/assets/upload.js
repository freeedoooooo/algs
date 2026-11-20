/* extract_report/assets/upload.js — 上传页交互：参数面板 + base64 上传 + 进度轮询 */
var picked=[],timer=null,paramSchema=[];
var drop=document.getElementById('drop'),picker=document.getElementById('picker');
var list=document.getElementById('filelist'),go=document.getElementById('go');
var log=document.getElementById('log'),msg=document.getElementById('msg');
var paramgroups=document.getElementById('paramgroups');
var lb=document.getElementById('lightbox'),lbimg=document.getElementById('lbimg');

/* 参数持久化：上传完看对照报告再回来不丢已填值。存浏览器 localStorage，
   与后端默认值解耦（后端 schema 仍是唯一真相源，这里只记用户上次的选择）。 */
var PKEY='c1_params';
function loadSaved(){
  try{ return JSON.parse(localStorage.getItem(PKEY)||'{}'); }catch(e){ return {}; }
}
function saveParams(obj){
  try{ localStorage.setItem(PKEY, JSON.stringify(obj)); }catch(e){}
}

/* 从后端 /api/params 读 schema（顺序=优先级），动态生成参数控件。
   前端不写死任何默认值/范围 —— 全部跟着 params.py 走，避免两处漂移。 */
function fieldHtml(p){
  var id='pf_'+p.key, v=p.default;
  var input;
  if(p.type==='select'){
    input='<select id="'+id+'">'+p.options.map(function(o){
      return '<option value="'+o+'"'+(o===v?' selected':'')+'>'+o+'</option>';
    }).join('')+'</select>';
  }else{
    var t=(p.type==='str')?'text':'number';
    var extra=' value="'+v+'"';
    if(p.min!==undefined) extra+=' min="'+p.min+'"';
    if(p.max!==undefined) extra+=' max="'+p.max+'"';
    if(p.step!==undefined) extra+=' step="'+p.step+'"';
    input='<input type="'+t+'" id="'+id+'"'+extra+'>';
  }
  return '<div class="field"><label for="'+id+'">'+escHtml(p.label)+'</label>'+
    '<span class="finput">'+input+
    '<span class="hint" tabindex="0" data-tip="'+escHtml(p.help)+'">?</span>'+
    '</span></div>';
}
function renderParams(schema){
  paramSchema=schema;
  var groups={},order=[];
  schema.forEach(function(p){
    if(!groups[p.group]){groups[p.group]=[];order.push(p.group);}
    groups[p.group].push(p);
  });
  paramgroups.innerHTML=order.map(function(g){
    return '<div class="pgroup"><h4>'+g+'</h4>'+
      groups[g].map(fieldHtml).join('')+'</div>';
  }).join('');
  var saved=loadSaved();
  schema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(el && saved[p.key]!==undefined && saved[p.key]!==null) el.value=saved[p.key];
  });
  updateBadge();
}
paramgroups.addEventListener('input',function(){ saveParams(collectParams()); updateBadge(); });
paramgroups.addEventListener('change',function(){ saveParams(collectParams()); updateBadge(); });
function collectParams(){
  var out={};
  paramSchema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(!el) return;
    out[p.key]=el.value;
  });
  return out;
}
function updateBadge(){
  var b=document.getElementById('parambadge');
  if(!b) return;
  var n=0;
  paramSchema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(el && String(el.value)!==String(p.default)) n++;
  });
  b.textContent=n?('已改 '+n+' 项'):'默认';
  b.classList.toggle('on',n>0);
}
fetch('/api/params').then(function(r){return r.json();}).then(function(j){
  if(j.schema) renderParams(j.schema);
}).catch(function(){});

/* 模板下拉：/api/templates（DB 降级时后端回内置「原始透传」）。
   value = 模板版本 id；降级项无 id，提交时省略走后端默认。 */
var tplsel=document.getElementById('tplsel');
function tplFallback(){ tplsel.innerHTML='<option value="">原始透传 v1</option>'; }
fetch('/api/templates').then(function(r){return r.json();}).then(function(j){
  var items=j.items||[];
  if(!items.length){ tplFallback(); return; }
  tplsel.innerHTML=items.map(function(t){
    return '<option value="'+(t.current_version_id||'')+'">'+
      escHtml((t.name||'原始透传')+' v'+(t.current_version||1))+'</option>';
  }).join('');
}).catch(tplFallback);
function tplVersionId(){ return tplsel.value||null; }

document.getElementById('resetparams').onclick=function(e){
  e.preventDefault();
  paramSchema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(el) el.value=p.default;
  });
  try{ localStorage.removeItem(PKEY); }catch(e){}
  updateBadge();
};

drop.onclick=function(){picker.click();};
drop.ondragover=function(e){e.preventDefault();drop.classList.add('on');};
drop.ondragleave=function(){drop.classList.remove('on');};
drop.ondrop=function(e){
  e.preventDefault();drop.classList.remove('on');add(e.dataTransfer.files);
};
picker.onchange=function(){add(picker.files);};

var ALLOWED=['png','jpg','jpeg','bmp','webp','tif','tiff','pdf','csv','txt','md'];
function add(fs){
  var rejected=[];
  for(var i=0;i<fs.length;i++){
    var f=fs[i];
    var e=(f.name.split('.').pop()||'').toLowerCase();
    if(ALLOWED.indexOf(e)<0){ rejected.push(f.name); continue; }
    if(picked.some(function(p){return p.name===f.name&&p.size===f.size;})) continue;
    picked.push(f);
  }
  if(rejected.length)
    msg.innerHTML='<span class="err">不支持的格式已忽略：'+escHtml(rejected.join('、'))+'</span>';
  render();
}
function fileRow(name,size,url){
  return '<span class="fthumb">'+thumbHtml(name,url)+'</span>'+
    '<span class="fname" title="'+escHtml(name)+'">'+escHtml(name)+'</span>'+
    '<span class="fsize">'+(size/1024).toFixed(0)+' KB</span>';
}
function render(){
  list.innerHTML='';
  picked.forEach(function(f,i){
    var li=document.createElement('li');
    var url=f._url||(f._url=URL.createObjectURL(f));
    li.innerHTML=fileRow(f.name,f.size,url)+
      '<button type="button" class="fdel" data-i="'+i+'" title="移除该文件">×</button>';
    list.appendChild(li);
  });
  document.getElementById('filebar').hidden=picked.length===0;
  document.getElementById('filecount').textContent='已选 '+picked.length+' 个文件';
  go.disabled=picked.length===0;
}
list.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('.fdel'):null;
  if(!b) return;
  var i=+b.getAttribute('data-i');
  var f=picked[i];
  picked.splice(i,1);
  render();                       // 先移除 DOM 里的 <img>，再释放 blob，避免引用已失效 URL
  if(f&&f._url) URL.revokeObjectURL(f._url);
});
document.getElementById('clearfiles').onclick=function(){
  var urls=picked.map(function(f){return f._url;});
  picked=[]; render();
  urls.forEach(function(u){ if(u) URL.revokeObjectURL(u); });
};
function kindOf(name){
  var e=(name.split('.').pop()||'').toLowerCase();
  if(['png','jpg','jpeg','bmp','webp','tif','tiff'].indexOf(e)>=0) return 'image';
  if(e==='pdf') return 'pdf';
  return 'text';
}
function thumbHtml(name,url){
  var k=kindOf(name);
  if(k==='image')
    return '<img class="thumb" src="'+url+'" data-full="'+url+'" alt="'+escHtml(name)+'" title="'+escHtml(name)+'">';
  var label=(k==='pdf'?'PDF':(name.split('.').pop()||'FILE').toUpperCase());
  return '<a class="thumb file" href="'+url+'" target="_blank" title="'+escHtml(name)+'"><span>'+escHtml(label)+'</span></a>';
}
/* ---- 上传页取 x 坐标：提取前在原图预览上量列边界，直接填进 column_lines ----
   坐标=原图像素，与 doc_unwarp=off 的重切空间一致；on 的矫正图坐标需提取后在报告页取。 */
var SVGNS='http://www.w3.org/2000/svg';
var pickMode=false, pickVals=[];
var lbStage=document.getElementById('lbStage'),lbsvg=document.getElementById('lbsvg');
var pickbar=document.getElementById('pickbar');
function syncSvg(){
  var nw=lbimg.naturalWidth,nh=lbimg.naturalHeight;
  if(nw) lbsvg.setAttribute('viewBox','0 0 '+nw+' '+nh);
}
lbimg.addEventListener('load',syncSvg);
function openLb(url){
  lbsvg.innerHTML='';
  lbimg.src=url; lb.hidden=false;
  if(lbimg.complete) syncSvg();
}
function closeLb(){
  lb.hidden=true; lbimg.removeAttribute('src'); lbsvg.innerHTML='';
  setPickMode(false);
}
document.getElementById('lbClose').onclick=closeLb;
lbStage.addEventListener('click',function(e){ if(e.target===lbStage) closeLb(); });
document.addEventListener('keydown',function(e){
  if(!lb.hidden&&e.key==='Escape') closeLb();
});
document.getElementById('lbZoom').onclick=function(){
  var z=lbStage.classList.toggle('zoom');
  this.classList.toggle('on',z);
  this.textContent=z?'适应窗口':'1:1 像素';
};
function setPickMode(on){
  pickMode=on;
  pickbar.hidden=!on;
  document.body.classList.toggle('picking',on);
  var b=document.getElementById('lbPick');
  b.classList.toggle('on',on); b.textContent=on?'退出取数':'取 x 坐标';
  renderPickVals();
}
document.getElementById('lbPick').onclick=function(){ setPickMode(!pickMode); };
function renderPickVals(){
  var el=document.getElementById('pickvals');
  if(el) el.textContent=pickVals.length?pickVals.join(', '):'（尚未取点）';
}
function naturalX(img,clientX){
  var r=img.getBoundingClientRect();
  var nw=img.naturalWidth||1000;
  return Math.max(0,Math.min(nw,Math.round((clientX-r.left)*nw/(r.width||1))));
}
lbimg.addEventListener('click',function(e){
  e.stopPropagation();
  if(!pickMode) return;
  var x=naturalX(lbimg,e.clientX);
  pickVals.push(x);
  var ln=document.createElementNS(SVGNS,'line');
  ln.setAttribute('class','pickline');
  ln.setAttribute('x1',x); ln.setAttribute('x2',x);
  ln.setAttribute('y1',0); ln.setAttribute('y2',lbimg.naturalHeight||0);
  lbsvg.appendChild(ln);
  renderPickVals();
});
pickbar.addEventListener('click',function(e){
  var b=e.target.closest?e.target.closest('[data-pick]'):null;
  if(!b) return;
  var a=b.getAttribute('data-pick');
  if(a==='fill'){
    var el=document.getElementById('pf_column_lines');
    if(el&&pickVals.length){
      document.getElementById('parampanel').open=true;
      el.value=pickVals.join(',');
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.scrollIntoView({block:'nearest',behavior:'smooth'});
      b.textContent='已填入'; setTimeout(function(){b.textContent='填入列边界';},1500);
    }
  }else if(a==='copy'){
    if(pickVals.length) navigator.clipboard.writeText(pickVals.join(',')).then(function(){
      b.textContent='已复制'; setTimeout(function(){b.textContent='复制';},1500);
    });
  }else if(a==='clear'){
    pickVals=[]; lbsvg.querySelectorAll('.pickline').forEach(function(x){x.remove();});
    renderPickVals();
  }else if(a==='exit'){ setPickMode(false); }
});
function bindThumbs(el){
  el.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('img.thumb'):null;
    if(t){ e.preventDefault(); openLb(t.getAttribute('data-full')); }
  });
}
bindThumbs(list);
function b64(file){
  return new Promise(function(ok,no){
    var r=new FileReader();
    r.onload=function(){ok(r.result.split(',')[1]);};
    r.onerror=no;
    r.readAsDataURL(file);
  });
}
var LV={info:'INFO',ok:' OK ',stage:'STEP',warn:'WARN',error:'ERR '};
function escHtml(s){
  return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}
function say(rows,fallback){
  if(!rows||!rows.length){
    log.textContent=(fallback||[]).join('\n')||'等待日志…';
    return;
  }
  var html=rows.map(function(r){
    var lv=LV[r.level]?'lv-'+r.level:'lv-info';
    return '<div class="logrow '+lv+'">'+
      '<span class="t">'+escHtml((r.t||0).toFixed(1))+'s</span>'+
      '<span class="lv">'+escHtml(LV[r.level]||'INFO')+'</span>'+
      '<span class="st">'+escHtml(r.stage||'-')+'</span>'+
      '<span class="ms">+'+escHtml(r.ms==null?0:r.ms)+'ms</span>'+
      '<span class="tx">'+escHtml(r.msg)+'</span></div>';
  }).join('');
  log.innerHTML=html;
  log.scrollTop=log.scrollHeight;
}
function progress(s){
  var pct=Math.max(0,Math.min(100,Number(s.progress)||0));
  document.getElementById('runfill').style.width=pct+'%';
  document.getElementById('runpct').textContent=pct+'%';
  document.getElementById('runstage').textContent=
    (s.stage==='done'?'完成':(s.stage==='error'?'出错':('阶段：'+(s.stage||'准备中'))));
}
function poll(){
  fetch('/api/status').then(function(r){return r.json();}).then(function(s){
    say(s.logs,s.steps);
    progress(s);
    if(s.error){
      msg.innerHTML='<span class="err">出错：'+escHtml(s.error)+'</span>';
      go.disabled=false;return;
    }
    if(s.running){timer=setTimeout(poll,800);return;}
    if(s.ready){
      msg.textContent='完成。改参数后直接重测。';
      go.disabled=false;
      showStgLink(s.run_id);
      showResult(s.cases);
    }
  }).catch(function(){timer=setTimeout(poll,1200);});
}
var reportFrame=document.getElementById('reportFrame'),
    reportempty=document.getElementById('reportempty'),
    runpanel=document.getElementById('runpanel'),
    logbtn=document.getElementById('logbtn'),
    logclose=document.getElementById('logclose'),
    filetabs=document.getElementById('filetabs'),
    reportcol=document.querySelector('.reportcol'),
    stglink=document.getElementById('stglink');
/* 完成提示：跳数据预览（run id 键） */
function showStgLink(runId){
  if(!runId) return;
  stglink.href='/staging?run='+runId;
  stglink.hidden=false;
}
/* 右侧报告区三态：idle 占位 / run 进度 / done 报告（+「查看日志」浮钮） */
function rightState(st){
  reportempty.hidden=(st!=='idle');
  runpanel.hidden=(st!=='run');
  runpanel.classList.remove('drawer');
  logclose.hidden=true;
  reportFrame.hidden=(st!=='done');
  logbtn.hidden=(st!=='done');
  if(st!=='done'){ filetabs.hidden=true; reportcol.classList.remove('hastabs'); }
}
/* 每个文件一份独立报告（各自 run_file 命名空间）。多文件运行顶部给文件页签，
   点击在下方 iframe 切换；单文件直接看报告，不显示页签。 */
function reportUrl(rf){
  return '/files/'+rf+'/'+encodeURIComponent('对照报告.html');
}
function showResult(cases){
  rightState('done');
  cases=cases||[];
  filetabs.innerHTML='';
  if(cases.length>1){
    reportcol.classList.add('hastabs');
    filetabs.hidden=false;
    cases.forEach(function(c,i){
      var b=document.createElement('button');
      b.type='button'; b.className='ftab'+(i===0?' on':'');
      b.textContent=c.file; b.title=c.file;
      b.onclick=function(){
        filetabs.querySelectorAll('.ftab').forEach(function(x){
          x.classList.toggle('on',x===b);
        });
        reportFrame.src=reportUrl(c.run_file_id)+'?t='+Date.now();
      };
      filetabs.appendChild(b);
    });
    reportFrame.src=reportUrl(cases[0].run_file_id)+'?t='+Date.now();
  }else{
    /* 单文件（或未知 cases）：路由重定向到最新 run_file 的报告真实地址 */
    reportFrame.src='/extract-report?t='+Date.now();
  }
}
/* 完成后点「查看日志」：进度卡作为抽屉叠加在报告上，「关闭」收回 */
logbtn.onclick=function(){
  runpanel.hidden=false;
  runpanel.classList.add('drawer');
  logclose.hidden=false;
};
logclose.onclick=function(){
  runpanel.hidden=true;
  runpanel.classList.remove('drawer');
  logclose.hidden=true;
};

go.onclick=async function(){
  go.disabled=true;msg.textContent='读取文件…';
  rightState('run');
  stglink.hidden=true;
  log.innerHTML='';
  document.getElementById('runfill').style.width='0%';
  document.getElementById('runpct').textContent='0%';
  document.getElementById('runstage').textContent='准备中…';
  try{
    var files=[];
    for(var i=0;i<picked.length;i++){
      var f=picked[i];
      if(f.size>20*1024*1024) throw new Error(f.name+' 超过 20MB');
      files.push({name:f.name,data:await b64(f)});
    }
    msg.textContent='上传中…';
    saveParams(collectParams());
    var res=await fetch('/api/upload',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({files:files,params:collectParams(),
        mode:'preview',template_version_id:tplVersionId()})
    });
    var j=await res.json();
    if(!j.ok) throw new Error(j.error||'上传失败');
    // 参数警告会由后端以 warn 级日志发出，poll() 拉到后统一渲染，这里不覆写日志容器
    msg.textContent='处理中…';
    poll();
  }catch(e){
    msg.innerHTML='<span class="err">'+escHtml(e.message)+'</span>';
    go.disabled=false;
  }
};

fetch('/api/status').then(function(r){return r.json();}).then(function(s){
  if(s.running){ rightState('run'); say(s.logs,s.steps); progress(s); poll(); }
  else if(s.ready){
    /* 刷新页面直接进完成态：日志/进度也要补渲染，否则「查看日志」抽屉是空的 */
    say(s.logs,s.steps); progress(s); showStgLink(s.run_id); showResult(s.cases);
  }
});

/* ---- 从资料库选择：抽屉多选已登记文件 → POST /api/runs（不再收 base64） ---- */
var srcdrawer=document.getElementById('srcdrawer'),
    srclist=document.getElementById('srclist'),
    srcgo=document.getElementById('srcgo'),
    srcSel={}, srcQ='', srcTimer=null;
function srcCount(){
  var n=Object.keys(srcSel).filter(function(k){return srcSel[k];}).length;
  document.getElementById('srccount').textContent='已选 '+n+' 个';
  srcgo.disabled=n===0;
}
function renderSrcList(items,preId){
  srclist.innerHTML=items.map(function(r){
    var url='/srcfiles/'+r.id;
    var checked=srcSel[r.id]||(preId&&r.id===preId);
    if(checked) srcSel[r.id]=true;
    return '<li><label><input type="checkbox" data-id="'+r.id+'"'+
      (checked?' checked':'')+'>'+thumbHtml(r.name,url)+
      '<span class="nm" title="'+escHtml(r.name)+'">'+escHtml(r.name)+'</span>'+
      '<span class="sz">'+fmtSize(r.size_bytes)+'</span></label></li>';
  }).join('');
  document.getElementById('srcempty').hidden=items.length>0;
  srcCount();
}
function loadSrcList(preId){
  fetch('/api/sources?page=1&q='+encodeURIComponent(srcQ)).then(function(r){
    if(r.status===503){
      document.getElementById('srcdegraded').hidden=false;
      renderSrcList([]); return null;
    }
    document.getElementById('srcdegraded').hidden=true;
    return r.json();
  }).then(function(j){
    if(j) renderSrcList(j.items||[],preId);
  }).catch(function(){
    document.getElementById('srcdegraded').hidden=false; renderSrcList([]);
  });
}
function openSrcDrawer(preId){
  srcdrawer.hidden=false;
  loadSrcList(preId);
}
function closeSrcDrawer(){ srcdrawer.hidden=true; }
document.getElementById('fromsrc').onclick=function(){ openSrcDrawer(); };
document.getElementById('srcclose').onclick=closeSrcDrawer;
srcdrawer.addEventListener('click',function(e){ if(e.target===srcdrawer) closeSrcDrawer(); });
document.addEventListener('keydown',function(e){
  if(!srcdrawer.hidden&&e.key==='Escape') closeSrcDrawer();
});
document.getElementById('srcq').addEventListener('input',function(){
  var v=this.value.trim();
  clearTimeout(srcTimer);
  srcTimer=setTimeout(function(){ srcQ=v; loadSrcList(); },300);
});
srclist.addEventListener('change',function(e){
  var c=e.target.closest?e.target.closest('input[data-id]'):null;
  if(!c) return;
  srcSel[c.getAttribute('data-id')]=c.checked;
  srcCount();
});
srclist.addEventListener('click',function(e){
  var t=e.target.closest?e.target.closest('img.thumb'):null;
  if(t){ e.preventDefault(); openLb(t.getAttribute('data-full')); }
});
srcgo.onclick=async function(){
  var ids=Object.keys(srcSel).filter(function(k){return srcSel[k];}).map(Number);
  if(!ids.length) return;
  srcgo.disabled=true;
  try{
    saveParams(collectParams());
    var res=await fetch('/api/runs',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({source_file_ids:ids,params:collectParams(),
        template_version_id:tplVersionId()})
    });
    var j=await res.json();
    if(!j.ok) throw new Error(j.error||'发起失败');
    closeSrcDrawer();
    stglink.hidden=true;
    rightState('run');
    log.innerHTML='';
    document.getElementById('runfill').style.width='0%';
    document.getElementById('runpct').textContent='0%';
    document.getElementById('runstage').textContent='准备中…';
    msg.textContent='处理中…';
    poll();
  }catch(e){
    msg.innerHTML='<span class="err">'+escHtml(e.message)+'</span>';
    srcgo.disabled=false;
  }
};
/* 资料页「提取」跳转：/?from_source=<id> → 打开抽屉并预选 */
var fromSrc=new URLSearchParams(location.search).get('from_source');
if(fromSrc) openSrcDrawer(+fromSrc);

/* ---- 左栏宽度拖拽：gutter 拖动改 .console 宽，存 localStorage，双击复位 ----
   拖拽时把 iframe pointer-events 关掉，否则鼠标移进报告区事件被 iframe 吞掉。 */
(function(){
  var g=document.getElementById('gutter'),col=document.querySelector('.console');
  var frame=document.getElementById('reportFrame');
  if(!g||!col) return;
  var WKEY='c1_console_w',MIN=220;
  function maxW(){ return Math.max(MIN,Math.min(640,window.innerWidth-360)); }
  function apply(w){ col.style.width=Math.round(Math.max(MIN,Math.min(maxW(),w)))+'px'; }
  var saved=parseInt(localStorage.getItem(WKEY),10);
  if(saved) apply(saved);
  var dragging=false;
  g.addEventListener('mousedown',function(e){
    e.preventDefault(); dragging=true; g.classList.add('on');
    document.body.style.userSelect='none'; document.body.style.cursor='col-resize';
    if(frame) frame.style.pointerEvents='none';
  });
  window.addEventListener('mousemove',function(e){ if(dragging) apply(e.clientX); });
  window.addEventListener('mouseup',function(){
    if(!dragging) return;
    dragging=false; g.classList.remove('on');
    document.body.style.userSelect=''; document.body.style.cursor='';
    if(frame) frame.style.pointerEvents='';
    try{ localStorage.setItem(WKEY,parseInt(col.style.width,10)); }catch(e){}
  });
  g.addEventListener('dblclick',function(){
    col.style.width=''; try{ localStorage.removeItem(WKEY); }catch(e){}
  });
  window.addEventListener('resize',function(){
    if(col.style.width) apply(parseInt(col.style.width,10));
  });
})();
