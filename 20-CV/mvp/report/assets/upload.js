/* report/assets/upload.js — 上传页交互：参数面板 + base64 上传 + 进度轮询 */
var picked=[],timer=null,paramSchema=[];
var drop=document.getElementById('drop'),picker=document.getElementById('picker');
var list=document.getElementById('filelist'),go=document.getElementById('go');
var log=document.getElementById('log'),msg=document.getElementById('msg');
var paramgroups=document.getElementById('paramgroups');
var lastpanel=document.getElementById('lastpanel'),lastthumbs=document.getElementById('lastthumbs');
var lb=document.getElementById('lightbox'),lbimg=document.getElementById('lbimg');

/* 参数持久化：上传完跳 /report 再回来不丢已填值。存浏览器 localStorage，
   与后端默认值解耦（后端 schema 仍是唯一真相源，这里只记用户上次的选择）。 */
var PKEY='cv_mvp_params';
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
    if(p.type==='str') extra=' value="'+v+'" placeholder="'+(p.help||'').slice(0,28)+'…"';
    input='<input type="'+t+'" id="'+id+'"'+extra+'>';
  }
  return '<div class="field"><label for="'+id+'">'+p.label+'</label>'+
    input+'<span class="fhelp">'+p.help+'</span></div>';
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
}
paramgroups.addEventListener('input',function(){ saveParams(collectParams()); });
paramgroups.addEventListener('change',function(){ saveParams(collectParams()); });
function collectParams(){
  var out={};
  paramSchema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(!el) return;
    out[p.key]=el.value;
  });
  return out;
}
fetch('/api/params').then(function(r){return r.json();}).then(function(j){
  if(j.schema) renderParams(j.schema);
}).catch(function(){});

document.getElementById('resetparams').onclick=function(){
  paramSchema.forEach(function(p){
    var el=document.getElementById('pf_'+p.key);
    if(el) el.value=p.default;
  });
  try{ localStorage.removeItem(PKEY); }catch(e){}
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
    '<span class="fname">'+escHtml(name)+'</span>'+
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
      el.value=pickVals.join(',');
      el.dispatchEvent(new Event('input',{bubbles:true}));
      document.getElementById('parampanel').open=true;
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
bindThumbs(list); bindThumbs(lastthumbs);
function loadLast(){
  fetch('/api/last').then(function(r){return r.json();}).then(function(j){
    var fs=j.files||[];
    if(!fs.length){ lastpanel.hidden=true; return; }
    lastpanel.hidden=false;
    lastthumbs.innerHTML=fs.map(function(f){
      return '<li>'+fileRow(f.name,f.size,encodeURI(f.url))+'</li>';
    }).join('');
  }).catch(function(){});
}
loadLast();
document.getElementById('rerun').onclick=async function(){
  var btn=this; btn.disabled=true;
  msg.textContent='复用上次文件…';
  document.getElementById('runpanel').hidden=false;
  saveParams(collectParams());
  try{
    var res=await fetch('/api/rerun',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({params:collectParams()})
    });
    var j=await res.json();
    if(!j.ok) throw new Error(j.error||'重跑失败');
    msg.textContent='处理中…';
    poll();
  }catch(e){
    msg.innerHTML='<span class="err">'+escHtml(e.message)+'</span>';
    btn.disabled=false;
  }
};
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
  document.getElementById('runpanel').hidden=false;
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
      msg.textContent='完成。文件已保留，改参数后直接再点「开始提取」即可重测。';
      go.disabled=false;
      showResult();
    }
  }).catch(function(){timer=setTimeout(poll,1200);});
}
var resultbar=document.getElementById('resultbar'),
    reportFrame=document.getElementById('reportFrame');
function showResult(){
  resultbar.hidden=false;
  reportFrame.hidden=false;
  reportFrame.src='/report?t='+Date.now();
  document.getElementById('toggleReport').textContent='收起报告';
}
document.getElementById('toggleReport').onclick=function(){
  var h=!reportFrame.hidden;
  reportFrame.hidden=h;
  this.textContent=h?'展开报告':'收起报告';
};

go.onclick=async function(){
  go.disabled=true;msg.textContent='读取文件…';
  document.getElementById('runpanel').hidden=false;
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
    msg.innerHTML='<span class="err">'+e.message+'</span>';
    go.disabled=false;
  }
};

fetch('/api/status').then(function(r){return r.json();}).then(function(s){
  if(s.ready) document.getElementById('last').style.display='inline';
});
