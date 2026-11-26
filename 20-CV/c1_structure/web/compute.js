/* web/compute.js — 计算资产库 + 计算流程配置 + 抽屉编辑 + 追溯 + 复核。 */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var PFX={index:'i',rule:'r',frame:'f'};
  var LABEL={source:'数据',index:'指标',rule:'规则',frame:'框架'};
  var VFIELD={index:'index_value',rule:'rule_value',frame:'frame_value'};
  var defs={index:[],rule:[],frame:[]};
  var editing={index:null,rule:null,frame:null};
  var editingScope='index',layout={},layoutAvailable=true,saveTimer=null;
  var LOCAL_KEY='c1.compute.layout';
  var inspectorSeq=0;

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
  $('inspector-close').onclick=closeInspector;
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape'&&!$('compute-inspector').hidden&&!document.querySelector('.drawer:not([hidden])'))closeInspector();
  });

  var graph=new ComputeGraph($('graph-canvas'),{
    action:nodeAction,menu:openNodeMenu,select:openInspector,connect:connectNodes,disconnect:disconnectEdge,layout:queueLayoutSave
  });
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
      '<button type="button" class="btn mini ghost" data-k="x" title="删除条件">×</button>';
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
  function detail(scope,d){
    if(scope==='index')return esc(d.source_table)+(d.source_column?' · '+esc(d.source_column):'')+
      ' <span class="tag2">'+esc(aggLabel(d.aggregate))+'</span>';
    if(scope==='rule'){
      var cs=d.conditions_json||[];
      return esc(cs.length+' 个条件')+' · '+esc(combineLabel(d.combine));
    }
    return esc(combineLabel(d.combine))+' · '+esc((d.rule_refs_json||[]).length)+' 条规则';
  }
  function actionMenuItem(act,label,d,v,disabled){
    return '<button type="button" role="menuitem" class="menu-item'+(act==='del'?' danger':'')+
      '" data-act="'+act+'" data-id="'+d.id+'"'+(v?' data-vid="'+v.id+'"':'')+
      (disabled?' disabled title="暂无可追溯结果"':'')+'>'+label+'</button>';
  }
  function fillActionMenu(scope,id){
    var d=defs[scope].filter(function(x){return x.id===id;})[0];
    if(!d)return;
    var v=d._latest,menu=$('compute-action-menu');
    menu.innerHTML=actionMenuItem('view','查看',d)+actionMenuItem('edit','编辑',d)+
      actionMenuItem('run','运行',d)+actionMenuItem('trace','追溯',d)+
      actionMenuItem('replay','复核',d,v,!v)+'<div class="menu-sep"></div>'+
      actionMenuItem('del','删除',d);
    menu.onclick=function(e){
      var item=e.target.closest?e.target.closest('[data-act]'):null;
      if(!item||item.disabled)return;
      nodeAction(scope,Number(item.dataset.id),item.dataset.act,
        item.dataset.vid?{id:Number(item.dataset.vid)}:null);
    };
  }
  function openNodeMenu(scope,id){fillActionMenu(scope,id);}
  function renderAssets(scope){
    var host=$(PFX[scope]+'-assets');
    $(PFX[scope]+'-count').textContent=defs[scope].length;
    host.innerHTML=defs[scope].map(function(d){
      return '<article class="asset-item" data-key="'+scope+':'+d.id+'">'+
        '<button type="button" class="asset-main" data-id="'+d.id+'" aria-label="定位'+esc(d.name)+'">'+
        '<b>'+esc(d.name)+'</b><span class="asset-detail">'+detail(scope,d)+'</span></button>'+
        '<button type="button" class="icon-btn mini asset-more" data-action-menu="compute-action-menu" '+
        'data-scope="'+scope+'" data-id="'+d.id+'" aria-haspopup="menu" aria-expanded="false" '+
        'aria-label="'+esc(d.name)+'更多操作">⋯</button></article>';
    }).join('')||'<div class="asset-empty">暂无'+LABEL[scope]+'</div>';
    host.onclick=function(e){
      var trigger=e.target.closest?e.target.closest('[data-action-menu]'):null;
      if(trigger){fillActionMenu(trigger.dataset.scope,Number(trigger.dataset.id));return;}
      var main=e.target.closest?e.target.closest('.asset-main'):null;
      if(main){var id=Number(main.dataset.id);graph.focus(scope,id);openInspector(scope,id);}
    };
  }
  function nodeAction(scope,id,act,v){
    var d=graph.def(scope,id);if(!d)return;
    if(act==='view')openView(scope,d);
    else if(act==='edit')fillForm(scope,d);
    else if(act==='run')doRun(scope,id);
    else if(act==='trace')openInspector(scope,id);
    else if(act==='replay'&&v)openReplay(scope,v.id);
    else if(act==='del')doDelete(scope,id);
  }
  function doDelete(scope,id){
    var d=graph.def(scope,id);if(!d||!confirm('确定删除「'+d.name+'」及其全部结果？'))return;
    api('/api/'+scope+'/'+id,{method:'DELETE'}).then(function(){
      delete layout[scope+':'+id];
      try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).filter(function(k){return layout[k].scope!=='source';}).map(function(k){return layout[k];})));}catch(e){}
      loadAll();ok('已删除');
    })
      .catch(function(e){err(e.message);});
  }
  function doRun(scope,id){
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
    if(scope==='index'){
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
    h+='<div class="dfoot"><span class="spacer"></span><button type="button" class="btn" id="view-edit">编辑</button></div>';
    $('view-body').innerHTML=h;$('view-edit').onclick=function(){closeEl('compute-view');fillForm(scope,d);};
    openEl('compute-view');
  }

  // ---------- 节点血缘检查器 ----------
  function closeInspector(){
    inspectorSeq++;$('compute-inspector').hidden=true;
    $('inspector-body').innerHTML='';graph.selectNode(null);
  }
  function inspectorSummary(d){
    var rows=[];
    if(d._scope==='source'){
      rows.push(['业务表',d.source_table],['数据列',d.source_column||'整行']);
    }else if(d._scope==='index'){
      rows.push(['业务表',d.source_table],['数据列',d.source_column||'整行'],['运算',aggLabel(d.aggregate)]);
      if((d.filter_json||[]).length)rows.push(['筛选条件',JSON.stringify(d.filter_json)]);
    }else if(d._scope==='rule'){
      rows.push(['条件组合',combineLabel(d.combine)],['条件数',(d.conditions_json||[]).length]);
    }else rows.push(['组合方式',combineLabel(d.combine)],['通过阈值',d.threshold==null?'—':d.threshold]);
    if(d._latest)rows.push(['最近结果',d._latest[VFIELD[d._scope]]]);
    return '<div class="view-grid">'+rows.map(function(r){
      return '<div><span>'+esc(r[0])+'</span><b>'+esc(r[1])+'</b></div>';}).join('')+'</div>';
  }
  function lineageItems(scope,d,direction){
    var items=[];
    function add(s,id){var x=graph.def(s,id);if(x)items.push({scope:s,id:id,name:x.name,detail:x._scope==='source'?x.source_table:x._detail||''});}
    if(scope==='source'){
      if(direction==='down')add('index',d.index_id);
    }else if(scope==='index'){
      if(direction==='up')add('source',d.id);
      else defs.rule.forEach(function(r){if((r.index_refs_json||[]).some(function(x){return x.index_id===d.id;}))add('rule',r.id);});
    }else if(scope==='rule'){
      if(direction==='up')(d.index_refs_json||[]).forEach(function(r){add('index',r.index_id);});
      else defs.frame.forEach(function(f){if((f.rule_refs_json||[]).some(function(x){return x.rule_id===d.id;}))add('frame',f.id);});
    }else if(direction==='up')(d.rule_refs_json||[]).forEach(function(r){add('rule',r.rule_id);});
    return items;
  }
  function lineageSection(title,items){
    return '<section class="lineage-section"><h3>'+esc(title)+'</h3>'+(items.length?
      '<div class="lineage-list">'+items.map(function(x){
        return '<button type="button" class="lineage-link" data-scope="'+x.scope+'" data-id="'+x.id+'">'+
          '<span class="tag tag-'+x.scope+'">'+LABEL[x.scope]+'</span><b>'+esc(x.name)+'</b><span>›</span></button>';
      }).join('')+'</div>':'<div class="lineage-empty">无</div>')+'</section>';
  }
  function openInspector(scope,id){
    var d=graph.def(scope,id);if(!d)return;
    graph.selectNode(scope,id);
    var seq=++inspectorSeq,indexId=scope==='source'?d.index_id:id;
    $('compute-inspector').hidden=false;$('inspector-title').textContent=d.name;
    $('inspector-tag').className='tag tag-'+scope;$('inspector-tag').textContent=LABEL[scope];
    var h='<div class="banner info">当前配置＋当前数据，不是历史执行快照。</div>'+inspectorSummary(d);
    h+=lineageSection('上游血缘回溯',lineageItems(scope,d,'up'));
    h+=lineageSection('下游影响分析',lineageItems(scope,d,'down'));
    if(scope==='source'||scope==='index')h+='<section class="lineage-section" id="inspector-sample"><h3>匹配数据样本</h3><div class="empty">加载中…</div></section>';
    $('inspector-body').innerHTML=h;
    Array.prototype.forEach.call($('inspector-body').querySelectorAll('[data-scope]'),function(btn){
      btn.onclick=function(){var s=btn.dataset.scope,n=Number(btn.dataset.id);graph.focus(s,n);openInspector(s,n);};
    });
    if(scope==='source'||scope==='index')loadSourcePreview(indexId,seq);
  }
  function loadSourcePreview(indexId,seq){
    api('/api/index/'+indexId+'/source-preview?limit=50').then(function(j){
      if(seq!==inspectorSeq)return;
      var host=$('inspector-sample');if(!host)return;
      var canTrace=(j.trace_columns||[]).indexOf('file_id')>=0&&(j.trace_columns||[]).indexOf('record_id')>=0;
      var h='<div class="sample-summary"><span>匹配 <b>'+esc(j.total)+'</b> 行</span><span>展示前 '+esc(j.items.length)+' 行</span>'+
        (j.has_more?'<span>仅样本</span>':'')+'</div>';
      if(!canTrace)h+='<div class="lineage-empty">业务表缺少 file_id/record_id，仅展示样本，无法回查原单元格。</div>';
      if(j.items.length)h+='<div class="sample-scroll"><table class="sample-table"><thead><tr>'+j.columns.map(function(c){
        return '<th>'+esc(c)+'</th>';}).join('')+'</tr></thead><tbody>'+j.items.map(function(row){
        return '<tr>'+j.columns.map(function(c){
          var value=row[c],text=value==null?'NULL':String(value);
          return '<td>'+(canTrace&&row.record_id!=null&&c!=='file_id'&&c!=='record_id'?
            '<button type="button" class="linkbtn source-cell" data-rid="'+esc(row.record_id)+'" data-col="'+esc(c)+'"'+(value==null?' disabled':'')+'>'+esc(text)+'</button>':esc(text))+'</td>';
        }).join('')+'</tr>';
      }).join('')+'</tbody></table></div>';
      else h+='<div class="lineage-empty">当前筛选没有匹配记录。</div>';
      h+='<div class="source-preview" id="source-preview" hidden><div class="sample-summary" id="source-preview-status">原单元格预览</div>'+
        '<iframe id="source-preview-frame" title="原始资料单元格预览"></iframe></div>';
      host.innerHTML=h;
      Array.prototype.forEach.call(host.querySelectorAll('[data-rid]'),function(btn){btn.onclick=function(){openSourceCell(btn);};});
    }).catch(function(e){
      if(seq!==inspectorSeq)return;var host=$('inspector-sample');if(host)host.innerHTML='<div class="banner err">'+esc(e.message)+'</div>';
    });
  }
  function openSourceCell(btn){
    var rid=btn.dataset.rid,col=btn.dataset.col,panel=$('source-preview'),frame=$('source-preview-frame'),status=$('source-preview-status');
    panel.hidden=false;status.textContent='定位原单元格…';
    api('/api/staging/locate/'+encodeURIComponent(rid)+'?key='+encodeURIComponent(col)).then(function(j){
      var key=j.field||col,base='/preview?embed=1&file='+encodeURIComponent(j.file_id);
      status.textContent='资料 #'+j.file_id+' · 记录 '+j.record_index+' · '+key;
      if(frame.getAttribute('data-src')===base){
        frame.contentWindow.postMessage({c1TraceKey:{key:key,index:j.record_index}},window.location.origin);
      }else{
        frame.setAttribute('data-src',base);
        frame.src=base+'&index='+encodeURIComponent(j.record_index)+'&key='+encodeURIComponent(key);
      }
    }).catch(function(e){status.textContent='无法定位：'+e.message;});
  }

  // ---------- 数据与布局 ----------
  function graphDefs(){
    var out={source:[],index:[],rule:[],frame:[]};
    out.source=defs.index.map(function(d){return {id:d.id,index_id:d.id,_scope:'source',
      name:d.source_table+(d.source_column?'.'+d.source_column:' · 整行'),source_table:d.source_table,source_column:d.source_column};});
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
        ['index','rule','frame'].forEach(renderAssets);
        graph.setData(graphDefs(),layout);
        if(selectedKey){
          var parts=selectedKey.split(':'),scope=parts[0],id=Number(parts[1]);
          if(graph.def(scope,id))openInspector(scope,id);else closeInspector();
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
    try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).filter(function(k){return layout[k].scope!=='source';}).map(function(k){return layout[k];})));}catch(e){}
    $('layout-state').textContent='正在保存…';clearTimeout(saveTimer);
    saveTimer=setTimeout(function(){
      if(!layoutAvailable){$('layout-state').textContent='未安装布局表 · 仅保存本机';return;}
      var items=Object.keys(layout).filter(function(k){return layout[k].scope!=='source';}).map(function(k){var p=layout[k];return {scope:p.scope,id:p.id,x:p.x,y:p.y};});
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
