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
  var lineageSeq=0,lineageState=null,sourceFiles={};

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
  $('lineage').addEventListener('click',function(e){if(e.target===this)closeLineage();});
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&!$('lineage').hidden&&!document.querySelector('.drawer:not([hidden]):not(#lineage)')){
      closeLineage();closeEl('lineage');
    }
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-lineage-tab]'),function(btn){
    btn.onclick=function(){setLineageTab(btn.dataset.lineageTab);};
  });

  var graph=new ComputeGraph($('graph-canvas'),{
    action:nodeAction,menu:openNodeMenu,select:selectNode,connect:connectNodes,disconnect:disconnectEdge,layout:queueLayoutSave
  });
  var lineageGraph=new ComputeGraph($('lineage-graph'),{
    select:function(scope,id){
      if(!lineageState)return;lineageState.activeKey=scope+':'+id;
      var d=lineageGraph.def(scope,id);if(d)$('lineage-selection').textContent=LABEL[scope]+' · '+d.name;
    },
    inspect:function(scope,id){renderLineageDetails(scope,id);}
  },{compact:true});
  $('zoom-in').onclick=function(){graph.zoom(1.15);};
  $('zoom-out').onclick=function(){graph.zoom(1/1.15);};
  $('graph-fit').onclick=function(){graph.fit();};
  $('graph-auto').onclick=function(){graph.autoLayout();ok('已自动排布');};
  $('edge-del').onclick=function(){graph.deleteSelected();};

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
    return api('/api/load/datasources/'+ds+'/tables').then(function(j){
      var names=(j.items||[]).map(function(x){return typeof x==='string'?x:x.name;});
      t.innerHTML='<option value="">请选择</option>'+names.map(function(n){
        return '<option value="'+esc(n)+'">'+esc(n)+'</option>';}).join('');
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
    }).join('')||'<span class="hint">还没有规则，请先建规则</span>';
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
  function latest(scope,id){
    return api('/api/'+scope+'/'+id+'/values?limit=1').then(function(j){return (j.items||[])[0]||null;});
  }
  var MENU_ICON={
    view:'<path d="M2 8s2.5-4 6-4 6 4 6 4-2.5 4-6 4-6-4-6-4Z"/><circle cx="8" cy="8" r="1.5"/>',
    edit:'<path d="m3 13 8-8 2 2-8 8-3 1 1-3Z"/>',
    run:'<path d="m5 3 7 5-7 5V3Z"/>',
    trace:'<path d="M2 3h5v5H2zM9 8h5v5H9zM7 5h2v6h2"/>',
    replay:'<path d="M13 6a5 5 0 1 0 1 5M13 2v4H9"/>',
    open:'<path d="M6 3h7v10H6zM3 5v8h3M9 6h2M9 9h2"/>',
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
      h=actionMenuItem('view','查看',d)+actionMenuItem('trace','追溯',d)+
        actionMenuItem('edit','编辑指标',d);
    }else if(scope==='document'){
      h=actionMenuItem('view','查看',d)+actionMenuItem('trace','追溯',d)+
        actionMenuItem('open','打开原件',d);
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
        '<button type="button" class="asset-main" data-id="'+d.id+'" title="'+esc(d.name)+'" aria-label="查看'+esc(d.name)+'">'+
        '<b>'+esc(d.name)+'</b></button>'+
        '<button type="button" class="icon-btn mini asset-more" data-action-menu="compute-action-menu" '+
        'data-scope="'+scope+'" data-id="'+d.id+'" data-tip="更多操作" aria-haspopup="menu" aria-expanded="false" '+
        'aria-label="'+esc(d.name)+'更多操作">⋯</button></article>';
    }).join('')||'<div class="asset-empty">暂无'+LABEL[scope]+'</div>';
    host.onclick=function(e){
      var trigger=e.target.closest?e.target.closest('[data-action-menu]'):null;
      if(trigger){fillActionMenu(trigger.dataset.scope,Number(trigger.dataset.id));return;}
      var main=e.target.closest?e.target.closest('.asset-main'):null;
      if(main){var id=Number(main.dataset.id);graph.focus(scope,id);selectNode(scope,id);}
    };
  }
  function nodeAction(scope,id,act,v){
    var d=graph.def(scope,id);if(!d)return;
    if(act==='view')openView(scope,d);
    else if(act==='edit'){
      if(scope==='source'){var index=graph.def('index',(d.index_ids||[])[0]);if(index)fillForm('index',index);}
      else fillForm(scope,d);
    }else if(act==='open')window.open('/srcfiles/'+encodeURIComponent(id),'_blank','noopener');
    else if(act==='run')doRun(scope,id);
    else if(act==='trace')openLineage(scope,id);
    else if(act==='replay'&&v)openReplay(scope,v.id);
    else if(act==='del')doDelete(scope,id);
  }
  function doDelete(scope,id){
    var d=graph.def(scope,id);if(!d||!confirm('确定删除「'+d.name+'」及其全部结果？'))return;
    api('/api/'+scope+'/'+id,{method:'DELETE'}).then(function(){
      delete layout[scope+':'+id];
      try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).filter(function(k){return ['index','rule','frame'].indexOf(layout[k].scope)>=0;}).map(function(k){return layout[k];})));}catch(e){}
      loadAll();ok('已删除');
    })
      .catch(function(e){err(e.message);});
  }
  function doRun(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    if(!confirm('确认按当前配置运行「'+d.name+'」？运行后会生成一条新结果。'))return;
    post('/api/'+scope+'/'+id+'/run',{}).then(function(){loadAll();ok('已计算');})
      .catch(function(e){err(e.message);});
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
      h+='<div><span>业务库 ID</span><b>'+esc(d.datasource_id)+'</b></div><div><span>业务表</span><b>'+esc(d.source_table)+'</b></div>'+
        '<div><span>关联指标</span><b>'+esc((d.index_ids||[]).length)+'</b></div>';
    }else if(scope==='document'){
      h+='<div><span>资料 ID</span><b>'+esc(d.id)+'</b></div><div><span>匹配业务行</span><b>'+esc(d.row_count)+'</b></div>'+
        '<div><span>来源业务表</span><b>'+esc((d.source_tables||[]).join('、')||'—')+'</b></div>';
    }else if(scope==='index'){
      h+='<div><span>业务库 ID</span><b>'+esc(d.datasource_id)+'</b></div><div><span>业务表</span><b>'+esc(d.source_table)+'</b></div>'+
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
    if(d._latest)h+='<h3 class="view-sub">最近结果</h3><div class="view-row">'+esc(d._latest[VFIELD[scope]])+'</div>';
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

  // ---------- 全宽上游追溯工作台 ----------
  function closeLineage(){
    lineageSeq++;lineageState=null;graph.selectNode(null);lineageGraph.selectNode(null);
  }
  function setLineageTab(tab){
    Array.prototype.forEach.call(document.querySelectorAll('[data-lineage-tab]'),function(btn){
      var on=btn.dataset.lineageTab===tab;btn.classList.toggle('is-active',on);btn.setAttribute('aria-selected',String(on));
    });
    $('lineage-data-panel').classList.toggle('lineage-mobile-active',tab==='data');
    $('lineage-document-panel').classList.toggle('lineage-mobile-active',tab==='document');
  }
  function relatedDefs(scope,d){
    var full=graphDefs(),downstream=scope==='source'||scope==='document',seen={},queue=[{scope:scope,d:d}],out={document:[],source:[],index:[],rule:[],frame:[]};
    function push(next){
      if(!next)return;
      if(!next.d)next.d=full[next.scope].filter(function(d){return d.id===next.id;})[0];
      if(next.d&&!seen[next.scope+':'+next.id])queue.push(next);
    }
    while(queue.length){
      var item=queue.shift(),x=item.d,key=item.scope+':'+x.id;if(seen[key])continue;seen[key]=true;
      if(out[item.scope].indexOf(x)<0)out[item.scope].push(x);
      if(item.scope==='document')(x.source_ids||[]).forEach(function(id){push({scope:'source',id:id});});
      else if(item.scope==='source'){
        full.document.filter(function(doc){return (doc.source_ids||[]).indexOf(x.id)>=0;}).forEach(function(doc){push({scope:'document',d:doc});});
        if(downstream)(x.index_ids||[]).forEach(function(id){push({scope:'index',id:id});});
      }else if(item.scope==='index'){
        full.source.filter(function(s){return (s.index_ids||[]).indexOf(x.id)>=0;}).forEach(function(s){push({scope:'source',d:s});});
        if(downstream)full.rule.filter(function(r){return (r.index_refs_json||[]).some(function(ref){return ref.index_id===x.id;});}).forEach(function(r){push({scope:'rule',d:r});});
      }else if(item.scope==='rule'){
        (x.index_refs_json||[]).forEach(function(ref){push({scope:'index',id:ref.index_id});});
        if(downstream)full.frame.filter(function(f){return (f.rule_refs_json||[]).some(function(ref){return ref.rule_id===x.id;});}).forEach(function(f){push({scope:'frame',d:f});});
      }else if(item.scope==='frame')(x.rule_refs_json||[]).forEach(function(ref){push({scope:'rule',id:ref.rule_id});});
    }
    ['document','source','index','rule','frame'].forEach(function(s){out[s]=out[s].map(function(x){return full[s].filter(function(d){return d.id===x.id;})[0]||x;});});
    return out;
  }
  function selectedIndices(scope,d){
    var ids=[];
    function addIndex(id){if(id!=null&&ids.indexOf(id)<0)ids.push(id);}
    if(scope==='index')addIndex(d.id);
    else if(scope==='source'||scope==='document')(d.index_ids||[]).forEach(addIndex);
    else if(scope==='rule')(d.index_refs_json||[]).forEach(function(ref){addIndex(ref.index_id);});
    else if(scope==='frame')(d.rule_refs_json||[]).forEach(function(ref){
      var rule=graph.def('rule',ref.rule_id);if(rule)(rule.index_refs_json||[]).forEach(function(r){addIndex(r.index_id);});
    });
    return ids.map(function(id){return graph.def('index',id);}).filter(Boolean);
  }
  function indexGroups(indices){
    var groups=[],byKey={};
    indices.forEach(function(d){
      var key=d.datasource_id+':'+d.source_table,g=byKey[key];
      if(!g){g={key:key,datasource_id:d.datasource_id,table:d.source_table,indices:[]};byKey[key]=g;groups.push(g);}
      g.indices.push(d);
    });
    return groups;
  }
  function resetLineageDocument(){
    if(lineageState)lineageState.cellSeq=(lineageState.cellSeq||0)+1;
    $('lineage-open-source').hidden=true;$('lineage-document-status').textContent='';
    var frame=$('lineage-document-frame');frame.hidden=true;frame.removeAttribute('src');frame.removeAttribute('data-file');
  }
  function loadSourceFiles(){
    if(sourceFiles.loaded){if(lineageState)renderLineageDocuments(lineageState.indices);return;}
    if(sourceFiles.loading)return;
    sourceFiles.loading=true;
    api('/api/sources?page=1&size=200').then(function(j){
      sourceFiles.loaded=true;(j.items||[]).forEach(function(f){sourceFiles[f.id]=f.name||('资料 #'+f.id);});
      if(lineageState)renderLineageDocuments(lineageState.indices);
    }).catch(function(){}).then(function(){sourceFiles.loading=false;});
  }
  function renderLineageTables(groups){
    var host=$('lineage-data');
    if(!groups.length){host.innerHTML='<div class="lineage-empty">当前节点没有关联业务表。</div>';return;}
    host.innerHTML=groups.map(function(g){
      var active=lineageState.activeIndexByTable[g.key]||g.indices[0].id;
      return '<section class="lineage-table-card" data-table="'+esc(g.key)+'">'+
        '<div class="lineage-table-title">'+esc(g.table)+'<small>业务库 #'+esc(g.datasource_id)+'</small></div>'+
        '<div class="lineage-index-row">'+g.indices.map(function(d){
          return '<button type="button" class="lineage-index'+(d.id===active?' on':'')+'" data-index="'+d.id+'">'+esc(d.name)+'</button>';
        }).join('')+'</div><div class="table-preview" data-preview><div class="lineage-empty">加载匹配数据…</div></div></section>';
    }).join('');
    Array.prototype.forEach.call(host.querySelectorAll('[data-index]'),function(btn){
      btn.onclick=function(){
        var card=btn.closest('[data-table]'),key=card.dataset.table,id=Number(btn.dataset.index);
        lineageState.activeIndexByTable[key]=id;
        Array.prototype.forEach.call(card.querySelectorAll('[data-index]'),function(x){x.classList.toggle('on',Number(x.dataset.index)===id);});
        loadTablePreview(key,id);
      };
    });
    groups.forEach(function(g){
      var active=lineageState.activeIndexByTable[g.key]||g.indices[0].id;
      lineageState.activeIndexByTable[g.key]=active;loadTablePreview(g.key,active);
    });
  }
  function renderSampleData(j,host){
    var canTrace=(j.trace_columns||[]).indexOf('file_id')>=0&&(j.trace_columns||[]).indexOf('record_id')>=0;
    var tableKey=host.closest('[data-table]')?host.closest('[data-table]').dataset.table:'';
    var h='<div class="sample-summary"><span>匹配 <b>'+esc(j.total)+'</b> 行</span><span>展示 '+esc(j.items.length)+' 行</span>'+
      (j.has_more?'<span>仅样本</span>':'')+'</div>';
    if(!canTrace)h+='<div class="lineage-empty">业务表缺少 file_id / record_id，仅展示样本。</div>';
    if(j.items.length)h+='<div class="sample-scroll"><table class="sample-table"><thead><tr>'+j.columns.map(function(c){return '<th>'+esc(c)+'</th>';}).join('')+
      '</tr></thead><tbody>'+j.items.map(function(row,rowIndex){
        return '<tr data-row="'+rowIndex+'">'+j.columns.map(function(c){
          var value=row[c],text=value==null?'NULL':String(value);
          return '<td>'+(canTrace&&row.record_id!=null&&c!=='file_id'&&c!=='record_id'&&value!=null?
            '<button type="button" class="linkbtn source-cell" data-rid="'+esc(row.record_id)+'" data-col="'+esc(c)+'" data-row="'+rowIndex+'" data-table="'+esc(tableKey)+'" data-file="'+esc(row.file_id)+'" data-tip="定位原单元格">'+esc(text)+'</button>':esc(text))+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table></div>';
    else h+='<div class="lineage-empty">当前筛选没有匹配记录。</div>';
    host.innerHTML=h;
    Array.prototype.forEach.call(host.querySelectorAll('[data-rid]'),function(btn){
      btn.onclick=function(){locateLineageCell(btn.dataset.rid,btn.dataset.col,Number(btn.dataset.row),btn.dataset.file,btn.dataset.table);};
    });
  }
  function loadTablePreview(key,indexId){
    if(!lineageState)return;
    var seq=lineageState.seq,card=Array.prototype.filter.call($('lineage-data').querySelectorAll('[data-table]'),function(x){return x.dataset.table===key;})[0];
    if(!card)return;
    var host=card.querySelector('[data-preview]');host.innerHTML='<div class="lineage-empty">加载匹配数据…</div>';
    api('/api/index/'+indexId+'/source-preview?limit=50').then(function(j){
      if(!lineageState||seq!==lineageState.seq||lineageState.activeIndexByTable[key]!==indexId)return;
      lineageState.previews[key]=j;renderSampleData(j,host);
    }).catch(function(e){if(lineageState&&seq===lineageState.seq)host.innerHTML='<div class="banner err">'+esc(e.message)+'</div>';});
  }
  function renderLineageDocuments(indices){
    if(!lineageState)return;
    var ids={},docs=[];
    (indices||[]).forEach(function(index){if(index)ids[index.id]=true;});
    documentLinks.forEach(function(link){
      if(!ids[link.index_id])return;
      var doc=docs.filter(function(d){return d.id===link.file_id;})[0];
      if(!doc){doc={id:link.file_id,name:link.file_name,tables:[],row_count:0};docs.push(doc);}
      if(doc.tables.indexOf(link.source_table)<0)doc.tables.push(link.source_table);
      doc.row_count=Math.max(doc.row_count,Number(link.row_count)||0);
    });
    docs.sort(function(a,b){return b.row_count-a.row_count||a.id-b.id;});
    $('lineage-documents').innerHTML=docs.map(function(d){
      return '<button type="button" class="lineage-document-chip'+(String(lineageState.activeFileId)===String(d.id)?' on':'')+'" data-file="'+esc(d.id)+'" title="'+esc(d.name)+'">'+
        esc(sourceFiles[d.id]||d.name||('资料 #'+d.id))+' · '+esc(d.row_count)+' 行</button>';
    }).join('')||'<div class="lineage-empty">未匹配到资料文件。</div>';
    Array.prototype.forEach.call($('lineage-documents').querySelectorAll('[data-file]'),function(btn){
      btn.onclick=function(){showLineageDocument(Number(btn.dataset.file),btn.title);};
    });
  }
  function locateLineageCell(rid,col,rowIndex,fileId,tableKey){
    if(!lineageState)return;
    var seq=lineageState.seq,request=++lineageState.cellSeq,status=$('lineage-document-status');lineageState.activeFileId=fileId;
    Array.prototype.forEach.call($('lineage-data').querySelectorAll('tr[data-row]'),function(tr){
      tr.classList.toggle('selected-row',tr.closest('[data-table]').dataset.table===tableKey&&Number(tr.dataset.row)===rowIndex);
    });
    renderLineageDocuments(lineageState.indices);setLineageTab('document');status.textContent='定位原单元格…';
    api('/api/staging/locate/'+encodeURIComponent(rid)+'?key='+encodeURIComponent(col)).then(function(j){
      if(!lineageState||seq!==lineageState.seq||request!==lineageState.cellSeq)return;
      var key=j.field||col,file=j.file_id,name=sourceFiles[file]||('资料 #'+file),base='/preview?embed=1&file='+encodeURIComponent(file);
      var frame=$('lineage-document-frame');lineageState.activeFileId=file;renderLineageDocuments(lineageState.indices);
      status.textContent=name+' · 记录 '+j.record_index+' · '+key;
      var open=$('lineage-open-source');open.hidden=false;open.href='/srcfiles/'+encodeURIComponent(file);frame.hidden=false;
      if(frame.getAttribute('data-file')===String(file))frame.contentWindow.postMessage({c1TraceKey:{key:key,index:j.record_index}},window.location.origin);
      else{frame.setAttribute('data-file',String(file));frame.src=base+'&index='+encodeURIComponent(j.record_index)+'&key='+encodeURIComponent(key);}
    }).catch(function(e){if(lineageState&&seq===lineageState.seq&&request===lineageState.cellSeq)status.textContent='无法定位：'+e.message;});
  }
  function showLineageDocument(fileId,name){
    if(!lineageState)return;
    lineageState.cellSeq=(lineageState.cellSeq||0)+1;
    lineageState.activeFileId=fileId;renderLineageDocuments(lineageState.indices);
    $('lineage-document-status').textContent=name||('资料 #'+fileId);
    var open=$('lineage-open-source');open.hidden=false;open.href='/srcfiles/'+encodeURIComponent(fileId);
    var frame=$('lineage-document-frame');frame.hidden=false;
    if(frame.getAttribute('data-file')!==String(fileId)){frame.setAttribute('data-file',String(fileId));frame.src='/preview?embed=1&file='+encodeURIComponent(fileId);}
    setLineageTab('document');
  }
  function renderLineageDetails(scope,id){
    if(!lineageState)return;
    var d=lineageGraph.def(scope,id);if(!d)return;
    lineageState.activeKey=scope+':'+id;lineageState.indices=selectedIndices(scope,d);
    $('lineage-selection').textContent=LABEL[scope]+' · '+d.name;
    resetLineageDocument();renderLineageTables(indexGroups(lineageState.indices));renderLineageDocuments(lineageState.indices);
    if(scope==='document')showLineageDocument(id,d.name);
  }
  function openLineage(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    graph.selectNode(scope,id);
    var seq=++lineageSeq;
    lineageState={key:scope+':'+id,seq:seq,activeKey:scope+':'+id,indices:[],previews:{},activeIndexByTable:{},activeFileId:null,cellSeq:0};
    $('lineage-title').textContent='上游追溯 · '+d.name;$('lineage-tag').className='tag tag-'+scope;$('lineage-tag').textContent=LABEL[scope];
    openEl('lineage');lineageGraph.setData(relatedDefs(scope,d),{});lineageGraph.selectNode(scope,id);
    requestAnimationFrame(function(){requestAnimationFrame(function(){lineageGraph.fit();});});
    setLineageTab('data');renderLineageDetails(scope,id);loadSourceFiles();
  }

  // ---------- 数据与布局 ----------
  function graphDefs(){
    var out={document:[],source:[],index:[],rule:[],frame:[]},sourceByKey={},indexSource={};
    defs.index.forEach(function(d){
      var key=d.datasource_id+':'+d.source_table,source=sourceByKey[key];
      if(!source){
        source={id:d.id,datasource_id:d.datasource_id,source_table:d.source_table,
          index_ids:[],source_columns:[],name:d.source_table,_scope:'source'};
        sourceByKey[key]=source;out.source.push(source);
      }
      if(source.index_ids.indexOf(d.id)<0)source.index_ids.push(d.id);
      if(d.source_column&&source.source_columns.indexOf(d.source_column)<0)source.source_columns.push(d.source_column);
      indexSource[d.id]=source.id;
    });
    documentLinks.forEach(function(link){
      var doc=out.document.filter(function(d){return d.id===link.file_id;})[0];
      if(!doc){
        doc={id:link.file_id,file_id:link.file_id,name:link.file_name,index_ids:[],source_ids:[],source_tables:[],row_count:0,_scope:'document'};
        out.document.push(doc);
      }
      if(doc.index_ids.indexOf(link.index_id)<0)doc.index_ids.push(link.index_id);
      var sourceId=indexSource[link.index_id];
      if(sourceId!=null&&doc.source_ids.indexOf(sourceId)<0)doc.source_ids.push(sourceId);
      if(doc.source_tables.indexOf(link.source_table)<0)doc.source_tables.push(link.source_table);
      doc.row_count=Math.max(doc.row_count,Number(link.row_count)||0);
    });
    ['index','rule','frame'].forEach(function(s){
      out[s]=defs[s].map(function(d){return Object.assign({},d,{_scope:s,_latest:d._latest,
        _agg:aggLabel(d.aggregate),_combine:combineLabel(d.combine),
        _value:d._latest?String(d._latest[VFIELD[s]]==null?'':d._latest[VFIELD[s]]):''});});
    });
    return out;
  }
  function loadAll(){
    var selectedKey=graph.selectedNode;
    return api('/api/index').then(function(j){defs.index=j.items||[];})
      .then(function(){return api('/api/rule');}).then(function(j){defs.rule=j.items||[];})
      .then(function(){return api('/api/frame');}).then(function(j){defs.frame=j.items||[];})
      .then(function(){
        var tasks=[];
        ['index','rule','frame'].forEach(function(s){defs[s].forEach(function(d){
          tasks.push(latest(s,d.id).then(function(v){d._latest=v;}));
        });});
        return Promise.all(tasks);
      }).then(function(){
        return api('/api/compute/source-documents').catch(function(){return {items:[]};});
      }).then(function(j){
        documentLinks=j.items||[];
        var next=graphDefs();defs.source=next.source;defs.document=next.document;
        ['source','index','rule','frame'].forEach(renderAssets);
        graph.setData(next,layout);
        if(lineageState&&selectedKey===lineageState.key){
          var parts=selectedKey.split(':'),scope=parts[0],id=Number(parts[1]);
          if(graph.def(scope,id))openLineage(scope,id);else{closeLineage();closeEl('lineage');}
        }
      })
      .catch(function(e){err(e.message);});
  }
  function readLocal(){
    try{return JSON.parse(localStorage.getItem(LOCAL_KEY)||'{}');}catch(e){return {};}
  }
  function loadLayout(){
    var local=readLocal();
    return api('/api/compute/layout').then(function(j){
      layoutAvailable=j.available!==false;
      layout=layoutAvailable?{}:local;
      if(layoutAvailable)(j.items||[]).forEach(function(p){layout[p.scope+':'+p.id]=p;});
      $('layout-state').textContent=layoutAvailable?'坐标自动保存':'未安装布局表 · 仅保存本机';
    }).catch(function(e){layoutAvailable=false;layout=local;$('layout-state').textContent='布局读取失败 · 仅保存本机';});
  }
  function queueLayoutSave(next){
    layout=next;
    try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).filter(function(k){return ['index','rule','frame'].indexOf(layout[k].scope)>=0;}).map(function(k){return layout[k];})));}catch(e){}
    $('layout-state').textContent='正在保存…';clearTimeout(saveTimer);
    saveTimer=setTimeout(function(){
      if(!layoutAvailable){$('layout-state').textContent='未安装布局表 · 仅保存本机';return;}
      var items=Object.keys(layout).filter(function(k){return ['index','rule','frame'].indexOf(layout[k].scope)>=0;}).map(function(k){var p=layout[k];return {scope:p.scope,id:p.id,x:p.x,y:p.y};});
      api('/api/compute/layout',{method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({items:items})}).then(function(){ $('layout-state').textContent='坐标已保存';})
        .catch(function(e){$('layout-state').textContent='保存失败：'+e.message;});
    },500);
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

  loadDatasources();loadLayout().then(function(){setTimeout(function(){loadAll().then(function(){graph.fit();});},0);});
})();
