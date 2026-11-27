/* web/compute.js — 计算资产库 + 计算流程配置 + 抽屉编辑 + 追溯 + 复核。 */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var PFX={source:'d',index:'i',rule:'r',frame:'f'};
  var LABEL={document:'文档',source:'数据',index:'指标',rule:'规则',frame:'框架'};
  var VFIELD={index:'index_value',rule:'rule_value',frame:'frame_value'};
  var defs={source:[],document:[],index:[],rule:[],frame:[]},documentLinks=[];
  var editing={index:null,rule:null,frame:null};
  var editingScope='index',layout={},layoutAvailable=true,saveTimer=null;
  var LOCAL_KEY='c1.compute.layout';
  var loadSeq=0,lineageSeq=0,lineageState=null,tableComments={},runAllRunning=false,computeLoaded=false;
  var assetClickTimer=null,lineageTableCache={},lineageRecordMaps={},layoutDirty=false,layoutSaving=false;
  var lineageTraceCache={},lineageTracePending={},TRACE_SKIP_COLS={file_id:true,record_id:true};

  function api(path,opt){
    return fetch(path,opt||{}).then(function(r){
      return r.json().then(function(j){
        if(!r.ok||j.ok===false) throw new Error(j.error||('HTTP '+r.status));
        return j;
      });
    });
  }
  function post(path,body){
    return api(path,{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body||{})});
  }
  function esc(s){return escHtml(s);}
  function tableLabel(datasourceId,table){return tableComments[datasourceId+':'+table]||table;}
  function scopeIcon(scope){return window.ComputeScopeIcon(scope,'scope-icon asset-scope-icon');}
  function say(kind,msg){
    var e=$(kind==='err'?'err':'ok');
    e.textContent=msg;e.hidden=false;
    setTimeout(function(){e.hidden=true;},2600);
  }
  function err(msg){say('err',msg);}
  function ok(msg){say('ok',msg);}
  function aggLabel(a){return {sum:'求和',count:'计数',avg:'平均',min:'最小',
    max:'最大',count_distinct:'去重计数'}[a]||a;}
  function opLabel(o){return {gt:'>',gte:'≥',lt:'<',lte:'≤',eq:'=',ne:'≠',between:'介于'}[o]||o;}
  function combineLabel(c){return {weighted:'加权得分',all_pass:'全部通过',
    any_pass:'任一通过',veto:'一票否决',all:'全部满足',any:'任一满足'}[c]||c;}
  function resultStatus(value){
    var text=String(value==null?'':value).trim().toLowerCase();
    if(/^pass(?:\s*[（(]|$)/.test(text))return 'pass';
    if(/^fail(?:\s*[（(]|$)/.test(text))return 'fail';
    return '';
  }
  function resultDisplay(scope,d){
    if(!d||!d._latest)return '';
    var value=d._latest[VFIELD[scope]];
    return resultStatus(value)||String(value==null?'':value);
  }
  function openEl(id){
    if(typeof animDrawerOpen==='function')animDrawerOpen($(id));else $(id).hidden=false;
  }
  function closeEl(id){
    if(typeof animDrawerClose==='function')animDrawerClose($(id));else $(id).hidden=true;
  }
  $('de-close').onclick=function(){closeEl('ded');};
  $('tr-close').onclick=function(){closeEl('trace');};
  $('view-close').onclick=function(){closeEl('compute-view');};
  $('lineage-close').onclick=function(){closeLineage();closeEl('lineage');};
  $('lineage').addEventListener('click',function(e){if(e.target===this){closeLineage();closeEl('lineage');}});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&!$('lineage').hidden&&!document.querySelector('.drawer:not([hidden]):not(#lineage)')){
      closeLineage();closeEl('lineage');
    }
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-lineage-tab]'),function(btn){
    btn.onclick=function(){setLineageTab(btn.dataset.lineageTab);};
  });

  function sendLineageTrace(frame,trace){
    if(!frame||!frame.contentWindow)return;
    frame.dataset.skipPin='1';
    setTimeout(function(){delete frame.dataset.skipPin;},1200);
    try{frame.contentWindow.postMessage({c1TraceKey:trace},location.origin);}catch(e){delete frame.dataset.skipPin;}
  }
  function sendLineageTraceBatch(frame,batch){
    if(!frame)return;
    if(!frame.contentWindow||frame.dataset.ready!=='1'){
      frame.dataset.pendingBatch=JSON.stringify(batch||{items:[]});return;
    }
    try{frame.contentWindow.postMessage({c1TraceBatch:batch||{items:[]}},location.origin);}
    catch(e){frame.dataset.pendingBatch=JSON.stringify(batch||{items:[]});}
  }
  function clearLineageTraceBatch(frame){
    if(!frame)return;
    delete frame.dataset.pendingBatch;
    if(frame.contentWindow&&frame.dataset.ready==='1'){
      try{frame.contentWindow.postMessage({c1TraceBatchClear:true},location.origin);}catch(e){}
    }
  }
  function bindLineageFrame(frame){
    if(!frame||frame.dataset.bound==='1')return;
    frame.dataset.bound='1';
    frame.addEventListener('load',function(){
      frame.dataset.ready='1';
      var pending=frame.dataset.pendingTrace;
      if(pending){
        delete frame.dataset.pendingTrace;
        sendLineageTrace(frame,JSON.parse(pending));
      }
      var pendingBatch=frame.dataset.pendingBatch;
      if(pendingBatch){
        delete frame.dataset.pendingBatch;
        sendLineageTraceBatch(frame,JSON.parse(pendingBatch));
      }
    });
  }
  function lineageFrameByWindow(win){
    var current=$('lineage-document-frame');
    if(current&&current.contentWindow===win)return current;
    return Array.prototype.filter.call(document.querySelectorAll('.lineage-upstream-frame'),function(frame){
      return frame.contentWindow===win;
    })[0]||null;
  }
  bindLineageFrame($('lineage-document-frame'));
  window.addEventListener('message',function(e){
    if(!lineageState||e.origin!==location.origin||!e.data||!e.data.c1PinField)return;
    var frame=lineageFrameByWindow(e.source);
    if(!frame||frame.hidden)return;
    if(frame.dataset.skipPin==='1'){delete frame.dataset.skipPin;return;}
    handleSourcePin(frame,String(frame.dataset.file||''),e.data.c1PinField);
  });

  var graph=new ComputeGraph($('graph-canvas'),{
    action:nodeAction,menu:openNodeMenu,select:selectNode,trace:openLineage,
    connect:connectNodes,disconnect:disconnectEdge,layout:queueLayoutSave
  });
  var lineageGraph=new ComputeGraph($('lineage-graph'),{
    select:function(scope,id){renderLineageDetails(scope,id);}
  },{compact:true});
  $('zoom-in').onclick=function(){graph.zoom(1.15);};
  $('zoom-out').onclick=function(){graph.zoom(1/1.15);};
  $('graph-fit').onclick=function(){graph.fit();};
  $('graph-auto').onclick=function(){graph.autoLayout();ok('已自动排布');};
  $('edge-del').onclick=function(){graph.deleteSelected();};
  $('graph-run-all').addEventListener('pointerdown',function(e){e.stopPropagation();});
  $('graph-run-all').onclick=runAllDefinitions;
  $('layout-save').onclick=function(){saveLayout(true);};

  (function(){
    var workspace=document.querySelector('.compute-workspace'),
      divider=$('assetDivider'),button=$('assetCollapse'),
      WKEY='c1.compute.assetWidth',CKEY='c1.compute.assetCollapsed',MIN=190,MAX=420,drag=null;
    function maxWidth(){return Math.max(MIN,Math.min(MAX,workspace.clientWidth-480));}
    function applyWidth(width,save){
      var w=Math.round(Math.max(MIN,Math.min(maxWidth(),width)));
      workspace.style.setProperty('--c1-asset-width',w+'px');
      if(save)try{localStorage.setItem(WKEY,String(w));}catch(e){}
    }
    function setCollapsed(collapsed,save){
      workspace.classList.toggle('is-collapsed',collapsed);
      button.textContent=collapsed?'›':'‹';
      button.title=collapsed?'展开侧栏':'收起侧栏';
      button.setAttribute('aria-label',collapsed?'展开计算资产栏':'收起计算资产栏');
      button.setAttribute('aria-expanded',String(!collapsed));
      if(save)try{localStorage.setItem(CKEY,collapsed?'1':'0');}catch(e){}
    }
    try{
      var savedWidth=parseInt(localStorage.getItem(WKEY),10);
      if(savedWidth)applyWidth(savedWidth,false);
      setCollapsed(localStorage.getItem(CKEY)==='1',false);
    }catch(e){}
    button.addEventListener('pointerdown',function(e){e.stopPropagation();});
    button.onclick=function(){setCollapsed(!workspace.classList.contains('is-collapsed'),true);};
    divider.addEventListener('pointerdown',function(e){
      if(e.button!==0||getComputedStyle(divider).display==='none')return;
      if(workspace.classList.contains('is-collapsed'))setCollapsed(false,true);
      drag={id:e.pointerId,x:e.clientX,width:parseFloat(getComputedStyle(workspace).getPropertyValue('--c1-asset-width'))||248};
      divider.setPointerCapture(e.pointerId);divider.classList.add('on');
      document.body.style.userSelect='none';document.body.style.cursor='col-resize';e.preventDefault();
    });
    divider.addEventListener('pointermove',function(e){
      if(!drag||drag.id!==e.pointerId)return;
      applyWidth(drag.width+e.clientX-drag.x,false);
    });
    function endDrag(e){
      if(!drag||drag.id!==e.pointerId)return;
      drag=null;divider.classList.remove('on');
      document.body.style.userSelect='';document.body.style.cursor='';
      applyWidth(parseFloat(workspace.style.getPropertyValue('--c1-asset-width')),true);
    }
    divider.addEventListener('pointerup',endDrag);
    divider.addEventListener('pointercancel',endDrag);
    window.addEventListener('resize',function(){
      if(workspace.style.getPropertyValue('--c1-asset-width'))
        applyWidth(parseFloat(workspace.style.getPropertyValue('--c1-asset-width')),false);
    });
  })();

  // ---------- 指标表单 ----------
  function loadDatasources(){
    return api('/api/load/datasources').then(function(j){
      var sel=$('i-ds'),keep=sel.value;
      sel.innerHTML='<option value="">请选择</option>'+(j.items||[]).map(function(d){
        return '<option value="'+d.id+'">'+esc(d.name||d.db_name)+' · '+esc(d.db_name)+'</option>';
      }).join('');
      if(keep)sel.value=keep;
    });
  }
  function selectTables(ds,keep){
    var t=$('i-table');
    t.innerHTML='<option value="">加载中…</option>';
    if(!ds){t.innerHTML='<option value="">先选业务库</option>';return Promise.resolve();}
    return api('/api/load/datasources/'+ds+'/tables?include_comment=1').then(function(j){
      var rows=j.items||[],names=rows.map(function(x){return typeof x==='string'?x:x.name;});
      t.innerHTML='<option value="">请选择</option>'+rows.map(function(x){
        var name=typeof x==='string'?x:x.name;
        return '<option value="'+esc(name)+'">'+esc(typeof x==='string'?x:(x.table_comment||x.name))+'</option>';
      }).join('');
      if(keep&&names.indexOf(keep)>=0)t.value=keep;
    }).catch(function(e){err(e.message);});
  }
  function selectColumns(ds,table,keep){
    var c=$('i-column');
    c.innerHTML='<option value="">加载中…</option>';
    if(!ds||!table){c.innerHTML='<option value="">先选业务表</option>';return Promise.resolve();}
    return api('/api/load/datasources/'+ds+'/columns?table='+encodeURIComponent(table))
      .then(function(j){
        var cols=j.items||[];
        c.innerHTML='<option value="">（留空＝统计整行）</option>'+cols.map(function(x){
          return '<option value="'+esc(x.name)+'">'+esc(x.name)+' · '+esc(x.type)+'</option>';
        }).join('');
        if(keep)c.value=keep;
      }).catch(function(e){err(e.message);});
  }
  $('i-ds').onchange=function(){selectTables(this.value,'');};
  $('i-table').onchange=function(){selectColumns($('i-ds').value,this.value,'');};
  function addFilterRow(f){
    var d=document.createElement('div');d.className='filterrow';
    d.innerHTML='<input class="tin" placeholder="列名" data-k="c">'+
      '<select class="tin" data-k="o"><option value="eq">=</option><option value="ne">≠</option>'+
      '<option value="gt">&gt;</option><option value="gte">≥</option><option value="lt">&lt;</option>'+
      '<option value="lte">≤</option></select><input class="tin" placeholder="值" data-k="v">'+
      '<button type="button" class="btn mini ghost" data-k="x">×</button>';
    if(f){
      d.querySelector('[data-k=c]').value=f.column||'';
      d.querySelector('[data-k=o]').value=f.op||'eq';
      d.querySelector('[data-k=v]').value=Array.isArray(f.value)?f.value.join(','):(f.value==null?'':f.value);
    }
    d.querySelector('[data-k=x]').onclick=function(){d.parentNode.removeChild(d);};
    $('i-filters').appendChild(d);return d;
  }
  $('i-addfilter').onclick=function(){addFilterRow();};

  // ---------- 规则 / 框架表单 ----------
  function indexOptions(){
    return '<option value="">请选择</option>'+defs.index.map(function(d){
      return '<option value="'+d.id+'">'+esc(d.name)+' · '+esc(aggLabel(d.aggregate))+'</option>';
    }).join('');
  }
  function addConditionRow(c){
    var n=$('r-conditions').children.length+1,row=document.createElement('div');
    row.className='conditionrow';
    row.innerHTML='<select class="tin" data-k="i">'+indexOptions()+'</select>'+
      '<input class="tin" data-k="a" placeholder="m'+n+'">'+
      '<select class="tin" data-k="o"><option value="gt">大于</option><option value="gte">大于等于</option>'+
      '<option value="lt">小于</option><option value="lte">小于等于</option><option value="eq">等于</option>'+
      '<option value="ne">不等于</option><option value="between">介于区间</option></select>'+
      '<input class="tin" data-k="t" placeholder="100 或 100,200">'+
      '<button type="button" class="btn mini ghost" data-k="x" data-tip="删除条件">×</button>';
    if(c){
      row.querySelector('[data-k=i]').value=c.index_id||'';
      row.querySelector('[data-k=a]').value=c.alias||'';
      row.querySelector('[data-k=o]').value=c.op||'gt';
      row.querySelector('[data-k=t]').value=Array.isArray(c.threshold)?c.threshold.join(','):
        (c.threshold==null?'':c.threshold);
    }else row.querySelector('[data-k=a]').value='m'+n;
    row.querySelector('[data-k=x]').onclick=function(){row.parentNode.removeChild(row);};
    $('r-conditions').appendChild(row);return row;
  }
  $('r-addcondition').onclick=function(){addConditionRow();};
  function ruleConditions(d){
    return (d.conditions_json||[]).map(function(c){
      var ref=(d.index_refs_json||[]).filter(function(r){return r.alias===c.alias;})[0]||{};
      return {index_id:ref.index_id,alias:c.alias,op:c.op,threshold:c.threshold};
    });
  }
  function renderRuleChecks(){
    $('f-rules').innerHTML=defs.rule.map(function(d){
      return '<label class="rc"><input type="checkbox" data-rid="'+d.id+'">'+
        '<span class="rname">'+esc(d.name)+'</span>'+
        '<input type="number" class="tin" data-w="'+d.id+'" value="1" step="0.1" min="0" title="权重">'+
        '<label class="veto"><input type="checkbox" data-v="'+d.id+'"> 否决</label></label>';
    }).join('')||'<span class="hint">暂无规则</span>';
  }
  function fillForm(scope,d){
    $('de-title').textContent=(d?'编辑':'新建')+LABEL[scope];
    editingScope=scope;editing[scope]=d?d.id:null;
    ['index','rule','frame'].forEach(function(s){$('de-'+s).hidden=(s!==scope);});
    $('de-msg').textContent='';
    if(scope==='index'){
      $('i-name').value=d?d.name:'';$('i-agg').value=d?d.aggregate:'sum';
      $('i-ds').value=d?d.datasource_id:'';
      $('i-filters').innerHTML='';
      if(d){
        (d.filter_json||[]).forEach(addFilterRow);
        selectTables(d.datasource_id,d.source_table).then(function(){
          return selectColumns(d.datasource_id,d.source_table,d.source_column);
        });
      }else{
        selectTables('','');selectColumns('','','');addFilterRow();
      }
    }else if(scope==='rule'){
      $('r-name').value=d?d.name:'';$('r-combine').value=d?d.combine:'all';
      $('r-conditions').innerHTML='';
      if(d)ruleConditions(d).forEach(addConditionRow);else addConditionRow();
    }else{
      $('f-name').value=d?d.name:'';$('f-combine').value=d?d.combine:'weighted';
      $('f-th').value=d&&d.threshold!=null?d.threshold:'0.8';
      renderRuleChecks();
      if(d)(d.rule_refs_json||[]).forEach(function(r){
        var cb=$('f-rules').querySelector('[data-rid="'+r.rule_id+'"]');
        if(cb){
          cb.checked=true;
          $('f-rules').querySelector('[data-w="'+r.rule_id+'"]').value=r.weight;
          $('f-rules').querySelector('[data-v="'+r.rule_id+'"]').checked=!!r.veto;
        }
      });
    }
    openEl('ded');
  }
  ['index','rule','frame'].forEach(function(scope){
    $(PFX[scope]+'-new').onclick=function(){fillForm(scope,null);};
  });
  $('de-save').onclick=function(){
    if(editingScope==='index')saveIndex();
    else if(editingScope==='rule')saveRule();else saveFrame();
  };
  function afterSave(){closeEl('ded');loadAll();ok('已保存');}
  function saveIndex(){
    var filters=[];
    Array.prototype.forEach.call($('i-filters').children,function(row){
      var c=row.querySelector('[data-k=c]').value.trim();if(!c)return;
      var v=row.querySelector('[data-k=v]').value.trim();
      filters.push({column:c,op:row.querySelector('[data-k=o]').value,
        value:isNaN(Number(v))?v:Number(v)});
    });
    var body={name:$('i-name').value.trim(),datasource_id:Number($('i-ds').value),
      source_table:$('i-table').value,source_column:$('i-column').value||null,
      aggregate:$('i-agg').value,filter_json:filters};
    if(editing.index)body.id=editing.index;
    post('/api/index',body).then(afterSave).catch(function(e){err(e.message);});
  }
  function saveRule(){
    var conditions=[],refs=[],aliases={},ids={},invalid=false;
    Array.prototype.forEach.call($('r-conditions').children,function(row){
      var iid=Number(row.querySelector('[data-k=i]').value),alias=row.querySelector('[data-k=a]').value.trim();
      var op=row.querySelector('[data-k=o]').value,text=row.querySelector('[data-k=t]').value.trim(),threshold;
      if(!iid||!alias||text===''){err('每行条件须选择指标、填写标识名与阈值');invalid=true;return;}
      if(aliases[alias]||ids[iid]){err('指标与标识名均不能重复');invalid=true;return;}
      aliases[alias]=true;ids[iid]=true;
      if(op==='between'){
        var parts=text.split(',').map(function(x){return Number(x.trim());});
        if(parts.length!==2||parts.some(isNaN)){err('区间须填两个数值');invalid=true;return;}
        threshold=parts;
      }else threshold=isNaN(Number(text))?text:Number(text);
      refs.push({index_id:iid,alias:alias});
      conditions.push({alias:alias,op:op,threshold:threshold});
    });
    if(invalid||!refs.length)return;
    var body={name:$('r-name').value.trim(),index_refs:refs,conditions:conditions,
      combine:$('r-combine').value};
    if(editing.rule)body.id=editing.rule;
    post('/api/rule',body).then(afterSave).catch(function(e){err(e.message);});
  }
  function saveFrame(){
    var refs=[];
    Array.prototype.forEach.call($('f-rules').querySelectorAll('input[data-rid]'),function(cb){
      if(!cb.checked)return;var id=cb.getAttribute('data-rid');
      refs.push({rule_id:Number(id),weight:Number($('f-rules').querySelector('[data-w="'+id+'"]').value),
        veto:$('f-rules').querySelector('[data-v="'+id+'"]').checked});
    });
    if(!refs.length){err('请勾选至少一个规则');return;}
    var body={name:$('f-name').value.trim(),rule_refs:refs,combine:$('f-combine').value,
      threshold:Number($('f-th').value)};
    if(editing.frame)body.id=editing.frame;
    post('/api/frame',body).then(afterSave).catch(function(e){err(e.message);});
  }

  // ---------- 资产栏与节点动作 ----------
  var MENU_ICON={
    view:'<path d="M2 8s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4Z"/><circle cx="8" cy="8" r="1.5"/>',
    edit:'<path d="m3 13 8-8 2 2-8 8-3 1 1-3Z"/>',
    run:'<path d="m5 3 7 5-7 5V3Z"/>',
    trace:'<path d="M2 3h5v5H2zM9 8h5v5H9zM7 5h2v6h2"/>',
    replay:'<path d="M13 6a5 5 0 1 0 1 5M13 2v4H9"/>',
    del:'<path d="M3 5h10M6 5V3h4v2M5 5l1 8h4l1-8M7 7v4M9 7v4"/>'
  };
  function actionMenuItem(act,label,d,v,disabled){
    return '<button type="button" role="menuitem" class="menu-item'+(act==='del'?' danger':'')+
      '" data-act="'+act+'" data-id="'+d.id+'"'+(v?' data-vid="'+v.id+'"':'')+
      (disabled?' disabled data-tip="暂无可追溯结果"':'')+'><svg class="menu-icon" viewBox="0 0 16 16" aria-hidden="true">'+MENU_ICON[act]+'</svg><span>'+label+'</span></button>';
  }
  function fillActionMenu(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    var v=d._latest,menu=$('compute-action-menu'),h='';
    if(scope==='source'){
      h=actionMenuItem('view','查看',d)+actionMenuItem('trace','追溯',d);
    }else if(scope==='document'){
      h=actionMenuItem('view','查看',d)+actionMenuItem('trace','追溯',d);
    }else{
      h=actionMenuItem('view','查看',d)+actionMenuItem('edit','编辑',d)+
        actionMenuItem('run','运行',d)+actionMenuItem('trace','追溯',d)+
        actionMenuItem('replay','复核',d,v,!v)+'<div class="menu-sep"></div>'+
        actionMenuItem('del','删除',d);
    }
    menu.innerHTML=h;
    menu.onclick=function(e){
      var item=e.target.closest?e.target.closest('[data-act]'):null;
      if(!item||item.disabled)return;
      nodeAction(scope,Number(item.dataset.id),item.dataset.act,
        item.dataset.vid?{id:Number(item.dataset.vid)}:null);
    };
  }
  function openNodeMenu(scope,id){fillActionMenu(scope,id);}
  function selectNode(scope,id){
    var d=graph.def(scope,id);if(d)openView(scope,d);
  }
  function renderAssets(scope){
    var host=$(PFX[scope]+'-assets');
    $(PFX[scope]+'-count').textContent=defs[scope].length;
    host.innerHTML=defs[scope].map(function(d){
      return '<article class="asset-item" data-key="'+scope+':'+d.id+'">'+
        '<button type="button" class="asset-main" data-id="'+d.id+'" data-tip="单击查看详情&#10;双击血缘追溯&#10;名称：'+esc(d.name)+'" aria-label="查看'+esc(d.name)+'">'+
        scopeIcon(scope)+'<b>'+esc(d.name)+'</b></button>'+
        '<button type="button" class="icon-btn mini asset-more" data-action-menu="compute-action-menu" '+
        'data-scope="'+scope+'" data-id="'+d.id+'" data-tip="更多操作" aria-haspopup="menu" aria-expanded="false" '+
        'aria-label="'+esc(d.name)+'更多操作">⋯</button></article>';
    }).join('')||'<div class="asset-empty">暂无'+LABEL[scope]+'</div>';
    host.onclick=function(e){
      var trigger=e.target.closest?e.target.closest('[data-action-menu]'):null;
      if(trigger){fillActionMenu(trigger.dataset.scope,Number(trigger.dataset.id));return;}
      var main=e.target.closest?e.target.closest('.asset-main'):null;
      if(main){
        var id=Number(main.dataset.id);graph.focus(scope,id);
        clearTimeout(assetClickTimer);
        assetClickTimer=setTimeout(function(){selectNode(scope,id);},260);
      }
    };
    host.ondblclick=function(e){
      if(e.target.closest&&e.target.closest('[data-action-menu]'))return;
      var main=e.target.closest?e.target.closest('.asset-main'):null;if(!main)return;
      clearTimeout(assetClickTimer);assetClickTimer=null;
      openLineage(scope,Number(main.dataset.id));
    };
  }
  function nodeAction(scope,id,act,v){
    var d=graph.def(scope,id);if(!d)return;
    if(act==='view')openView(scope,d);
    else if(act==='edit')fillForm(scope,d);
    else if(act==='run')doRun(scope,id);
    else if(act==='trace')openLineage(scope,id);
    else if(act==='replay'&&v)openReplay(scope,v.id);
    else if(act==='del')doDelete(scope,id);
  }
  function doDelete(scope,id){
    var d=graph.def(scope,id);if(!d||!confirm('确定删除「'+d.name+'」及其全部结果？'))return;
    api('/api/'+scope+'/'+id,{method:'DELETE'}).then(function(){
      delete layout[scope+':'+id];
      try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).map(function(k){return layout[k];})));}catch(e){}
      loadAll();ok('已删除');
    })
      .catch(function(e){err(e.message);});
  }
  function doRun(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    if(!confirm('确认按当前配置运行「'+d.name+'」？运行后会覆盖该节点原结果。'))return;
    post('/api/'+scope+'/'+id+'/run',{}).then(function(){loadAll();ok('已计算');})
      .catch(function(e){err(e.message);});
  }
  function runAllDefinitions(){
    if(runAllRunning)return;
    var tasks=[];
    ['index','rule','frame'].forEach(function(scope){
      defs[scope].slice().sort(function(a,b){return a.id-b.id;}).forEach(function(d){
        tasks.push({scope:scope,d:d});
      });
    });
    if(!tasks.length){err('暂无可计算的定义');return;}
    var btn=$('graph-run-all'),done=0,total=tasks.length,failed=false;
    runAllRunning=true;btn.disabled=true;btn.textContent='计算中 0/'+total;
    function next(){
      if(done>=total)return Promise.resolve();
      var task=tasks[done];
      return post('/api/'+task.scope+'/'+task.d.id+'/run',{}).then(function(){
        done++;btn.textContent='计算中 '+done+'/'+total;return next();
      }).catch(function(e){
        throw new Error('「'+task.d.name+'」计算失败：'+e.message);
      });
    }
    next().catch(function(e){failed=true;err(e.message);})
      .then(function(){return loadAll();})
      .then(function(){
        runAllRunning=false;btn.disabled=false;btn.textContent='重新计算';
        if(!failed)ok('全部计算完成');
      });
  }
  function connectNodes(fromScope,fromId,toScope,toId){
    var target=graph.def(toScope,toId);
    if(toScope==='rule'){
      var existing=(target.index_refs_json||[]).some(function(r){return r.index_id===fromId;});
      fillForm('rule',target);
      var row=existing?Array.prototype.filter.call($('r-conditions').children,function(r){
        return Number(r.querySelector('[data-k=i]').value)===fromId;})[0]:addConditionRow();
      if(row){row.querySelector('[data-k=i]').value=fromId;$('r-conditions').scrollTop=row.offsetTop;}
      if(existing)ok('该指标已在此规则中，可直接编辑条件');
    }else{
      fillForm('frame',target);
      var cb=$('f-rules').querySelector('[data-rid="'+fromId+'"]');
      if(cb){cb.checked=true;cb.closest('.rc').scrollIntoView({block:'nearest'});}
    }
    graph.focus(fromScope,fromId);
  }
  function disconnectEdge(edge){
    var target=graph.def(edge.to.scope,edge.to.id),refs=target[edge.to.scope==='rule'?'index_refs_json':'rule_refs_json']||[];
    if(refs.length<=1){err(LABEL[edge.to.scope]+'至少须保留一个上级引用，不能断开最后一条连线');return;}
    if(!confirm('确定断开「'+graph.def(edge.from.scope,edge.from.id).name+'」到「'+target.name+'」的引用？'))return;
    var key=edge.to.scope==='rule'?'index_id':'rule_id',fromId=edge.from.id;
    var body;
    if(edge.to.scope==='rule')body={name:target.name,index_refs:refs.filter(function(r){return r[key]!==fromId;}),
      conditions:target.conditions_json.filter(function(c){return refs.some(function(r){return r[key]!==fromId&&r.alias===c.alias;});}),
      combine:target.combine,id:target.id};
    else body={name:target.name,rule_refs:refs.filter(function(r){return r[key]!==fromId;}),
      combine:target.combine,threshold:target.threshold,id:target.id};
    post('/api/'+edge.to.scope,body).then(function(){graph.selectEdge(null);loadAll();ok('已断开引用');})
      .catch(function(e){err(e.message);});
  }

  // ---------- 只读查看 ----------
  function openView(scope,d){
    $('view-title').textContent='查看'+LABEL[scope]+' · '+d.name;
    var h='<div class="view-grid">';
    if(scope==='source'){
      h+='<div><span>业务库 ID</span><b>'+esc(d.datasource_id)+'</b></div><div><span>业务表</span><b>'+esc(d.name||d.source_table)+'</b></div>'+
        '<div><span>关联指标</span><b>'+esc((d.index_ids||[]).length)+'</b></div>';
    }else if(scope==='document'){
      h+='<div><span>资料 ID</span><b>'+esc(d.id)+'</b></div><div><span>关联数据</span><b>'+esc(d.row_count)+' 行</b></div>'+
        '<div><span>来源数据</span><b>'+esc((d.source_table_labels||d.source_tables||[]).join('、')||'—')+'</b></div>';
    }else if(scope==='index'){
      h+='<div><span>业务库 ID</span><b>'+esc(d.datasource_id)+'</b></div><div><span>业务表</span><b>'+esc(tableLabel(d.datasource_id,d.source_table))+'</b></div>'+
        '<div><span>聚合列</span><b>'+esc(d.source_column||'整行')+'</b></div><div><span>运算</span><b>'+esc(aggLabel(d.aggregate))+'</b></div>';
    }else if(scope==='rule'){
      h+='<div><span>条件组合</span><b>'+esc(combineLabel(d.combine))+'</b></div><div><span>条件数</span><b>'+esc((d.conditions_json||[]).length)+'</b></div>';
    }else h+='<div><span>组合方式</span><b>'+esc(combineLabel(d.combine))+'</b></div>'+
      '<div><span>通过阈值</span><b>'+esc(d.threshold==null?'—':d.threshold)+'</b></div>';
    h+='</div>';
    if(scope==='rule')h+='<h3 class="view-sub">条件</h3>'+ruleConditions(d).map(function(c){
      return '<div class="view-row">'+esc(defs.index.filter(function(x){return x.id===c.index_id;})[0]?.name||('#'+c.index_id))+
        ' · '+esc(c.alias)+' '+esc(opLabel(c.op))+' '+esc(c.threshold)+'</div>';}).join('');
    if(scope==='frame')h+='<h3 class="view-sub">关联规则</h3>'+(d.rule_refs_json||[]).map(function(r){
      return '<div class="view-row">'+esc(defs.rule.filter(function(x){return x.id===r.rule_id;})[0]?.name||('#'+r.rule_id))+
        ' · 权重 '+esc(r.weight)+(r.veto?' · 否决':'')+'</div>';}).join('');
    if(d._latest)h+='<h3 class="view-sub">最近结果</h3><div class="view-row">'+esc(resultDisplay(scope,d))+'</div>';
    if(scope==='source')h+='<h3 class="view-sub">关联指标</h3>'+(d.index_ids||[]).map(function(id){
      var index=graph.def('index',id);return '<div class="view-row">'+esc(index?index.name:('#'+id))+'</div>';
    }).join('');
    h+='<div class="dfoot"><span class="spacer"></span>'+
      (scope==='document'?'<a class="btn" href="/srcfiles/'+encodeURIComponent(d.id)+'" target="_blank" rel="noopener">打开原件</a>':'')+
      (scope==='source'||scope==='document'?'<button type="button" class="btn" id="view-trace">追溯</button>':'<button type="button" class="btn" id="view-edit">编辑</button>')+'</div>';
    $('view-body').innerHTML=h;
    var edit=$('view-edit');if(edit)edit.onclick=function(){closeEl('compute-view');fillForm(scope,d);};
    var trace=$('view-trace');if(trace)trace.onclick=function(){closeEl('compute-view');openLineage(scope,d.id);};
    openEl('compute-view');
  }

  // ---------- 全宽血缘追溯工作台 ----------
  function closeLineage(){
    lineageSeq++;lineageState=null;graph.selectNode(null);lineageGraph.selectNode(null);
    clearLineageTraceFrames();setLineageLinkStatus('');
  }
  function setLineageTab(tab){
    Array.prototype.forEach.call(document.querySelectorAll('[data-lineage-tab]'),function(btn){
      var on=btn.dataset.lineageTab===tab;btn.classList.toggle('is-active',on);btn.setAttribute('aria-selected',String(on));
    });
    $('lineage-current-panel').classList.toggle('lineage-mobile-active',tab==='current');
    $('lineage-upstream-panel').classList.toggle('lineage-mobile-active',tab==='upstream');
  }
  function relatedDefs(scope,d){
    var full=graphDefs(),seen={},queue=[{scope:scope,d:d}],out={document:[],source:[],index:[],rule:[],frame:[]};
    function enqueue(nextScope,id){
      var next=full[nextScope].filter(function(x){return x.id===id;})[0];
      if(next)queue.push({scope:nextScope,d:next});
    }
    while(queue.length){
      var item=queue.shift(),x=item.d,key=item.scope+':'+x.id;
      if(!x||seen[key])continue;seen[key]=true;
      if(out[item.scope].indexOf(x)<0)out[item.scope].push(x);
      if(item.scope==='document')(x.source_ids||[]).forEach(function(id){enqueue('source',id);});
      else if(item.scope==='source'){
        if(scope!=='document')full.document.filter(function(doc){return (doc.source_ids||[]).indexOf(x.id)>=0;})
          .forEach(function(doc){queue.push({scope:'document',d:doc});});
      }else if(item.scope==='index'){
        full.source.filter(function(s){return (s.index_ids||[]).indexOf(x.id)>=0;})
          .forEach(function(s){queue.push({scope:'source',d:s});});
      }else if(item.scope==='rule'){
        (x.index_refs_json||[]).forEach(function(ref){enqueue('index',ref.index_id);});
      }else if(item.scope==='frame'){
        (x.rule_refs_json||[]).forEach(function(ref){enqueue('rule',ref.rule_id);});
      }
    }
    return out;
  }
  function directRelatedNodes(scope,d){
    var full=lineageGraph.defs;
    function refs(targetScope,refs,key){
      var out=[],seen={};
      (refs||[]).forEach(function(ref){
        var id=ref[key],k=targetScope+':'+id;if(seen[k])return;seen[k]=true;
        var item=full[targetScope].filter(function(x){return x.id===id;})[0];if(item)out.push(item);
      });
      return out;
    }
    if(scope==='document')return (d.source_ids||[]).map(function(id){
      return full.source.filter(function(x){return x.id===id;})[0];
    }).filter(Boolean);
    if(scope==='source')return full.document.filter(function(doc){
      return (doc.source_ids||[]).indexOf(d.id)>=0;
    }).sort(function(a,b){return String(a.name).localeCompare(String(b.name),'zh-CN')||Number(a.id)-Number(b.id);});
    if(scope==='index')return full.source.filter(function(s){return (s.index_ids||[]).indexOf(d.id)>=0;});
    if(scope==='rule')return refs('index',d.index_refs_json,'index_id');
    return refs('rule',d.rule_refs_json,'rule_id');
  }
  function valueText(value){
    if(value==null)return '暂无结果';
    if(typeof value==='object'){try{return JSON.stringify(value);}catch(e){return String(value);}}
    return String(value);
  }
  function fieldHtml(label,value){
    return '<div><span>'+esc(label)+'</span><b>'+esc(value==null||value===''?'—':value)+'</b></div>';
  }
  function nodeHeading(scope,d){
    return '<div class="lineage-current-title">'+scopeIcon(scope)+'<b>'+esc(d.name)+'</b><small>'+esc(LABEL[scope])+' #'+esc(d.id)+'</small></div>';
  }
  function nodeSubtitle(scope,d){
    if(scope==='document')return '资料 #'+d.id+' · 关联数据 '+d.row_count+' 行';
    if(scope==='source')return tableLabel(d.datasource_id,d.source_table)+' · '+(d.index_ids||[]).length+' 个指标';
    if(scope==='index')return tableLabel(d.datasource_id,d.source_table)+' · '+aggLabel(d.aggregate);
    if(scope==='rule')return (d.conditions_json||[]).length+' 个条件 · '+combineLabel(d.combine);
    return combineLabel(d.combine)+' · '+(d.rule_refs_json||[]).length+' 条规则';
  }
  function nodeSummaryHtml(scope,d){
    var h='';
    if(scope==='document'){
      h+='<div class="lineage-summary-grid">'+fieldHtml('资料 ID',d.id)+
        fieldHtml('文件类型',KIND_LABEL[kindOf(d.name)]||'文件')+
        fieldHtml('关联数据',d.row_count+' 行')+
        fieldHtml('来源数据',(d.source_table_labels||d.source_tables||[]).join('、'))+'</div>';
    }else if(scope==='source'){
      h+='<div class="lineage-summary-grid">'+fieldHtml('表注释',tableLabel(d.datasource_id,d.source_table))+
        fieldHtml('业务库 ID',d.datasource_id)+fieldHtml('关联指标数',(d.index_ids||[]).length)+'</div>';
    }else if(scope==='index'){
      h+='<div class="lineage-summary-grid">'+fieldHtml('业务库 ID',d.datasource_id)+
        fieldHtml('业务表',tableLabel(d.datasource_id,d.source_table))+
        fieldHtml('聚合列',d.source_column||'整行')+fieldHtml('运算',aggLabel(d.aggregate))+
        fieldHtml('筛选条件',(d.filter_json||[]).length+' 条')+'</div>';
      if((d.filter_json||[]).length)h+='<div class="lineage-summary-list">'+(d.filter_json||[]).map(function(f){
        return '<div>'+esc(f.column)+' '+esc(opLabel(f.op))+' '+esc(valueText(f.value))+'</div>';
      }).join('')+'</div>';
    }else if(scope==='rule'){
      h+='<div class="lineage-summary-grid">'+fieldHtml('条件组合',combineLabel(d.combine))+
        fieldHtml('条件数',(d.conditions_json||[]).length)+'</div>';
      h+='<div class="lineage-summary-list">'+ruleConditions(d).map(function(c){
        var index=defs.index.filter(function(x){return x.id===c.index_id;})[0];
        return '<div>'+esc(index?index.name:('#'+c.index_id))+' · '+esc(c.alias)+' '+esc(opLabel(c.op))+' '+esc(valueText(c.threshold))+'</div>';
      }).join('')+'</div>';
    }else{
      h+='<div class="lineage-summary-grid">'+fieldHtml('组合方式',combineLabel(d.combine))+
        fieldHtml('关联规则数',(d.rule_refs_json||[]).length)+fieldHtml('通过阈值',d.threshold==null?'—':d.threshold)+'</div>';
      h+='<div class="lineage-summary-list">'+(d.rule_refs_json||[]).map(function(ref){
        var rule=defs.rule.filter(function(x){return x.id===ref.rule_id;})[0];
        return '<div>'+esc(rule?rule.name:('#'+ref.rule_id))+' · 权重 '+esc(ref.weight)+(ref.veto?' · 否决':'')+'</div>';
      }).join('')+'</div>';
    }
    return h;
  }
  function nodeResultHtml(scope,d){
    return VFIELD[scope]?'<div class="lineage-result"><span>最新结果</span><strong>'+esc(resultDisplay(scope,d)||'暂无结果')+'</strong></div>':'';
  }
  function tableCacheKey(source,fileId,page){
    return [source.datasource_id,source.source_table,fileId==null?'':fileId,page].join(':');
  }
  function tableRowsUrl(source,fileId,page){
    var url='/api/load/datasources/'+encodeURIComponent(source.datasource_id)+'/rows?table='+
      encodeURIComponent(source.source_table)+'&page='+page+'&per_page=20';
    if(fileId!=null)url+='&file_id='+encodeURIComponent(fileId);
    return url;
  }
  function tableCellText(value){
    if(value==null)return '—';
    if(typeof value==='object')return valueText(value);
    return String(value);
  }
  function traceColumns(data){
    return (data.columns||[]).filter(function(c){return !TRACE_SKIP_COLS[c];});
  }
  function traceResultMap(result){
    var map={};(result||[]).forEach(function(item){map[String(item.record_id)]=item;});return map;
  }
  function traceSummary(data,result){
    var items=data.items||[],cols=traceColumns(data);
    if(!items.length)return '当前页暂无数据';
    if(!result)return '';
    var map=traceResultMap(result),rows=0,fields=0;
    items.forEach(function(row){
      var item=map[String(row.record_id)],rowOk=false;
      cols.forEach(function(c){
        var st=item&&item.fields&&item.fields[c];
        if(st&&st.traceable){fields++;rowOk=true;}
      });
      if(rowOk)rows++;
    });
    return '可追溯 '+rows+'/'+items.length+' 行 · '+fields+'/'+(items.length*cols.length)+' 个字段';
  }
  function traceToolbar(host){
    if(!host)return null;
    var external=host.dataset.traceToolbar&&document.getElementById(host.dataset.traceToolbar);
    return external||host.querySelector('.lineage-table-toolbar');
  }
  function setTraceSummary(host,text){
    var toolbar=traceToolbar(host),summary=toolbar&&toolbar.querySelector('.lineage-trace-summary');
    if(summary)summary.textContent=text||'';
  }
  function clearTableTrace(host){
    if(!host)return;
    Array.prototype.forEach.call(host.querySelectorAll('.trace-ok,.trace-no'),function(td){
      td.classList.remove('trace-ok','trace-no');td.removeAttribute('data-trace-reason');td.removeAttribute('title');
    });
  }
  function applyTableTrace(host,data,result){
    clearTableTrace(host);
    var map=traceResultMap(result),cols=traceColumns(data);
    (data.items||[]).forEach(function(row){
      var rid=row.record_id==null?'':String(row.record_id),item=map[rid];
      var tr=Array.prototype.filter.call(host.querySelectorAll('tr[data-rid]'),function(x){
        return x.getAttribute('data-rid')===rid;
      })[0];
      if(!tr)return;
      cols.forEach(function(c){
        var td=Array.prototype.filter.call(tr.querySelectorAll('td.cell[data-col]'),function(x){
          return x.getAttribute('data-col')===c;
        })[0];
        if(!td)return;
        var st=item&&item.fields&&item.fields[c];
        if(st&&st.traceable)td.classList.add('trace-ok');
        else{
          td.classList.add('trace-no');
          var reason=st?st.message:'该记录缺少溯源标识';
          td.dataset.traceReason=reason;td.title=reason;
        }
      });
    });
    var toolbar=traceToolbar(host),summary=toolbar&&toolbar.querySelector('.lineage-trace-summary');
    if(summary)summary.textContent=traceSummary(data,result);
  }
  function updateTraceToggle(host,on,loading){
    var toolbar=traceToolbar(host),btn=toolbar&&toolbar.querySelector('[data-trace-toggle]');
    if(btn){btn.classList.toggle('is-on',!!on);btn.setAttribute('aria-pressed',String(!!on));btn.disabled=!!loading;}
  }
  function traceGroups(result,cols){
    var groups={};
    (result||[]).forEach(function(item){
      if(item.file_id==null)return;
      var keys=[];
      cols.forEach(function(c){
        var st=item.fields&&item.fields[c];
        if(st&&st.traceable)keys.push(st.field||c);
      });
      if(!keys.length)return;
      var fid=String(item.file_id);
      if(!groups[fid])groups[fid]=[];
      groups[fid].push({record_index:item.record_index,keys:keys});
    });
    return groups;
  }
  function dispatchTraceGroups(groups){
    var active=activeLineageNode();if(!active)return;
    var firstCard=null;
    Object.keys(groups).forEach(function(fid){
      var batch={items:groups[fid]},card=null,frame=null;
      if(active.scope==='source'){
        card=findRelatedLineageCard('document',fid);
        if(card){
          if(!firstCard){firstCard=card;card.open=true;loadLineageCard(card);}
          else card.dataset.pendingBatch=JSON.stringify(batch);
          frame=card.querySelector('iframe');
        }
      }else if(active.scope==='document'&&String(active.def.id)===String(fid)){
        frame=$('lineage-document-frame');
      }
      if(frame)sendLineageTraceBatch(frame,batch);
    });
    if(firstCard)setActiveLineageCard(firstCard);
  }
  function clearLineageTraceFrames(){
    Array.prototype.forEach.call(document.querySelectorAll('.lineage-upstream-frame,#lineage-document-frame'),function(frame){
      clearLineageTraceBatch(frame);
    });
  }
  function runTableTrace(host,source,fileId,page,data){
    var key=tableCacheKey(source,fileId,page);
    if(lineageTracePending[key])return;
    var cols=traceColumns(data),ids=(data.items||[]).map(function(row){return row.record_id;})
      .filter(function(rid){return rid!=null&&rid!=='';});
    var activeKey=lineageState&&lineageState.activeKey;
    host.dataset.traceOn='1';updateTraceToggle(host,true,true);
    setTraceSummary(host,'正在批量追溯…');
    function done(result){
      lineageTraceCache[key]=result;
      if(host.isConnected&&host.dataset.traceOn==='1'&&lineageState&&lineageState.activeKey===activeKey){
        applyTableTrace(host,data,result);updateTraceToggle(host,true,false);
        dispatchTraceGroups(traceGroups(result,cols));
      }
    }
    if(!ids.length){
      done((data.items||[]).map(function(row){return {record_id:row.record_id,file_id:null,fields:{}};}));
      return;
    }
    lineageTracePending[key]=true;
    post('/api/staging/trace-batch',{record_ids:ids,columns:cols}).then(function(j){
      done(j.items||[]);
    }).catch(function(e){
      if(host.isConnected&&host.dataset.traceOn==='1'){
        host.dataset.traceOn='0';clearTableTrace(host);updateTraceToggle(host,false,false);
        setTraceSummary(host,'追溯失败：'+e.message);
        setLineageLinkStatus('批量追溯失败：'+e.message,'warn');
      }
    }).then(function(){delete lineageTracePending[key];});
  }
  function renderTablePreview(host,source,fileId,page,data,meta,toolbarHost){
    var total=Number(data.total)||0,pages=Math.max(1,Math.ceil(total/Number(data.per_page||20))),current=Number(data.page)||page;
    if(meta)meta.textContent='共 '+total+' 行 · 第 '+current+' / '+pages+' 页';
    var cols=data.columns||[],items=data.items||[],locatable=lineageLocateEnabled(),on=host.dataset.traceOn==='1',
      cached=on?lineageTraceCache[tableCacheKey(source,fileId,page)]:null;
    host.dataset.tracePage=String(current);
    host.dataset.traceKey=tableCacheKey(source,fileId,page);
    var toolbar='<div class="lineage-table-toolbar"><button type="button" class="btn mini ghost trace-toggle'+(on?' is-on':'')+'" data-trace-toggle aria-pressed="'+on+'">一键追溯</button>'+
      '<span class="hint" tabindex="0" aria-label="一键追溯说明" data-tip="批量追溯当前页数据；橙色表示可追溯，灰色表示不可追溯。">?</span>'+
      '<span class="lineage-trace-summary">'+esc(traceSummary(data,cached))+'</span></div>';
    if(toolbarHost){
      host.dataset.traceToolbar=toolbarHost.id;
      toolbarHost.innerHTML=toolbar;
    }else{
      delete host.dataset.traceToolbar;
    }
    var h=(toolbarHost?'':toolbar)+'<div class="lineage-table-wrap"><table class="lineage-table"><thead><tr>'+
      cols.map(function(c){return '<th>'+esc(c)+'</th>';}).join('')+'</tr></thead><tbody>'+
      items.map(function(row){
        var rid=row.record_id==null?'':String(row.record_id);
        return '<tr'+(rid?' data-rid="'+esc(rid)+'"':'')+'>'+cols.map(function(c){
          return '<td class="cell'+(locatable?' locatable':'')+'" data-col="'+esc(c)+'">'+esc(tableCellText(row[c]))+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table></div>';
    if(!items.length)h+='<div class="lineage-empty">暂无数据</div>';
    h+='<div class="lineage-pager"><button type="button" class="btn mini ghost" data-page="'+Math.max(1,current-1)+'"'+(current<=1?' disabled':'')+'>上一页</button>'+
      '<span>'+current+' / '+pages+'</span>'+
      '<button type="button" class="btn mini ghost" data-page="'+Math.min(pages,current+1)+'"'+(current>=pages?' disabled':'')+'>下一页</button></div>';
    host.innerHTML=h;
    if(on&&cached)applyTableTrace(host,data,cached);
    function toggleTrace(){
      if(host.dataset.traceOn==='1'){
        host.dataset.traceOn='0';clearTableTrace(host);clearLineageTraceFrames();updateTraceToggle(host,false,false);
        setTraceSummary(host,'');
      }else runTableTrace(host,source,fileId,current,data);
    }
    if(toolbarHost)toolbarHost.onclick=function(e){
      if(e.target.closest&&e.target.closest('[data-trace-toggle]'))toggleTrace();
    };
    host.onclick=function(e){
      var cell=e.target.closest?e.target.closest('td.cell[data-col]'):null;
      if(cell){if(locatable)handleTableCellClick(cell,host,source,fileId,cell.closest('.lineage-upstream-card'));return;}
      var btn=e.target.closest?e.target.closest('[data-page]'):null;if(!btn||btn.disabled)return;
      loadTablePreview(host,source,fileId,Number(btn.dataset.page),meta,toolbarHost);
    };
  }
  function loadTablePreview(host,source,fileId,page,meta,toolbarHost){
    page=Math.max(1,Number(page)||1);
    delete host.dataset.traceOn;clearTableTrace(host);
    var key=tableCacheKey(source,fileId,page);
    if(lineageTableCache[key]){renderTablePreview(host,source,fileId,page,lineageTableCache[key],meta,toolbarHost);return;}
    host.innerHTML='<div class="lineage-empty">数据加载中…</div>';
    if(meta)meta.textContent='加载中…';
    api(tableRowsUrl(source,fileId,page)).then(function(data){
      lineageTableCache[key]=data;
      if(host.isConnected)renderTablePreview(host,source,fileId,page,data,meta,toolbarHost);
    }).catch(function(e){
      if(host.isConnected){host.innerHTML='<div class="lineage-empty">数据加载失败：'+esc(e.message)+'</div>';if(meta)meta.textContent='加载失败';}
    });
  }
  function setLineageLinkStatus(text,kind){
    var el=$('lineage-link-status');if(!el)return;
    if(!text){el.hidden=true;el.textContent='';el.className='lineage-link-status';return;}
    el.hidden=false;el.textContent=text;el.className='lineage-link-status'+(kind?' '+kind:'');
  }
  function clearLineageCellSelection(host){
    if(!host)return;
    Array.prototype.forEach.call(host.querySelectorAll('.sel-cell'),function(el){el.classList.remove('sel-cell');});
    Array.prototype.forEach.call(host.querySelectorAll('.sel-row'),function(el){el.classList.remove('sel-row');});
  }
  function highlightLineageCell(host,rid,col){
    if(!host)return;
    clearLineageCellSelection(host);
    var row=Array.prototype.filter.call(host.querySelectorAll('tr[data-rid]'),function(tr){
      return tr.getAttribute('data-rid')===String(rid);
    })[0];
    if(!row)return;
    row.classList.add('sel-row');
    var cell=Array.prototype.filter.call(row.querySelectorAll('td.cell[data-col]'),function(td){
      return td.getAttribute('data-col')===col;
    })[0];
    if(cell){cell.classList.add('sel-cell');cell.scrollIntoView({block:'nearest',inline:'nearest'});}
  }
  function setActiveLineageCard(card){
    Array.prototype.forEach.call(document.querySelectorAll('#lineage-upstream .lineage-upstream-card.is-active'),function(el){
      el.classList.remove('is-active');
    });
    if(card)card.classList.add('is-active');
    if(lineageState)lineageState.activeCard=card||null;
  }
  function findRelatedLineageCard(scope,id){
    return document.querySelector('#lineage-upstream [data-lineage-upstream="'+scope+':'+id+'"]');
  }
  function activeLineageNode(){
    if(!lineageState)return null;
    var parts=lineageState.activeKey.split(':'),scope=parts[0],id=Number(parts[1]);
    return {scope:scope,def:lineageGraph.def(scope,id)};
  }
  function lineageLocateEnabled(){
    var active=activeLineageNode();
    return !!active&&(active.scope==='source'||active.scope==='document');
  }
  function loadLineageCard(card){
    if(!lineageState||!card||card.dataset.loaded==='1')return;
    card.dataset.loaded='1';
    var parts=card.dataset.lineageUpstream.split(':'),nodeScope=parts[0],id=Number(parts[1]),
      node=lineageGraph.def(nodeScope,id),area=card.querySelector('.lineage-upstream-data');
    if(!node||!area)return;
    if(nodeScope==='source'){
      var active=activeLineageNode();
      loadTablePreview(area,node,active&&active.scope==='document'?active.def.id:null,1,null);
    }else if(nodeScope==='document'){
      area.innerHTML=documentPreviewHtml(node);var frame=area.querySelector('iframe');bindLineageFrame(frame);
      var pendingBatch=card.dataset.pendingBatch;
      if(pendingBatch){delete card.dataset.pendingBatch;sendLineageTraceBatch(frame,JSON.parse(pendingBatch));}
    }
  }
  function traceDocumentFrame(frame,fileId,index,key){
    if(!frame)return;
    var trace={key:key,index:index};
    if(frame.getAttribute('data-file')!==String(fileId)){
      frame.setAttribute('data-file',String(fileId));frame.dataset.ready='0';
      frame.src='/preview?embed=1&file='+encodeURIComponent(fileId)+'&index='+encodeURIComponent(index)+
        (key?('&key='+encodeURIComponent(key)):'');
    }else if(frame.dataset.ready==='1'&&frame.contentWindow){
      sendLineageTrace(frame,trace);
    }else frame.dataset.pendingTrace=JSON.stringify(trace);
  }
  function loadLineageRecordMap(fileId){
    if(lineageRecordMaps[fileId])return lineageRecordMaps[fileId];
    lineageRecordMaps[fileId]=api('/api/sources/'+encodeURIComponent(fileId)+'/record-ids').then(function(j){
      var map={};(j.items||[]).forEach(function(x){map[x.index]=x.record_id;});return map;
    });
    return lineageRecordMaps[fileId];
  }
  function handleTableCellClick(cell,host,source,fileId,card){
    if(!lineageState)return;
    var active=activeLineageNode();if(!active||(active.scope!=='source'&&active.scope!=='document'))return;
    var tr=cell.closest?cell.closest('tr[data-rid]'):null,rid=tr&&tr.getAttribute('data-rid'),
      col=cell.getAttribute('data-col'),seq=++lineageState.linkSeq;
    if(cell.classList.contains('trace-no')){
      setLineageLinkStatus(cell.getAttribute('data-trace-reason')||'该字段无法追溯','warn');return;
    }
    if(!rid){setLineageLinkStatus('该记录缺少溯源标识，无法定位源文件','warn');return;}
    lineageState.activeTable={host:host,source:source,fileId:fileId,card:card||null,
      meta:host.id==='lineage-current-table'?$('lineage-current-table-meta'):null};
    setActiveLineageCard(card);highlightLineageCell(host,rid,col);setLineageLinkStatus('正在定位源文件…');
    var cached=host.dataset.traceOn==='1'?traceResultMap(lineageTraceCache[host.dataset.traceKey])[rid]:null;
    var field=cached&&cached.fields&&cached.fields[col]?cached.fields[col].field:null;
    var hitPromise=cached?Promise.resolve({file_id:cached.file_id,record_index:cached.record_index,
      field:field||col,field_map:cached.field_map||{}}):
      api('/api/staging/locate/'+encodeURIComponent(rid)+(col?('?key='+encodeURIComponent(col)):''));
    hitPromise.then(function(hit){
      if(!lineageState||seq!==lineageState.linkSeq)return;
      if(active.scope==='source'){
        var docCard=findRelatedLineageCard('document',hit.file_id);
        if(!docCard){setLineageLinkStatus('未找到对应文档节点','warn');return;}
        docCard.open=true;loadLineageCard(docCard);setActiveLineageCard(docCard);setLineageTab('upstream');
        var frame=docCard.querySelector('iframe');
        if(!frame){setLineageLinkStatus('文档预览加载失败','warn');return;}
        traceDocumentFrame(frame,hit.file_id,hit.record_index,hit.field||col);
        setLineageLinkStatus('已定位到资料 #'+hit.file_id+' · '+(hit.field||col),'ok');
      }else{
        if(String(active.def.id)!==String(hit.file_id)){
          setLineageLinkStatus('该记录来源与当前资料不一致','warn');return;
        }
        var currentFrame=$('lineage-document-frame');currentFrame.hidden=false;setLineageTab('current');
        traceDocumentFrame(currentFrame,hit.file_id,hit.record_index,hit.field||col);
        setLineageLinkStatus('已定位到当前资料 · '+(hit.field||col),'ok');
      }
    }).catch(function(e){if(lineageState&&seq===lineageState.linkSeq)setLineageLinkStatus('溯源查询失败：'+e.message,'warn');});
  }
  function sourceCardContext(card,fileId){
    var parts=card.dataset.lineageUpstream.split(':'),source=lineageGraph.def('source',Number(parts[1])),
      area=card.querySelector('.lineage-upstream-data');if(!source||!area)return null;
    return {host:area,source:source,fileId:fileId,card:card,meta:null};
  }
  function targetTableContexts(fileId){
    if(!lineageState)return [];
    var active=activeLineageNode();if(!active)return [];
    if(active.scope==='source'){
      var host=$('lineage-current-table');if(!host)return [];
      return [{host:host,source:active.def,fileId:null,card:null,meta:$('lineage-current-table-meta')}];
    }
    if(active.scope!=='document')return [];
    var out=[],activeTable=lineageState.activeTable;
    if(activeTable&&activeTable.host.isConnected&&String(activeTable.fileId)===String(fileId))out.push(activeTable);
    Array.prototype.forEach.call(document.querySelectorAll('#lineage-upstream [data-lineage-upstream^="source:"]'),function(card){
      if(activeTable&&card===activeTable.card)return;
      var ctx=sourceCardContext(card,fileId);if(ctx)out.push(ctx);
    });
    return out;
  }
  function findRowInTable(ctx,rid){
    return new Promise(function(resolve){
      if(!ctx||!ctx.host.isConnected){resolve(false);return;}
      var page=1,pages=1,seq=lineageState?lineageState.linkSeq:0;
      function next(){
        var key=tableCacheKey(ctx.source,ctx.fileId,page),data=lineageTableCache[key];
        if(data){check(data);return;}
        api(tableRowsUrl(ctx.source,ctx.fileId,page)).then(function(d){
          lineageTableCache[key]=d;check(d);
        }).catch(function(){resolve(false);});
      }
      function check(data){
        if(!lineageState||seq!==lineageState.linkSeq){resolve(false);return;}
        pages=Math.max(1,Math.ceil(Number(data.total||0)/Number(data.per_page||20)));
        var found=(data.items||[]).some(function(row){return String(row.record_id)===String(rid);});
        if(found){
          renderTablePreview(ctx.host,ctx.source,ctx.fileId,page,data,ctx.meta);resolve(true);
        }else if(page<pages){page++;next();}else resolve(false);
      }
      next();
    });
  }
  function handleSourcePin(frame,fileId,pin){
    if(!lineageState||!fileId)return;
    var seq=++lineageState.linkSeq;setLineageLinkStatus('正在定位数据表…');
    loadLineageRecordMap(fileId).then(function(map){
      var rid=map[pin.record_index];
      if(rid==null){setLineageLinkStatus('未找到对应暂存记录','warn');return null;}
      return api('/api/staging/locate/'+encodeURIComponent(rid)).then(function(hit){
        if(!lineageState||seq!==lineageState.linkSeq)return null;
        var fieldMap=hit.field_map||{},col=Object.keys(fieldMap).filter(function(c){
          return fieldMap[c]===pin.key;
        })[0]||pin.key,contexts=targetTableContexts(fileId);
        if(!contexts.length){setLineageLinkStatus('未找到可联动的数据表','warn');return null;}
        setLineageTab('upstream');
        function next(i){
          if(i>=contexts.length){
            setLineageLinkStatus('下游数据表中未找到对应记录','warn');return null;
          }
          var ctx=contexts[i];
          return findRowInTable(ctx,rid).then(function(found){
            if(!lineageState||seq!==lineageState.linkSeq)return null;
            if(!found)return next(i+1);
            if(ctx.card){ctx.card.dataset.loaded='1';ctx.card.open=true;}
            setActiveLineageCard(ctx.card);highlightLineageCell(ctx.host,rid,col);
            setLineageLinkStatus('已定位到数据表 · '+col,'ok');return ctx;
          });
        }
        return next(0);
      });
    }).catch(function(e){if(lineageState&&seq===lineageState.linkSeq)setLineageLinkStatus('反向定位失败：'+e.message,'warn');});
  }
  function documentPreviewHtml(d){
    return '<iframe class="lineage-upstream-frame" title="'+esc(d.name)+' · 资料文件预览" loading="lazy" data-file="'+esc(d.id)+'" data-ready="0" src="/preview?embed=1&file='+encodeURIComponent(d.id)+'"></iframe>';
  }
  function renderCurrentNode(scope,d){
    var host=$('lineage-current'),panel=$('lineage-current-panel'),isDocument=scope==='document';
    var frame=$('lineage-document-frame'),open=$('lineage-open-source');
    panel.classList.toggle('is-document',isDocument);open.hidden=!isDocument;
    if(isDocument){
      open.href='/srcfiles/'+encodeURIComponent(d.id);frame.title=d.name+' · 资料文件预览';frame.hidden=false;
      if(frame.getAttribute('data-file')!==String(d.id)){
        frame.setAttribute('data-file',String(d.id));frame.dataset.ready='0';frame.src='/preview?embed=1&file='+encodeURIComponent(d.id);
      }
    }else{
      frame.hidden=true;frame.removeAttribute('src');frame.removeAttribute('data-file');delete frame.dataset.ready;
    }
    var h=nodeHeading(scope,d)+nodeSummaryHtml(scope,d)+nodeResultHtml(scope,d);
    if(scope==='source')h+='<div class="lineage-current-data"><div class="lineage-data-head"><b>数据列表</b><span id="lineage-current-table-meta" class="lineage-table-meta"></span><div id="lineage-current-table-toolbar" class="lineage-data-actions"></div></div>'+
      '<div id="lineage-current-table" class="lineage-table-host"></div></div>';
    host.innerHTML=h;
    if(scope==='source')loadTablePreview($('lineage-current-table'),d,null,1,$('lineage-current-table-meta'),$('lineage-current-table-toolbar'));
  }
  function renderRelatedNodes(scope,d){
    var host=$('lineage-upstream'),nodes=directRelatedNodes(scope,d);
    if(!nodes.length){
      host.innerHTML='<div class="lineage-empty">'+(scope==='document'?'暂无直接下游节点':'暂无直接上游节点')+'</div>';return;
    }
    host.innerHTML=nodes.map(function(node){
      return '<details class="lineage-upstream-card scope-'+node._scope+'" data-lineage-upstream="'+node._scope+':'+node.id+'">'+
        '<summary><span class="lineage-node-card-icon">'+scopeIcon(node._scope)+'</span>'+
        '<span class="lineage-node-card-body"><b>'+esc(node.name)+'</b><small>'+esc(nodeSubtitle(node._scope,node))+'</small></span>'+
        '<span class="lineage-node-card-arrow">⌄</span></summary>'+
        '<div class="lineage-upstream-detail">'+nodeSummaryHtml(node._scope,node)+nodeResultHtml(node._scope,node)+
        '<div class="lineage-upstream-data"></div></div></details>';
    }).join('');
    Array.prototype.forEach.call(host.querySelectorAll('[data-lineage-upstream]'),function(card){
      card.addEventListener('toggle',function(){if(card.open)loadLineageCard(card);});
    });
  }
  function renderLineageDetails(scope,id){
    if(!lineageState)return;
    var d=lineageGraph.def(scope,id);if(!d)return;
    clearLineageTraceFrames();
    lineageState.activeKey=scope+':'+id;lineageState.activeCard=null;lineageState.activeTable=null;lineageState.linkSeq++;
    setLineageLinkStatus('');
    lineageGraph.selectNode(scope,id);
    var relatedLabel=scope==='document'?'下游节点':'上游节点';
    $('lineage-related-title').textContent=relatedLabel;
    $('lineage-related-tab').textContent=relatedLabel;
    renderCurrentNode(scope,d);renderRelatedNodes(scope,d);
  }
  function refreshLineage(){
    if(!lineageState)return;
    var parts=lineageState.activeKey.split(':'),scope=parts[0],id=Number(parts[1]),d=graph.def(scope,id);
    if(!d){closeLineage();closeEl('lineage');return;}
    var seq=lineageSeq;
    lineageGraph.setData(relatedDefs(scope,d),{});
    renderLineageDetails(scope,id);
    requestAnimationFrame(function(){requestAnimationFrame(function(){if(seq===lineageSeq)lineageGraph.fit();});});
  }
  function openLineage(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    closeEl('compute-view');graph.selectNode(scope,id);lineageSeq++;
    lineageState={activeKey:scope+':'+id,activeCard:null,activeTable:null,linkSeq:0};
    setLineageLinkStatus('');
    $('lineage-title').textContent='血缘追溯 · '+d.name;
    $('lineage-tag').className='tag tag-'+scope;$('lineage-tag').textContent=LABEL[scope];
    openEl('lineage');setLineageTab('current');refreshLineage();
  }

  // ---------- 数据与布局 ----------
  function graphDefs(){
    var out={document:[],source:[],index:[],rule:[],frame:[]},sourceByKey={},indexSource={};
    defs.index.slice().sort(function(a,b){return Number(a.id)-Number(b.id);}).forEach(function(d){
      var key=d.datasource_id+':'+d.source_table,source=sourceByKey[key];
      if(!source){
        var comment=tableComments[d.datasource_id+':'+d.source_table]||'';
        source={id:d.id,datasource_id:d.datasource_id,source_table:d.source_table,
          table_comment:comment,index_ids:[],source_columns:[],name:comment||d.source_table,_scope:'source'};
        sourceByKey[key]=source;out.source.push(source);
      }
      if(source.index_ids.indexOf(d.id)<0)source.index_ids.push(d.id);
      if(d.source_column&&source.source_columns.indexOf(d.source_column)<0)source.source_columns.push(d.source_column);
      indexSource[d.id]=source.id;
    });
    documentLinks.forEach(function(link){
      var sourceId=indexSource[link.index_id];if(sourceId==null)return;
      var doc=out.document.filter(function(d){return d.id===link.file_id;})[0];
      if(!doc){
        doc={id:link.file_id,file_id:link.file_id,name:link.file_name,index_ids:[],source_ids:[],source_tables:[],source_table_labels:[],row_count:0,_scope:'document'};
        out.document.push(doc);
      }
      if(doc.index_ids.indexOf(link.index_id)<0)doc.index_ids.push(link.index_id);
      if(doc.source_ids.indexOf(sourceId)<0)doc.source_ids.push(sourceId);
      var source=out.source.filter(function(item){return item.id===sourceId;})[0];
      if(source&&doc.source_table_labels.indexOf(source.name)<0)doc.source_table_labels.push(source.name);
      if(doc.source_tables.indexOf(link.source_table)<0)doc.source_tables.push(link.source_table);
      doc.row_count=Math.max(doc.row_count,Number(link.row_count)||0);
    });
    ['index','rule','frame'].forEach(function(s){
      out[s]=defs[s].map(function(d){
        var value=d._latest?d._latest[VFIELD[s]]:null,status=resultStatus(value);
        return Object.assign({},d,{_scope:s,_latest:d._latest,
          _agg:aggLabel(d.aggregate),_combine:combineLabel(d.combine),
          _status:status,_value:status||String(value==null?'':value)});
      });
    });
    return out;
  }
  function renderCompute(){
    var next=graphDefs();defs.source=next.source;defs.document=next.document;
    ['source','index','rule','frame'].forEach(renderAssets);
    graph.setData(next,layout);refreshLineage();
  }
  function loadAll(){
    var seq=++loadSeq;
    var documentsPromise=api('/api/compute/source-documents').catch(function(){return null;});
    return api('/api/compute/definitions').then(function(j){
      if(seq!==loadSeq)return;
      defs.index=j.index||[];defs.rule=j.rule||[];defs.frame=j.frame||[];
      lineageTableCache={};lineageTraceCache={};lineageTracePending={};
      computeLoaded=true;
      renderCompute();
      return documentsPromise;
    }).then(function(j){
      if(!j||seq!==loadSeq)return;
      documentLinks=j.items||[];
      (j.tables||[]).forEach(function(t){
        tableComments[t.datasource_id+':'+t.source_table]=t.table_comment||'';
      });
      renderCompute();
    }).catch(function(e){if(seq===loadSeq)err(e.message);});
  }
  function readLocal(){
    try{return JSON.parse(localStorage.getItem(LOCAL_KEY)||'{}');}catch(e){return {};}
  }
  function loadLayout(){
    var local=readLocal();
    return api('/api/compute/layout').then(function(j){
      layoutAvailable=j.available!==false;
      layout=Object.assign({},local);
      if(layoutAvailable)(j.items||[]).forEach(function(p){layout[p.scope+':'+p.id]=p;});
      updateLayoutSaveState();
      if(computeLoaded)renderCompute();
    }).catch(function(){layoutAvailable=false;layout=local;updateLayoutSaveState();if(computeLoaded)renderCompute();});
  }
  function updateLayoutSaveState(){
    var btn=$('layout-save');
    btn.disabled=layoutSaving||!layoutAvailable;
    btn.textContent=layoutSaving?'保存中…':'保存布局';
    btn.classList.toggle('is-dirty',layoutDirty);
    btn.title=layoutAvailable?(layoutDirty?'当前位置尚未保存到数据库':'将当前血缘图位置保存到数据库'):'布局表未安装，无法保存到数据库';
  }
  function currentLayoutItems(){
    return Object.keys(graph.positions).map(function(k){return graph.positions[k];}).filter(function(p){
      return p&&['document','source','index','rule','frame'].indexOf(p.scope)>=0;
    }).map(function(p){return {scope:p.scope,id:p.id,x:p.x,y:p.y};});
  }
  function saveLayout(manual){
    if(layoutSaving)return Promise.resolve();
    if(!layoutAvailable){if(manual)err('布局表尚未安装，暂时无法保存到数据库');return Promise.resolve();}
    var items=currentLayoutItems();
    layoutSaving=true;updateLayoutSaveState();
    return api('/api/compute/layout',{method:'PUT',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({items:items})}).then(function(j){
        layoutDirty=false;if(manual)ok('已保存 '+(j.saved==null?items.length:j.saved)+' 个节点位置');
      }).catch(function(e){if(manual)err('保存失败：'+e.message);else err('布局自动保存失败：'+e.message);})
      .then(function(){layoutSaving=false;updateLayoutSaveState();});
  }
  function queueLayoutSave(next){
    layout=next;layoutDirty=true;updateLayoutSaveState();
    try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).map(function(k){return layout[k];})));}catch(e){}
    clearTimeout(saveTimer);
    saveTimer=setTimeout(function(){saveLayout(false);},700);
  }

  // ---------- 复核 ----------
  function openReplay(scope,vid){
    $('tr-title').textContent='结果复核';$('tr-body').innerHTML='<div class="empty">复核中…</div>';openEl('trace');
    api('/api/'+scope+'/value/'+vid+'/replay').then(function(j){
      var h='<div class="banner '+(j.consistent?'info':'err')+'">'+(j.consistent?
        '复核一致：按当前配置重算，结果与存储值相符。':'复核不一致：重算结果与存储值有差异，请核查配置或数据是否变化。')+'</div>';
      h+='<table class="cmp"><thead><tr><th>项目</th><th>存储值</th><th>重算值</th><th>结果</th></tr></thead><tbody>';
      Object.keys(j.checks).forEach(function(k){var c=j.checks[k];
        h+='<tr><td>'+esc(labelOf(k))+'</td><td><code>'+esc(String(c.stored).slice(0,90))+
          '</code></td><td><code>'+esc(String(c.recomputed).slice(0,90))+'</code></td><td class="'+(c.match?'ok':'bad')+'">'+(c.match?'一致':'不一致')+'</td></tr>';});
      h+='</tbody></table><p class="hint">'+esc(j.note||'')+'</p>';$('tr-body').innerHTML=h;
    }).catch(function(e){$('tr-body').innerHTML='<div class="banner err">'+esc(e.message)+'</div>';});
  }
  function labelOf(k){return {index_value:'指标值',rule_value:'规则结果',frame_value:'框架结果'}[k]||k;}

  loadDatasources();
  Promise.all([loadLayout(),loadAll()]).then(function(){graph.fit();});
})();
