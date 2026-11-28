(function(){
  'use strict';
  var file=null,currentIntent=null,currentPlan=null,fileId=null,phase='idle',timer=null;
  var planNode=null,progressNode=null,seenLogs=0,busy=false,expanded=false;
  var stageNodes={},stagePending={},tableOptions=null;
  var allowedFile=/\.(png|jpe?g|bmp|webp|tiff?|pdf|csv|txt|md)$/i,maxFileSize=20*1024*1024;
  var $=function(id){return document.getElementById(id);};
  var statusNames={ready:'等待确认',waiting_target:'等待选择目标表',target_missing:'目标表不存在',
    target_ambiguous:'目标表有歧义',mapping_incomplete:'请选择入库字段',no_records:'没有抽取记录',
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
      if(row.event==='parse_complete')loadStageResult('parse');
      if(row.event==='extract_complete')loadStageResult('extract');
    });
    progressNode.log.scrollTop=progressNode.log.scrollHeight;scrollBottom();
  }
  function stopProgress(error){
    if(!progressNode)return;
    var spinner=progressNode.body.querySelector('.spinner');if(spinner)spinner.remove();
    if(error){progressNode.body.querySelector('b').textContent='处理未完成';}
    progressNode.bar.style.width='100%';
  }
  function renderStageResult(kind,data){
    if(!data||!['ready','empty'].includes(data.status))return;
    if(stageNodes[kind])stageNodes[kind].remove();
    var body=addMessage('assistant','','stage-card');
    stageNodes[kind]=body;
    if(kind==='parse'){
      var report=data.report_available?' · <a href="/files/'+fileId+'/'+encodeURIComponent('对照报告.html')+'" target="_blank">打开对照报告 →</a>':'';
      body.innerHTML='<div class="stage-head"><span class="badge green">解析完成</span><b>'+escHtml(data.file_name||'附件')+'</b></div>'+
        '<div class="stage-stats"><span><b>'+escHtml(data.page_count||0)+'</b> 页</span><span><b>'+escHtml(data.text_fragments||0)+'</b> 个文本片段</span><span><b>'+escHtml(data.table_count||0)+'</b> 张表</span></div>'+
        '<p class="muted">文本块 '+escHtml(data.blocks||0)+' · 文本约 '+escHtml(data.text_chars||0)+' 字'+report+'</p>';
      return;
    }
    var fields=data.fields||[],samples=data.samples||[];
    var html='<div class="stage-head"><span class="badge green">抽取完成</span><b>'+escHtml(data.record_count||0)+' 条记录</b></div>'+
      '<div class="field-chips">'+fields.map(function(name){return '<span>'+escHtml(name)+'</span>';}).join('')+'</div>';
    if(fields.length&&samples.length){
      html+='<div class="tblscroll stage-sample"><table class="list"><thead><tr>'+fields.map(function(name){return '<th>'+escHtml(name)+'</th>';}).join('')+
        '</tr></thead><tbody>'+samples.map(function(row){return '<tr>'+fields.map(function(name){var value=row[name];return '<td>'+escHtml(value===undefined||value===null||value===''?'—':value)+'</td>';}).join('')+'</tr>';}).join('')+
        '</tbody></table></div><p class="muted">仅展示前 '+samples.length+' 条样例 · 有血缘记录 '+escHtml(data.anchored_records||0)+' 条</p>';
    }else{html+='<p class="muted">没有可展示的抽取记录。</p>';}
    html+='<p class="muted"><a href="/preview?file='+fileId+'" target="_blank">打开完整结果、血缘与复核 →</a></p>';
    body.innerHTML=html;
  }
  function loadStageResult(kind){
    if(stageNodes[kind])return Promise.resolve();
    if(kind==='extract'&&stagePending.parse)return stagePending.parse.then(function(){return loadStageResult('extract');});
    if(!fileId)return Promise.resolve();
    if(stagePending[kind])return stagePending[kind];
    stagePending[kind]=api('/api/sources/'+fileId+'/stage-results').then(function(result){
      renderStageResult(kind,result[kind]);
    }).catch(function(err){
      addMessage('assistant','<div class="result-box err">'+escHtml((kind==='parse'?'解析':'抽取')+'结果读取失败：'+err.message)+'</div>');
    }).finally(function(){stagePending[kind]=null;});
    return stagePending[kind];
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
      currentPlan=plan;renderPlan(plan);
      stateBadge(statusNames[plan.status]||plan.status,plan.status==='ready'?'green':'yellow');
      loadStageResult('parse');loadStageResult('extract');
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
    currentIntent={description:description,auto_load:false};currentPlan=null;fileId=null;planNode=null;
    stageNodes={};stagePending={};tableOptions=null;
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
    var next=Object.assign({},currentIntent);
    Object.keys(patch).forEach(function(key){if(patch[key]===null)delete next[key];else next[key]=patch[key];});
    currentIntent=Object.assign(next,{auto_load:false});
    delete currentIntent.mapping;delete currentIntent.confirmed;
    api('/api/sources/'+fileId+'/load-plan',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({intent:currentIntent})}).then(function(plan){
      currentPlan=plan;renderPlan(plan);stateBadge(statusNames[plan.status]||plan.status,plan.status==='ready'?'green':'yellow');
      setBusy(false);
    }).catch(function(err){
      setBusy(false);if(button)button.disabled=false;
      addMessage('assistant','<div class="result-box err">'+escHtml(err.message)+'</div>');
    });
  }
  function addSelectOption(select,value,label){
    var option=document.createElement('option');option.value=String(value);option.textContent=label;select.appendChild(option);
  }
  function fillOtherTables(panel){
    var dsSelect=panel.querySelector('[data-other-datasource]'),tableSelect=panel.querySelector('[data-other-table]');
    var status=panel.querySelector('[data-other-status]'),button=panel.querySelector('[data-choose-other]');
    var previous=dsSelect.value;dsSelect.innerHTML='';tableSelect.innerHTML='';button.disabled=true;
    (tableOptions.datasources||[]).forEach(function(ds){addSelectOption(dsSelect,ds.id,ds.name+' (#'+ds.id+')');});
    if(previous&&tableOptions.datasources.some(function(ds){return String(ds.id)===previous;}))dsSelect.value=previous;
    function fillTables(){
      tableSelect.innerHTML='';button.disabled=true;
      var items=(tableOptions.tables||[]).filter(function(item){return String(item.datasource_id)===dsSelect.value;});
      items.forEach(function(item){addSelectOption(tableSelect,item.table,item.table);});
      if(items.length){button.disabled=false;status.textContent='共 '+items.length+' 张业务表';}
      else{addSelectOption(tableSelect,'','该业务库没有可选业务表');status.textContent='该业务库没有可选业务表';}
    }
    dsSelect.onchange=fillTables;fillTables();
    if(tableOptions.warnings&&tableOptions.warnings.length)status.textContent+='；'+tableOptions.warnings.join('；');
  }
  function openOtherTables(panel,button){
    panel.hidden=false;button.hidden=true;
    if(tableOptions){fillOtherTables(panel);return;}
    api('/api/load/business-table-options').then(function(result){
      tableOptions=result;fillOtherTables(panel);
    }).catch(function(err){
      panel.querySelector('[data-other-status]').textContent='业务表读取失败：'+err.message;
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
    html+='<div class="plan-section other-tables"><h3>其他目标表</h3>'+
      '<p>推荐列表没有需要的表？可从业务库已有表中选择；平台产品配置表不会列出。</p>'+
      '<button type="button" class="btn ghost mini" data-other-tables>选择其他现有表</button>'+
      '<div class="other-table-panel" data-other-panel hidden>'+
      '<label>业务库<select data-other-datasource></select></label>'+
      '<label>目标表<select data-other-table></select></label>'+
      '<div class="plan-actions"><button type="button" class="btn mini" data-choose-other disabled>使用此表重新规划</button>'+
      '<span class="muted" data-other-status>正在读取业务表…</span></div></div></div>';
    if(mapping.field_map){
      var fmap=mapping.field_map||{},conf=mapping.confidence||{},amb=mapping.ambiguous_fields||{};
      var names=Object.keys(fmap);(mapping.unmapped_fields||[]).forEach(function(n){if(names.indexOf(n)<0)names.push(n);});
      html+='<div class="plan-section"><h3>字段映射</h3>'+
        '<p class="muted">已预填高置信度建议；勾选需要入库的字段，至少选择一个。</p>'+
        '<table class="mapping-table"><thead><tr><th>入库</th><th>中文字段</th><th>数据库列</th><th>置信度</th></tr></thead><tbody>'+
        names.map(function(name){
          var selected=!!fmap[name];
          return '<tr><td><input type="checkbox" data-load-field="'+escHtml(name)+'"'+(selected?' checked':'')+' aria-label="入库字段 '+escHtml(name)+'"></td>'+
            '<td>'+escHtml(name)+'</td><td><select data-field="'+escHtml(name)+'"'+(selected?'':' disabled')+'></select></td>'+
            '<td data-confidence="'+escHtml(name)+'" class="muted">'+(selected?escHtml(amb[name]?'建议候选，请确认':Math.round(Number(conf[name]||0)*100)+'%'):'')+'</td></tr>';
        }).join('')+'</tbody></table>';
      html+='<div class="plan-actions"><button type="button" class="btn ghost mini" data-save-map>保存并重新检查</button>'+
        '<span class="muted">仅所选字段会在确认后写入</span></div></div>';
    }
    if(plan.warnings&&plan.warnings.length)html+='<div class="plan-section"><h3>提示</h3>'+
      plan.warnings.map(function(w){return '<p>· '+escHtml(w)+'</p>';}).join('')+'</div>';
    if(plan.status==='ready')html+='<div class="plan-actions"><button type="button" class="btn" data-confirm>确认并写入数据库</button>'+
      '<span class="muted">将向 '+escHtml(target.table)+' 执行 '+escHtml(mapping.write_mode||'insert')+'</span></div>';
    html+='</div>';planNode.innerHTML=html;
    if(mapping.field_map){
      var fmap=mapping.field_map||{},amb=mapping.ambiguous_fields||{};
      var columns=mapping.available_columns||[];
      planNode.querySelectorAll('[data-field]').forEach(function(select){
        var name=select.getAttribute('data-field');
        var suggested=(amb[name]||[]).map(function(item){return item.target_column;});
        var ordered=suggested.slice();
        columns.forEach(function(column){
          if(ordered.indexOf(column.name)<0)ordered.push(column.name);
        });
        ordered.forEach(function(columnName){
          var column=columns.filter(function(item){return item.name===columnName;})[0]||{};
          addSelectOption(select,columnName,columnName+(column.comment?' · '+column.comment:''));
        });
        if(fmap[name])select.value=fmap[name];
        else{
          var preferred=ordered.filter(function(columnName){
            var column=columns.filter(function(item){return item.name===columnName;})[0];
            return column&&!column.primary&&column.default==null;
          });
          if(preferred.length)select.value=preferred[0];
          else if(ordered.length)select.value=ordered[0];
        }
      });
      planNode.querySelectorAll('[data-load-field]').forEach(function(checkbox){
        checkbox.onchange=function(){
          var name=checkbox.getAttribute('data-load-field');
          var select=planNode.querySelector('[data-field="'+CSS.escape(name)+'"]');
          var confidence=planNode.querySelector('[data-confidence="'+CSS.escape(name)+'"]');
          select.disabled=!checkbox.checked;
          if(!checkbox.checked){confidence.textContent='';return;}
          var suggestion=(amb[name]||[])[0];
          confidence.textContent=amb[name]?'建议候选，请确认':
            Math.round(Number((suggestion&&suggestion.confidence)||conf[name]||0)*100)+'%';
        };
      });
    }
    planNode.querySelectorAll('[data-choose]').forEach(function(btn){
      btn.onclick=function(){var r=recs[Number(btn.getAttribute('data-choose'))];
        replan({target_table:r.table,datasource_id:r.datasource_id,field_map:null,field_aliases:null},btn);};
    });
    var other=planNode.querySelector('[data-other-tables]'),otherPanel=planNode.querySelector('[data-other-panel]');
    if(other)other.onclick=function(){openOtherTables(otherPanel,other);};
    var chooseOther=planNode.querySelector('[data-choose-other]');
    if(chooseOther)chooseOther.onclick=function(){
      var ds=otherPanel.querySelector('[data-other-datasource]').value;
      var table=otherPanel.querySelector('[data-other-table]').value;
      if(!ds||!table)return;
      replan({target_table:table,datasource_id:Number(ds),field_map:null,field_aliases:null},chooseOther);
    };
    var save=planNode.querySelector('[data-save-map]');
    if(save)save.onclick=function(){
      var patch={field_map:{}};
      planNode.querySelectorAll('[data-load-field]').forEach(function(checkbox){
        if(!checkbox.checked)return;
        var input=planNode.querySelector('[data-field="'+CSS.escape(checkbox.getAttribute('data-load-field'))+'"]');
        var value=input.value.trim();if(value)patch.field_map[checkbox.getAttribute('data-load-field')]=value;
      });replan(patch,save);
    };
    var confirm=planNode.querySelector('[data-confirm]');
    if(confirm)confirm.onclick=confirmLoad;
    scrollBottom();
  }
  function confirmLoad(){
    if(busy||!fileId)return;
    var button=planNode&&planNode.querySelector('[data-confirm]');
    var plan=currentPlan||{},target=plan.target||{};
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
    clearTimeout(timer);fileId=null;currentIntent=null;currentPlan=null;phase='idle';planNode=null;progressNode=null;
    stageNodes={};stagePending={};tableOptions=null;setFile(null);
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
