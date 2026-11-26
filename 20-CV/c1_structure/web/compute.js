/* web/compute.js — 计算资产库 + 计算流程配置 + 抽屉编辑 + 追溯 + 复核。 */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var PFX={index:'i',rule:'r',frame:'f'};
  var LABEL={index:'指标',rule:'规则',frame:'框架'};
  var VFIELD={index:'index_value',rule:'rule_value',frame:'frame_value'};
  var defs={index:[],rule:[],frame:[]};
  var editing={index:null,rule:null,frame:null};
  var editingScope='index',layout={},layoutAvailable=true,saveTimer=null;
  var LOCAL_KEY='c1.compute.layout';

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

  var graph=new ComputeGraph($('graph-canvas'),{
    action:nodeAction,menu:openNodeMenu,connect:connectNodes,disconnect:disconnectEdge,layout:queueLayoutSave
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
      actionMenuItem('run','运行',d)+actionMenuItem('trace','追溯',d,v,!v)+
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
      if(main)graph.focus(scope,Number(main.dataset.id));
    };
  }
  function nodeAction(scope,id,act,v){
    var d=graph.def(scope,id);if(!d)return;
    if(act==='view')openView(scope,d);
    else if(act==='edit')fillForm(scope,d);
    else if(act==='run')doRun(scope,id);
    else if(act==='trace'&&v)openTraceView(scope,v.id);
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

  // ---------- 数据与布局 ----------
  function graphDefs(){
    var out={index:[],rule:[],frame:[]};
    ['index','rule','frame'].forEach(function(s){
      out[s]=defs[s].map(function(d){return Object.assign({},d,{_scope:s,_latest:d._latest,
        _agg:aggLabel(d.aggregate),_combine:combineLabel(d.combine),
        _value:d._latest?String(d._latest[VFIELD[s]]==null?'':d._latest[VFIELD[s]]):''});});
    });
    return out;
  }
  function loadAll(){
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
    try{localStorage.setItem(LOCAL_KEY,JSON.stringify(Object.keys(layout).map(function(k){return layout[k];})));}catch(e){}
    $('layout-state').textContent='正在保存…';clearTimeout(saveTimer);
    saveTimer=setTimeout(function(){
      if(!layoutAvailable){$('layout-state').textContent='未安装布局表 · 仅保存本机';return;}
      var items=Object.keys(layout).map(function(k){var p=layout[k];return {scope:p.scope,id:p.id,x:p.x,y:p.y};});
      api('/api/compute/layout',{method:'PUT',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({items:items})}).then(function(){ $('layout-state').textContent='坐标已保存';})
        .catch(function(e){$('layout-state').textContent='保存失败：'+e.message;});
    },500);
  }

  // ---------- 追溯 / 复核 ----------
  function openTraceView(scope,vid){
    $('tr-title').textContent='全链路追溯';$('tr-body').innerHTML='<div class="empty">加载中…</div>';openEl('trace');
    api('/api/'+scope+'/value/'+vid+'/lineage').then(function(j){
      var h='<div class="banner info">以下为当前配置构成的元数据链，不是历史配置快照。</div>';
      h+='<div class="dlist">结果：<b>'+esc(String(j.result[VFIELD[j.scope]]))+'</b></div>';
      h+='<div class="chain">'+renderMeta(j.definition,0)+'</div>';$('tr-body').innerHTML=h;
      Array.prototype.forEach.call($('tr-body').querySelectorAll('[data-locate]'),function(btn){
        btn.onclick=function(){closeEl('trace');graph.focus(btn.dataset.scope,Number(btn.dataset.locate));};
      });
    }).catch(function(e){$('tr-body').innerHTML='<div class="banner err">'+esc(e.message)+'</div>';});
  }
  function renderMeta(m,depth){
    if(!m)return '';
    var h='<div class="chain-item" style="margin-left:'+(depth*14)+'px">'+
      '<div class="ct"><span class="tag tag-'+m.scope+'">'+LABEL[m.scope]+'</span> '+esc(m.name)+
      '<button type="button" class="linkbtn locate" data-scope="'+m.scope+'" data-locate="'+m.id+'">定位到配置图</button></div>'+
      '<div class="cd">'+metaConfig(m)+'</div></div>';
    (m.refs||[]).forEach(function(r){h+=renderMeta(r,depth+1);});return h;
  }
  function metaConfig(m){
    var c=m.config||{},parts=[];
    if(m.scope==='index'){
      parts.push('表 '+esc(c.source_table||'—'));if(c.source_column)parts.push('列 '+esc(c.source_column));
      parts.push('运算 '+esc(aggLabel(c.aggregate)));if(c.filter&&c.filter.length)parts.push('筛选 '+esc(JSON.stringify(c.filter)));
    }else if(m.scope==='rule'){
      parts.push('组合 '+esc(combineLabel(c.combine)));
      (c.conditions||[]).forEach(function(x){parts.push(esc(x.alias)+' '+esc(opLabel(x.op))+' '+esc(x.threshold));});
    }else{parts.push('组合 '+esc(combineLabel(c.combine)));if(c.threshold!=null)parts.push('阈值 '+esc(c.threshold));}
    return parts.join(' · ');
  }
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
