/* report/assets/upload.js — 上传页交互：参数面板 + base64 上传 + 进度轮询 */
var picked=[],timer=null,paramSchema=[];
var drop=document.getElementById('drop'),picker=document.getElementById('picker');
var list=document.getElementById('filelist'),go=document.getElementById('go');
var log=document.getElementById('log'),msg=document.getElementById('msg');
var paramgroups=document.getElementById('paramgroups');

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
}
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
};

drop.onclick=function(){picker.click();};
drop.ondragover=function(e){e.preventDefault();drop.classList.add('on');};
drop.ondragleave=function(){drop.classList.remove('on');};
drop.ondrop=function(e){
  e.preventDefault();drop.classList.remove('on');add(e.dataTransfer.files);
};
picker.onchange=function(){add(picker.files);};

function add(fs){
  for(var i=0;i<fs.length;i++) picked.push(fs[i]);
  render();
}
function render(){
  list.innerHTML='';
  picked.forEach(function(f){
    var li=document.createElement('li');
    li.innerHTML='<span></span><span></span>';
    li.firstChild.textContent=f.name;
    li.lastChild.textContent=(f.size/1024).toFixed(0)+' KB';
    list.appendChild(li);
  });
  go.disabled=picked.length===0;
}
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
      msg.textContent='完成，正在打开报告…';
      setTimeout(function(){location.href='/report';},600);
    }
  }).catch(function(){timer=setTimeout(poll,1200);});
}

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
