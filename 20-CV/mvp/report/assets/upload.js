/* report/assets/upload.js — 上传页交互：base64 上传 + 进度轮询 */
var picked=[],timer=null;
var drop=document.getElementById('drop'),picker=document.getElementById('picker');
var list=document.getElementById('filelist'),go=document.getElementById('go');
var log=document.getElementById('log'),msg=document.getElementById('msg');

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
function say(steps){
  log.style.display='block';
  log.textContent=steps.join('\n');
  log.scrollTop=log.scrollHeight;
}
function poll(){
  fetch('/api/status').then(function(r){return r.json();}).then(function(s){
    say(s.steps);
    if(s.error){
      msg.innerHTML='<span class="err">出错：'+s.error+'</span>';
      go.disabled=false;return;
    }
    if(s.running){timer=setTimeout(poll,800);return;}
    if(s.ready){
      msg.textContent='完成，正在打开报告…';
      location.href='/report';
    }
  }).catch(function(){timer=setTimeout(poll,1200);});
}

go.onclick=async function(){
  go.disabled=true;msg.textContent='读取文件…';log.style.display='block';
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
      body:JSON.stringify({files:files})
    });
    var j=await res.json();
    if(!j.ok) throw new Error(j.error||'上传失败');
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
