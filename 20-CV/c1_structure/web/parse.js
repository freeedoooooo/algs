/* web/parse.js — 上传页交互：参数面板 + base64 上传 + 进度轮询 */
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
var BASIC_KEYS=['model','page'];   /* 基础配置：默认展开；其余归高级配置（可收起） */
function renderParams(schema){
  paramSchema=schema;
  var groups={},order=[],basic=[];
  schema.forEach(function(p){
    if(p.hidden) return;   /* 服务端标记隐藏的参数不生成控件（如识别模型档位） */
    if(BASIC_KEYS.indexOf(p.key)>=0){ basic.push(p); return; }
    if(!groups[p.group]){groups[p.group]=[];order.push(p.group);}
    groups[p.group].push(p);
  });
  var basicHtml='<div class="pgroup basic"><h4>基础配置</h4>'+
    basic.map(fieldHtml).join('')+'</div>';
  var advHtml='<details class="advanced" id="advancedParams">'+
    '<summary class="advanced-head"><span>高级配置</span>'+
    '<span class="hint" tabindex="0" onclick="event.preventDefault()" '+
    'data-tip="展开可调整表格识别、文字识别、渲染精度等细节参数；&#10;'+
    '通常保持默认即可，修改仅对本次解析生效。">?</span></summary>'+
    '<div class="advanced-body">'+
    order.map(function(g){
      return '<div class="pgroup"><h4>'+escHtml(g)+'</h4>'+
        groups[g].map(fieldHtml).join('')+'</div>';
    }).join('')+
    '</div></details>';
  paramgroups.innerHTML=basicHtml+advHtml;
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
  b.textContent=n?('已修改 '+n+' 项'):'默认';
  b.classList.toggle('on',n>0);
}
fetch('/api/params').then(function(r){return r.json();}).then(function(j){
  if(j.schema) renderParams(j.schema);
}).catch(function(){});

/* 抽取规则不在解析页选择（方案A）：在数据预览页「执行抽取」时绑定。 */

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
  // 一条资料 = 一次运行（单文件）：一次只解析一个文件
  if(!fs||!fs.length) return;
  var f=fs[0], multi=fs.length>1;
  var e=(f.name.split('.').pop()||'').toLowerCase();
  if(ALLOWED.indexOf(e)<0){
    msg.innerHTML='<span class="err">不支持的格式：'+escHtml(e)+'</span>';
    return;
  }
  if(f.size>20*1024*1024){
    msg.innerHTML='<span class="err">文件超过 20MB，已忽略</span>';
    return;
  }
  picked.forEach(function(p){ if(p._url) URL.revokeObjectURL(p._url); });
  picked=[f];
  render();
  msg.innerHTML=multi
    ? '<span class="warn">已选多个文件，本次只解析「'+escHtml(f.name)+'」</span>'
    : '';
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
/* ---- 上传页取 x 坐标：解析前在原图预览上量列边界，直接填进 column_lines ----
   坐标=原图像素，与 doc_unwarp=off 的重切空间一致；on 的矫正图坐标需解析后在报告页取。 */
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
  if(el) el.textContent=pickVals.length?pickVals.join(', '):'（尚未拾取坐标）';
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
      var adv=document.getElementById('advancedParams'); if(adv) adv.open=true;
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
var LV={info:'INFO',ok:' OK ',stage:'STEP',warn:'WARN',error:'ERR '};
function say(rows,fallback){
  if(!rows||!rows.length){
    log.textContent=(fallback||[]).join('\n')||'暂无日志输出';
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
      msg.textContent='解析完成。可调整参数后，用同一批文件重新解析。';
      go.disabled=false;
      showStgLink(s.file_id);
      showResult(s.cases);
      loadHistory(s.file_id,true);
    }
  }).catch(function(){timer=setTimeout(poll,1200);});
}
var reportFrame=document.getElementById('reportFrame'),
    reportempty=document.getElementById('reportempty'),
    unparsed=document.getElementById('unparsed'),
    runpanel=document.getElementById('runpanel'),
    logbtn=document.getElementById('logbtn'),
    logclose=document.getElementById('logclose'),
    filetabs=document.getElementById('filetabs'),
    histbar=document.getElementById('histbar'),
    histsel=document.getElementById('histsel'),
    reportcol=document.querySelector('.reportcol'),
    stglink=document.getElementById('stglink');
/* 完成提示：跳数据预览（task id 键） */
function showStgLink(fileId){
  if(!fileId) return;
  stglink.href='/preview?file='+fileId;
  stglink.hidden=false;
}
/* 右侧报告区四态：idle 占位 / 任务进度 / done 报告 / unparsed 未解析提示
   （资料选择条在 done 与 unparsed 两态都显示，方便随时切换资料） */
function rightState(st){
  reportempty.hidden=(st!=='idle');
  unparsed.hidden=(st!=='unparsed');
  runpanel.hidden=(st!=='run');
  runpanel.classList.remove('drawer');
  logclose.hidden=true;
  reportFrame.hidden=(st!=='done');
  logbtn.hidden=(st!=='done');
  var showHist=(st==='done'||st==='unparsed');
  histbar.hidden=!showHist;
  reportcol.classList.toggle('has-hist',showHist);
  if(st!=='done'){ filetabs.hidden=true; reportcol.classList.remove('hastabs'); }
}
/* 单文件报告：直接落该资料命名空间，无文件页签 */
function reportUrl(fid){
  return '/files/'+fid+'/'+encodeURIComponent('对照报告.html');
}
function showResult(cases){
  rightState('done');
  cases=cases||[];
  reportFrame.src=(cases.length?reportUrl(cases[0].file_id):'/parse-report')+'?t='+Date.now();
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

/* ---- 资料选择：列出全部资料；已解析→报告，未解析→提示并提供解析按钮 ---- */
var histItems=[], curHist=null;
var PARSED_STATES=['to_extract','to_review','to_load','loading','loaded'];
function isParsed(f){ return PARSED_STATES.indexOf(f.state)>=0; }
function histLabel(f){
  return '#'+f.id+' · '+shortName(f.name)+' · '+fmtTime(f.created_at)+
    (isParsed(f)?'':'（未解析）');
}
function showHistItem(f){
  curHist=f;
  if(isParsed(f)){
    showResult([{file:f.name,file_id:f.id}]);
  }else{
    rightState('unparsed');
    document.getElementById('upDesc').textContent=
      '「'+f.name+'」尚未解析，暂无对照报告。点击下方按钮发起解析，完成后自动生成报告。';
    var b=document.getElementById('upParse');
    b.disabled=false; b.textContent='解析此资料';
    document.getElementById('upMsg').textContent='';
  }
}
function loadHistory(selectId,skipRender){
  fetch('/api/sources/state').then(function(r){return r.ok?r.json():null;}).then(function(j){
    histItems=(j&&j.items)||[];
    histsel.innerHTML=histItems.map(function(f){
      return '<option value="'+f.id+'">'+escHtml(histLabel(f))+'</option>';
    }).join('');
    if(!histItems.length){ if(!skipRender) rightState('idle'); return; }
    var pick=null;
    for(var i=0;i<histItems.length;i++){
      if(String(histItems[i].id)===String(selectId)){pick=histItems[i];break;}
    }
    pick=pick||histItems[0];
    histsel.value=String(pick.id);
    if(!skipRender) showHistItem(pick);
  }).catch(function(){});
}
histsel.addEventListener('change',function(){
  for(var i=0;i<histItems.length;i++){
    if(String(histItems[i].id)===histsel.value){ showHistItem(histItems[i]); return; }
  }
});
/* 未解析资料的「解析此资料」按钮：复用 /api/sources/{id}/parse */
document.getElementById('upParse').onclick=async function(){
  if(!curHist) return;
  var b=this, upMsg=document.getElementById('upMsg');
  b.disabled=true; b.textContent='解析中…'; upMsg.textContent='正在发起解析…';
  try{
    saveParams(collectParams());
    var res=await fetch('/api/sources/'+curHist.id+'/parse',{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({params:collectParams()})
    });
    var j=await res.json();
    if(!j.ok) throw new Error(j.error||'发起失败');
    stglink.hidden=true;
    rightState('run');
    log.innerHTML='';
    document.getElementById('runfill').style.width='0%';
    document.getElementById('runpct').textContent='0%';
    document.getElementById('runstage').textContent='准备中…';
    msg.textContent='处理中…';
    poll();
  }catch(e){
    upMsg.textContent='发起失败：'+e.message;
    b.disabled=false; b.textContent='解析此资料';
  }
};

go.onclick=async function(){
  go.disabled=true;msg.textContent='正在读取文件…';
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
      body:JSON.stringify({files:files,params:collectParams()})
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

/* 资料页「解析」跳转：/parse?from_source=<id> → 右侧资料选择里预选该资料 */
var fromSrc=new URLSearchParams(location.search).get('from_source');
fetch('/api/status').then(function(r){return r.json();}).then(function(s){
  if(s.running){ rightState('run'); say(s.logs,s.steps); progress(s); poll(); }
  else if(s.ready){
    /* 刷新页面直接进完成态：日志/进度也要补渲染，否则「查看日志」抽屉是空的 */
    say(s.logs,s.steps); progress(s); showStgLink(s.file_id); showResult(s.cases);
    loadHistory(s.file_id,true);
  }
  else loadHistory(fromSrc||undefined);
});

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
