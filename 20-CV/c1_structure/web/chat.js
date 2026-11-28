(function(){
  'use strict';
  var file=null,currentIntent=null,fileId=null,phase='idle',timer=null;
  var planNode=null,progressNode=null,seenLogs=0,busy=false,expanded=false;
  var allowedFile=/\.(png|jpe?g|bmp|webp|tiff?|pdf|csv|txt|md)$/i,maxFileSize=20*1024*1024;
  var $=function(id){return document.getElementById(id);};
  var statusNames={ready:'等待确认',waiting_target:'等待选择目标表',target_missing:'目标表不存在',
    target_ambiguous:'目标表有歧义',mapping_incomplete:'需要完善字段映射',no_records:'没有抽取记录',
    rule_empty:'规则生成失败',loaded:'入库完成',loading:'入库中',error:'处理失败'};

  function api(url,options){
    options=options||{};
    return fetch(url,options).then(function(r){
      return r.json().catch(function(){return {};}).then(function(j){
        if(!r.ok||j.ok===false) throw new Error(j.error||j.message||('HTTP '+r.status));
        return j;
      });
    });
  }
  function scrollBottom(){
    requestAnimationFrame(function(){var box=$('messages');box.scrollTop=box.scrollHeight;});
  }
  function addMessage(role,html,cls){
    $('welcome').hidden=true;
    var row=document.createElement('div');row.className='msg '+role;
    var avatar=document.createElement('div');avatar.className='avatar';avatar.textContent=role==='user'?'我':'AI';
    var body=document.createElement('div');body.className=cls||'bubble';body.innerHTML=html;
    row.appendChild(avatar);row.appendChild(body);$('messages').appendChild(row);scrollBottom();return body;
  }
  function stateBadge(text,color){$('chatState').textContent=text;$('chatState').className='badge '+(color||'blue');}
  function setFile(f){
    file=f;$('fileChip').hidden=!f;
    if(f){$('fileName').textContent=f.name;$('fileSize').textContent=fmtSize(f.size);}
    else{$('fileInput').value='';}
    updateSend();
  }
  function chooseFile(f){
    if(!f)return;
    if(!allowedFile.test(f.name)){addMessage('assistant','<div class="result-box err">仅支持 PDF、图片、CSV 或文本文件。</div>');$('fileInput').value='';return;}
    if(!f.size||f.size>maxFileSize){addMessage('assistant','<div class="result-box err">附件不能为空，且大小不能超过 20MB。</div>');$('fileInput').value='';return;}
    setFile(f);
  }
  function updateSend(){
    $('send').disabled=busy||!file||!$('prompt').value.trim();
    $('send').textContent=phase==='loading'?'入库中…':(phase==='processing'?'处理中…':'发送');
  }
  function setComposerExpanded(value){
    expanded=!!value;var wrap=$('composerWrap'),button=$('expandComposer');
    wrap.classList.toggle('expanded',expanded);$('composerBackdrop').hidden=!expanded;
    button.setAttribute('aria-expanded',expanded?'true':'false');
    button.setAttribute('aria-label',expanded?'还原聊天输入框':'放大聊天输入框');
    button.title=expanded?'还原输入框':'放大输入框';
    if(expanded){
      wrap.setAttribute('role','dialog');wrap.setAttribute('aria-modal','true');
      wrap.setAttribute('aria-labelledby','composerTitle');$('prompt').focus();
    }else{
      wrap.removeAttribute('role');wrap.removeAttribute('aria-modal');wrap.removeAttribute('aria-labelledby');
      button.focus();
    }
  }
  function setBusy(v){
    busy=v;$('pickFile').disabled=v;$('newChat').disabled=v;updateSend();
  }
  function addProgress(label){
    var body=addMessage('assistant','','bubble progress-card');
    body.innerHTML='<div class="progress-top"><span class="spinner"></span><b>'+escHtml(label)+'</b></div>'+
      '<div class="progress-track"><div class="progress-bar"></div></div><div class="progress-log"></div>';
    progressNode={body:body,bar:body.querySelector('.progress-bar'),log:body.querySelector('.progress-log')};
    seenLogs=0;return progressNode;
  }
  function showProgress(status){
    if(!progressNode)return;
    progressNode.bar.style.width=Math.max(0,Math.min(100,Number(status.progress)||0))+'%';
    var logs=status.logs||[],fresh=logs.slice(seenLogs);seenLogs=logs.length;
    fresh.forEach(function(row){
      var line=document.createElement('div');line.textContent=row.msg||'';progressNode.log.appendChild(line);
    });
    progressNode.log.scrollTop=progressNode.log.scrollHeight;scrollBottom();
  }
  function stopProgress(error){
    if(!progressNode)return;
    var spinner=progressNode.body.querySelector('.spinner');if(spinner)spinner.remove();
    if(error){progressNode.body.querySelector('b').textContent='处理未完成';}
    progressNode.bar.style.width='100%';
  }
  function poll(){
    clearTimeout(timer);
    api('/api/status').then(function(status){
      if(status.file_id!==fileId)return;
      showProgress(status);
      if(status.running){timer=setTimeout(poll,1200);return;}
      stopProgress(status.error);
      if(phase==='loading'){finishLoad(status);return;}
      if(phase==='processing'){finishPlan(status);return;}
    }).catch(function(err){
      if(phase==='idle')return;
      stopProgress(err.message);stateBadge('连接中断','red');phase='idle';setBusy(false);
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function finishPlan(status){
    phase='idle';
    return api('/api/sources/'+fileId+'/load-plan').then(function(plan){
      currentIntent=plan;renderPlan(plan);
      stateBadge(statusNames[plan.status]||plan.status,plan.status==='ready'?'green':'yellow');
      if(status.error)addMessage('assistant','<div class="result-box err">'+escHtml(status.error)+'</div>');
      setBusy(false);
    }).catch(function(err){
      stateBadge('规划读取失败','red');setBusy(false);
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function send(){
    if(busy||!file||!$('prompt').value.trim())return;
    var description=$('prompt').value.trim();
    if(expanded)setComposerExpanded(false);
    addMessage('user','<span class="file-ref">附件：'+escHtml(file.name)+'</span>'+escHtml(description));
    var upload=file;setFile(null);$('prompt').value='';updateSend();
    currentIntent={description:description,auto_load:false};fileId=null;planNode=null;
    setBusy(true);stateBadge('正在上传','blue');addProgress('正在提交附件与处理需求');
    b64(upload).then(function(data){
      return api('/api/auto/process',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({files:[{name:upload.name,data:data}],intent:currentIntent})});
    }).then(function(result){
      fileId=result.file_id;currentIntent.file_id=fileId;phase='processing';
      stateBadge('正在解析与抽取','blue');progressNode.body.querySelector('b').textContent='正在解析文档、生成规则并抽取字段';
      poll();
    }).catch(function(err){
      stopProgress(err.message);phase='idle';setBusy(false);stateBadge('提交失败','red');
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function replan(patch,button){
    if(!fileId||busy)return;
    setBusy(true);if(button)button.disabled=true;
    currentIntent=Object.assign({},currentIntent,patch,{auto_load:false});
    api('/api/sources/'+fileId+'/load-plan',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({intent:currentIntent})}).then(function(plan){
      currentIntent=plan;renderPlan(plan);stateBadge(statusNames[plan.status]||plan.status,plan.status==='ready'?'green':'yellow');
      setBusy(false);
    }).catch(function(err){
      setBusy(false);if(button)button.disabled=false;
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function renderPlan(plan){
    var old=planNode;planNode=addMessage('assistant','','plan-card');
    if(old)old.remove();
    var status=statusNames[plan.status]||plan.status;
    var html='<div class="plan-head"><b>处理方案</b><span class="spacer"></span>'+
      '<span class="badge '+(plan.status==='ready'?'green':'yellow')+'">'+escHtml(status)+'</span></div><div class="plan-body">'+
      '<p>'+escHtml(plan.message||'')+'</p>';
    var target=plan.target||{},mapping=plan.mapping||{};
    if(target.table)html+='<dl class="kv-grid"><dt>目标表</dt><dd>'+escHtml(target.table)+
      ' <span class="muted">数据源 #'+escHtml(target.datasource_id)+'</span></dd>'+
      '<dt>写入方式</dt><dd>'+escHtml(mapping.write_mode||'—')+'</dd></dl>';
    var fields=(mapping.fields||[]);
    if(fields.length){
      html+='<div class="plan-section"><h3>抽取字段（'+fields.length+'）</h3><div class="field-chips">'+
        fields.map(function(f){return '<span>'+escHtml(f.name)+'</span>';}).join('')+'</div></div>';
      html+='<div class="plan-section"><h3>数据预览</h3><div class="tblscroll"><table class="list"><thead><tr>'+
        fields.map(function(f){return '<th>'+escHtml(f.name)+'</th>';}).join('')+
        '</tr></thead><tbody><tr>'+fields.map(function(f){return '<td>'+escHtml((f.samples||[])[0]||'—')+'</td>';}).join('')+
        '</tr></tbody></table></div><p style="margin:7px 0 0">共 '+escHtml(mapping.record_count||'—')+
        ' 条记录 · <a href="/preview?file='+fileId+'" target="_blank">打开完整预览与血缘 →</a></p></div>';
    }
    var recs=plan.recommendations||[];
    if(recs.length){
      html+='<div class="plan-section"><h3>推荐目标表</h3><div class="rec-list">'+recs.map(function(r,i){
        return '<div class="rec-item"><div class="rec-info"><b>'+escHtml(r.table)+'</b><span>数据源 #'+
          escHtml(r.datasource_id)+' · 匹配度 '+Math.round(Number(r.score||0)*100)+'%'+
          (r.comment?' · '+escHtml(r.comment):'')+'</span></div><button type="button" class="btn ghost mini" data-choose="'+i+'">选择此表</button></div>';
      }).join('')+'</div></div>';
    }
    if(mapping.field_map){
      var fmap=mapping.field_map||{},conf=mapping.confidence||{},amb=mapping.ambiguous_fields||{};
      var names=Object.keys(fmap);(mapping.unmapped_fields||[]).forEach(function(n){if(names.indexOf(n)<0)names.push(n);});
      html+='<div class="plan-section"><h3>字段映射</h3><table class="mapping-table"><thead><tr><th>中文字段</th><th>数据库列</th><th>置信度</th></tr></thead><tbody>'+
        names.map(function(name){
          var note=amb[name]?'有歧义，请选择':(!fmap[name]?'待映射':'');
          return '<tr><td>'+escHtml(name)+'</td><td><input data-field="'+escHtml(name)+'" value="'+escHtml(fmap[name]||'')+'" placeholder="填写数据库列名"></td>'+
            '<td class="'+(note?'warn-text':'muted')+'">'+escHtml(note||Math.round(Number(conf[name]||0)*100)+'%')+'</td></tr>';
        }).join('')+'</tbody></table>';
      if(mapping.unmapped_fields&&mapping.unmapped_fields.length)html+='<p style="margin:7px 0 0;color:var(--c1-warning)">未映射：'+escHtml(mapping.unmapped_fields.join('、'))+'</p>';
      html+='<div class="plan-actions"><button type="button" class="btn ghost mini" data-save-map>保存并重新检查</button>'+
        '<span class="muted">映射仅在确认方案后写入</span></div></div>';
    }
    if(plan.warnings&&plan.warnings.length)html+='<div class="plan-section"><h3>提示</h3>'+
      plan.warnings.map(function(w){return '<p>· '+escHtml(w)+'</p>';}).join('')+'</div>';
    if(plan.status==='ready')html+='<div class="plan-actions"><button type="button" class="btn" data-confirm>确认并写入数据库</button>'+
      '<span class="muted">将向 '+escHtml(target.table)+' 执行 '+escHtml(mapping.write_mode||'insert')+'</span></div>';
    html+='</div>';planNode.innerHTML=html;
    planNode.querySelectorAll('[data-choose]').forEach(function(btn){
      btn.onclick=function(){var r=recs[Number(btn.getAttribute('data-choose'))];
        replan({target_table:r.table,datasource_id:r.datasource_id,field_map:{}},btn);};
    });
    var save=planNode.querySelector('[data-save-map]');
    if(save)save.onclick=function(){
      var patch={field_map:{}};
      planNode.querySelectorAll('[data-field]').forEach(function(input){
        var value=input.value.trim();if(value)patch.field_map[input.getAttribute('data-field')]=value;
      });replan(patch,save);
    };
    var confirm=planNode.querySelector('[data-confirm]');
    if(confirm)confirm.onclick=confirmLoad;
    scrollBottom();
  }
  function confirmLoad(){
    if(busy||!fileId)return;
    var button=planNode&&planNode.querySelector('[data-confirm]');
    var plan=currentIntent||{},target=plan.target||{};
    if(!window.confirm('确认将抽取结果写入 '+target.table+'（数据源 #'+target.datasource_id+'）？\n此操作会修改业务数据库。'))return;
    setBusy(true);if(button)button.disabled=true;addProgress('正在创建入库映射并写入数据库');
    api('/api/sources/'+fileId+'/load-plan/apply',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({intent:Object.assign({},currentIntent,{auto_load:false})})}).then(function(){
      phase='loading';stateBadge('正在入库','cyan');poll();
    }).catch(function(err){
      stopProgress(err.message);phase='idle';setBusy(false);if(button)button.disabled=false;stateBadge('入库未启动','red');
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function finishLoad(status){
    phase='idle';setBusy(false);stateBadge(status.error?'入库失败':'入库完成',status.error?'red':'green');
    api('/api/sources/'+fileId).then(function(detail){
      var f=detail.file||{},load=f.load||{};
      var html='<div class="result-box '+(f.state==='failed'?'err':'')+'"><b>'+(f.state==='failed'?'入库失败':'入库完成')+'</b><br>'+
        '目标：'+escHtml(load.target_table||'—')+'<br>资料状态：'+escHtml(f.state)+
        '<br><a href="/preview?file='+fileId+'" target="_blank">查看记录与入库血缘 →</a></div>';
      addMessage('assistant',html);
      if(f.error)addMessage('assistant','<div class="result-box err">'+escHtml(f.error)+'</div>');
    }).catch(function(err){addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');});
  }
  function newChat(){
    if(busy)return;
    if(expanded)setComposerExpanded(false);
    clearTimeout(timer);fileId=null;currentIntent=null;phase='idle';planNode=null;progressNode=null;setFile(null);
    $('prompt').value='';$('messages').querySelectorAll('.msg').forEach(function(n){n.remove();});
    $('welcome').hidden=false;stateBadge('准备就绪','blue');updateSend();
  }
  $('pickFile').onclick=function(){$('fileInput').click();};
  $('fileInput').onchange=function(){chooseFile(this.files[0]);};
  $('removeFile').onclick=function(){setFile(null);};
  $('expandComposer').onclick=function(){setComposerExpanded(!expanded);};
  $('collapseComposer').onclick=function(){setComposerExpanded(false);};
  $('composerBackdrop').onclick=function(){setComposerExpanded(false);};
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&expanded){e.preventDefault();setComposerExpanded(false);return;}
    if(e.key!=='Tab'||!expanded)return;
    var nodes=Array.prototype.filter.call($('composerWrap').querySelectorAll('button:not([disabled]),textarea:not([disabled]),input:not([disabled])'),function(node){return node.getClientRects().length>0;});
    if(!nodes.length)return;var first=nodes[0],last=nodes[nodes.length-1];
    if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}
  });
  $('send').onclick=send;
  $('newChat').onclick=newChat;
  $('prompt').oninput=updateSend;
  $('prompt').onkeydown=function(e){if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();send();}};
  document.querySelectorAll('[data-example]').forEach(function(btn){
    btn.onclick=function(){if(busy)return;$('prompt').value=btn.getAttribute('data-example');updateSend();$('prompt').focus();};
  });
  ['dragenter','dragover'].forEach(function(ev){$('dropZone').addEventListener(ev,function(e){e.preventDefault();if(!busy)$('dropZone').classList.add('on');});});
  ['dragleave','drop'].forEach(function(ev){$('dropZone').addEventListener(ev,function(e){e.preventDefault();$('dropZone').classList.remove('on');});});
  $('dropZone').addEventListener('drop',function(e){var f=e.dataTransfer.files[0];if(f&&!busy)chooseFile(f);});
  stateBadge('准备就绪','blue');updateSend();
})();
