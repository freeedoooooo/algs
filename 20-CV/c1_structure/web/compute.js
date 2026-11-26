/* web/compute.js — 计算台账：指标/规则/框架 + 抽屉编辑 + 追溯 + 复核 */
(function(){
  'use strict';
  var $=function(id){return document.getElementById(id);};
  var PFX={index:'i',rule:'r',frame:'f'};
  var LABEL={index:'指标',rule:'规则',frame:'框架'};
  var current='index';
  var defs={index:[],rule:[],frame:[]};
  var editing={index:null,rule:null,frame:null};

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
    e.textContent=msg; e.hidden=false;
    setTimeout(function(){e.hidden=true;},2600);
  }
  function err(msg){say('err',msg);}
  function ok(msg){say('ok',msg);}
  function okBadge(o){
    return '<span class="badge '+(o==='pass'?'green':'red')+'">'+
      (o==='pass'?'通过':'未通过')+'</span>';
  }
  function aggLabel(a){return {sum:'求和',count:'计数',avg:'平均',min:'最小',
    max:'最大',count_distinct:'去重计数'}[a]||a;}
  function opLabel(o){return {gt:'>',gte:'≥',lt:'<',lte:'≤',eq:'=',ne:'≠',between:'介于'}[o]||o;}
  function combineLabel(c){return {weighted:'加权得分',all_pass:'全部通过',
    any_pass:'任一通过',veto:'一票否决',all:'全部满足',any:'任一满足'}[c]||c;}

  // ---------- 抽屉 ----------
  function openEl(id){
    if(typeof animDrawerOpen==='function') animDrawerOpen($(id));
    else $(id).hidden=false;
  }
  function closeEl(id){
    if(typeof animDrawerClose==='function') animDrawerClose($(id));
    else $(id).hidden=true;
  }
  $('de-close').onclick=function(){closeEl('ded');};
  $('tr-close').onclick=function(){closeEl('trace');};

  // ---------- Tab ----------
  Array.prototype.forEach.call(document.querySelectorAll('#tabs .tab'),function(t){
    t.onclick=function(){
      current=t.getAttribute('data-scope');
      Array.prototype.forEach.call(document.querySelectorAll('#tabs .tab'),function(x){
        x.classList.toggle('on',x===t);
      });
      ['index','rule','frame'].forEach(function(s){$('pane-'+s).hidden=(s!==current);});
      loadAll();
    };
  });

  // ---------- 指标表单 ----------
  function loadDatasources(){
    return api('/api/load/datasources').then(function(j){
      var sel=$('i-ds'), keep=sel.value;
      sel.innerHTML='<option value="">请选择</option>'+(j.items||[]).map(function(d){
        return '<option value="'+d.id+'">'+esc(d.name||d.db_name)+' · '+esc(d.db_name)+'</option>';
      }).join('');
      if(keep) sel.value=keep;
    });
  }
  $('i-ds').onchange=function(){
    var ds=this.value, t=$('i-table');
    t.innerHTML='<option value="">加载中…</option>';
    if(!ds){t.innerHTML='<option value="">先选业务库</option>';return;}
    api('/api/load/datasources/'+ds+'/tables').then(function(j){
      t.innerHTML='<option value="">请选择</option>'+(j.items||[]).map(function(x){
        var n=typeof x==='string'?x:x.name;
        return '<option value="'+esc(n)+'">'+esc(n)+'</option>';
      }).join('');
    }).catch(function(e){err(e.message);});
  };
  $('i-table').onchange=function(){
    var ds=$('i-ds').value, table=this.value, c=$('i-column');
    c.innerHTML='<option value="">加载中…</option>';
    if(!ds||!table){c.innerHTML='<option value="">先选业务表</option>';return;}
    api('/api/load/datasources/'+ds+'/columns?table='+encodeURIComponent(table))
      .then(function(j){
        c.innerHTML='<option value="">（留空＝统计整行）</option>'+
          (j.items||[]).map(function(x){
            return '<option value="'+esc(x.name)+'">'+esc(x.name)+' · '+esc(x.type)+'</option>';
          }).join('');
      }).catch(function(e){err(e.message);});
  };
  function addFilterRow(){
    var d=document.createElement('div'); d.className='filterrow';
    d.innerHTML='<input class="tin" placeholder="列名" data-k="c">'+
      '<select class="tin" data-k="o">'+
      '<option value="eq">=</option><option value="ne">≠</option>'+
      '<option value="gt">&gt;</option><option value="gte">≥</option>'+
      '<option value="lt">&lt;</option><option value="lte">≤</option></select>'+
      '<input class="tin" placeholder="值" data-k="v">'+
      '<button type="button" class="btn mini ghost" data-k="x">×</button>';
    d.querySelector('[data-k=x]').onclick=function(){d.parentNode.removeChild(d);};
    $('i-filters').appendChild(d);
    return d;
  }
  $('i-addfilter').onclick=addFilterRow;

  function loadIndexOptions(cb){
    return api('/api/index').then(function(j){
      defs.index=j.items||[];
      $('r-index').innerHTML='<option value="">请选择</option>'+
        defs.index.map(function(d){
          return '<option value="'+d.id+'">'+esc(d.name)+' · '+esc(aggLabel(d.aggregate))+'</option>';
        }).join('');
      if(cb)cb();
    });
  }
  function loadRuleChecks(cb){
    return api('/api/rule').then(function(j){
      defs.rule=j.items||[];
      $('f-rules').innerHTML=defs.rule.map(function(d){
        return '<label class="rc"><input type="checkbox" data-rid="'+d.id+'">'+
          ' <span class="rname">'+esc(d.name)+'</span>'+
          '<input type="number" class="tin" data-w="'+d.id+'" value="1" step="0.1" min="0" title="权重">'+
          '<label class="veto"><input type="checkbox" data-v="'+d.id+'"> 否决</label></label>';
      }).join('')||'<span class="hint">还没有规则，请先建规则</span>';
      if(cb)cb();
    });
  }

  function fillForm(scope,d){
    $('de-title').textContent=(d?'编辑':'新建')+LABEL[scope];
    ['index','rule','frame'].forEach(function(s){$('de-'+s).hidden=(s!==scope);});
    $('de-msg').textContent='';
    editing[scope]=d?d.id:null;
    if(scope==='index'){
      $('i-name').value=d?d.name:'';
      $('i-agg').value=d?d.aggregate:'sum';
      $('i-ds').value=d?d.datasource_id:'';
      $('i-ds').onchange();
      if(d){
        var tid=d.source_table, col=d.source_column, flt=d.filter_json||[];
        setTimeout(function(){
          $('i-table').value=tid;
          $('i-table').onchange();
          setTimeout(function(){
            $('i-column').value=col||'';
            $('i-filters').innerHTML='';
            flt.forEach(function(f){
              var row=addFilterRow();
              row.querySelector('[data-k=c]').value=f.column;
              row.querySelector('[data-k=o]').value=f.op;
              row.querySelector('[data-k=v]').value=f.value;
            });
          },200);
        },200);
      }else{
        $('i-table').innerHTML='<option value="">先选业务库</option>';
        $('i-column').innerHTML='<option value="">先选业务表</option>';
        $('i-filters').innerHTML=''; addFilterRow();
      }
    }else if(scope==='rule'){
      $('r-name').value=d?d.name:'';
      $('r-alias').value=d&&(d.index_refs_json||[])[0]?d.index_refs_json[0].alias:'m1';
      var c=d&&(d.conditions_json||[])[0]||{};
      $('r-op').value=c.op||'gt';
      $('r-th').value=c.threshold==null?'':(Array.isArray(c.threshold)?c.threshold.join(','):c.threshold);
      loadIndexOptions(function(){
        if(d&&(d.index_refs_json||[])[0]) $('r-index').value=d.index_refs_json[0].index_id;
      });
    }else{
      $('f-name').value=d?d.name:'';
      $('f-combine').value=d?d.combine:'weighted';
      $('f-th').value=d&&d.threshold!=null?d.threshold:'0.8';
      loadRuleChecks(function(){
        if(!d)return;
        (d.rule_refs_json||[]).forEach(function(r){
          var cb=$('f-rules').querySelector('[data-rid="'+r.rule_id+'"]');
          if(cb){cb.checked=true;
            $('f-rules').querySelector('[data-w="'+r.rule_id+'"]').value=r.weight;
            $('f-rules').querySelector('[data-v="'+r.rule_id+'"]').checked=r.veto;}
        });
      });
    }
    openEl('ded');
  }
  ['index','rule','frame'].forEach(function(scope){
    $(PFX[scope]+'-new').onclick=function(){fillForm(scope,null);};
  });

  $('de-save').onclick=function(){
    if(current==='index') saveIndex();
    else if(current==='rule') saveRule();
    else saveFrame();
  };
  function afterSave(){closeEl('ded');loadAll();ok('已保存');}
  function saveIndex(){
    var filters=[];
    Array.prototype.forEach.call($('i-filters').children,function(row){
      var c=row.querySelector('[data-k=c]').value.trim();
      if(!c)return;
      var v=row.querySelector('[data-k=v]').value.trim();
      filters.push({column:c,op:row.querySelector('[data-k=o]').value,
        value:isNaN(Number(v))?v:Number(v)});
    });
    var body={name:$('i-name').value.trim(),datasource_id:Number($('i-ds').value),
      source_table:$('i-table').value,source_column:$('i-column').value||null,
      aggregate:$('i-agg').value,filter_json:filters};
    if(editing.index) body.id=editing.index;
    post('/api/index',body).then(afterSave).catch(function(e){err(e.message);});
  }
  function saveRule(){
    var iid=Number($('r-index').value);
    if(!iid){err('请选择指标');return;}
    var th=$('r-th').value.trim(), op=$('r-op').value, threshold;
    if(op==='between'){
      var parts=th.split(',').map(function(x){return Number(x.trim());});
      if(parts.length!==2||parts.some(isNaN)){err('区间须填两个数值');return;}
      threshold=parts;
    }else{
      if(th===''){err('请填阈值');return;}
      threshold=isNaN(Number(th))?th:Number(th);
    }
    var alias=$('r-alias').value.trim()||'m1';
    var body={name:$('r-name').value.trim(),
      index_refs:[{index_id:iid,alias:alias}],
      conditions:[{alias:alias,op:op,threshold:threshold}]};
    if(editing.rule) body.id=editing.rule;
    post('/api/rule',body).then(afterSave).catch(function(e){err(e.message);});
  }
  function saveFrame(){
    var refs=[];
    Array.prototype.forEach.call($('f-rules').querySelectorAll('input[data-rid]'),function(cb){
      if(!cb.checked)return;
      var id=cb.getAttribute('data-rid');
      refs.push({rule_id:Number(id),
        weight:Number($('f-rules').querySelector('[data-w="'+id+'"]').value),
        veto:$('f-rules').querySelector('[data-v="'+id+'"]').checked});
    });
    if(!refs.length){err('请勾选至少一个规则');return;}
    var body={name:$('f-name').value.trim(),rule_refs:refs,
      combine:$('f-combine').value,threshold:Number($('f-th').value)};
    if(editing.frame) body.id=editing.frame;
    post('/api/frame',body).then(afterSave).catch(function(e){err(e.message);});
  }

  // ---------- 台账列表 ----------
  function latest(scope,defId){
    return api('/api/'+scope+'/'+defId+'/values?limit=1').then(function(j){
      return (j.items||[])[0]||null;
    });
  }
  function renderRows(scope){
    var p=PFX[scope], list=defs[scope];
    var table=$(p+'-defs'), tbody=$(p+'-rows'), empty=$(p+'-empty');
    if(!table||!tbody||!empty) return;
    if(!list.length){table.hidden=true;empty.hidden=false;return;}
    Promise.all(list.map(function(d){return latest(scope,d.id);})).then(function(vals){
      tbody.innerHTML=list.map(function(d,i){
        var v=vals[i], result='<span class="muted">尚未运行</span>';
        if(v){
          result=scope==='index'?('<b class="value">'+esc(v.value_text)+'</b>'):okBadge(v.outcome);
          if(scope==='frame'&&v.score_text) result+=' <span class="mono">'+esc(v.score_text)+'</span>';
        }
        var detail;
        if(scope==='index') detail=esc(d.source_table)+(d.source_column?' · '+esc(d.source_column):'');
        else if(scope==='rule'){
          var c=(d.conditions_json||[])[0]||{};
          detail=esc(c.alias)+' '+esc(opLabel(c.op))+' '+esc(c.threshold);
        }else detail=esc(combineLabel(d.combine))+' · '+(d.rule_refs_json||[]).length+' 条规则';
        var ops='<span class="op" data-act="run" data-id="'+d.id+'">运行</span>'+
          ' <span class="op" data-act="edit" data-id="'+d.id+'">编辑</span>'+
          ' <span class="op" data-act="del" data-id="'+d.id+'">删除</span>';
        if(v) ops+=' <span class="op" data-act="trace" data-vid="'+v.id+'">追溯</span>'+
                   ' <span class="op" data-act="replay" data-vid="'+v.id+'">复核</span>';
        return '<tr><td class="seq">'+(i+1)+'</td><td><b>'+esc(d.name)+'</b></td>'+
          '<td>'+detail+'</td><td>'+result+'</td><td class="ops">'+ops+'</td></tr>';
      }).join('');
      table.hidden=false; empty.hidden=true;
      bindOps(scope);
    }).catch(function(e){err(e.message);});
  }
  function bindOps(scope){
    Array.prototype.forEach.call($(PFX[scope]+'-rows').querySelectorAll('[data-act]'),function(el){
      el.onclick=function(){
        var act=el.getAttribute('data-act');
        var id=Number(el.getAttribute('data-id'));
        var vid=Number(el.getAttribute('data-vid'));
        if(act==='run') doRun(scope,id);
        else if(act==='edit') doEdit(scope,id);
        else if(act==='del') doDelete(scope,id);
        else if(act==='trace') openTraceView(scope,vid);
        else if(act==='replay') openReplay(scope,vid);
      };
    });
  }
  function doEdit(scope,id){
    var d=defs[scope].filter(function(x){return x.id===id;})[0];
    if(d)fillForm(scope,d);
  }
  function doDelete(scope,id){
    var d=defs[scope].filter(function(x){return x.id===id;})[0];
    if(!d||!confirm('确定删除「'+d.name+'」及其全部结果？'))return;
    api('/api/'+scope+'/'+id,{method:'DELETE'}).then(function(){
      loadAll();ok('已删除');
    }).catch(function(e){err(e.message);});
  }
  function doRun(scope,id){
    var done=function(){loadAll();ok('已计算');};
    var fail=function(e){err(e.message);};
    if(scope==='index')return post('/api/index/'+id+'/run',{}).then(done).catch(fail);
    if(scope==='rule'){
      var d=defs.rule.filter(function(x){return x.id===id;})[0];
      var ref=(d&&d.index_refs_json||[])[0];
      if(!ref){err('规则未引用指标');return;}
      return latest('index',ref.index_id).then(function(iv){
        if(!iv){err('引用的指标还没有结果，请先运行指标');return;}
        return post('/api/rule/'+id+'/run',{index_value_ids:[iv.id]}).then(done);
      }).catch(fail);
    }
    var fd=defs.frame.filter(function(x){return x.id===id;})[0];
    var refs=fd&&fd.rule_refs_json||[];
    return Promise.all(refs.map(function(r){return latest('rule',r.rule_id);}))
      .then(function(vals){
        if(vals.some(function(v){return !v;})){err('关联规则还没有结果，请先运行规则');return;}
        return post('/api/frame/'+id+'/run',
          {rule_value_ids:vals.map(function(v){return v.id;})}).then(done);
      }).catch(fail);
  }
  function loadAll(){
    return api('/api/index').then(function(j){defs.index=j.items||[];})
      .then(function(){return api('/api/rule');}).then(function(j){defs.rule=j.items||[];})
      .then(function(){return api('/api/frame');}).then(function(j){defs.frame=j.items||[];})
      .then(function(){['index','rule','frame'].forEach(renderRows);})
      .catch(function(e){err(e.message);});
  }

  // ---------- 追溯 ----------
  function openTraceView(scope,vid){
    $('tr-title').textContent='全链路追溯';
    $('tr-body').innerHTML='<div class="empty">加载中…</div>';
    openEl('trace');
    api('/api/'+scope+'/value/'+vid+'/lineage').then(function(j){
      var h='<div class="banner info">从结论向下逐级展开，直到原始单据的具体格子。点击条目查看原文。</div><div class="chain">';
      j.chain.forEach(function(c){
        h+='<div class="chain-item"><div class="ct"><span class="tag tag-'+c.scope+'">'+
          LABEL[c.scope]+'</span> '+(c.outcome?okBadge(c.outcome):'')+'</div><div class="cd">';
        if(c.scope==='index'){
          h+='结果 <b>'+esc(c.value)+'</b> · 命中 '+(c.matched_rows==null?'—':c.matched_rows)+' 行';
          if(c.rows&&c.rows.length){
            h+='<div class="anchors">';
            c.rows.slice(0,10).forEach(function(r){
              h+='<span class="anchor" data-locate="'+esc(r.locate||'')+'">第'+esc(r.record_id)+'条</span>';
            });
            if(c.rows.length>10)h+='<span class="muted">…另有 '+(c.rows.length-10)+' 条</span>';
            h+='</div>';
          }
        }else if(c.scope==='rule'){
          h+='<div class="dlist">';
          (c.detail||[]).forEach(function(d){
            h+='<div>'+esc(d.alias)+'：'+esc(d.actual)+
              ' <span class="'+(d.passed?'ok':'bad')+'">'+(d.passed?'符合':'不符合')+'</span></div>';
          });
          h+='</div>';
        }else{
          h+='综合得分 <b>'+esc(c.score==null?'—':c.score)+'</b><div class="dlist">';
          (c.detail||[]).forEach(function(d){
            h+='<div>规则 '+esc(d.rule_value_id)+'：'+esc(d.outcome)+
              ' · 贡献 '+esc(d.contribution||'—')+'</div>';
          });
          h+='</div>';
        }
        h+='</div></div>';
      });
      h+='</div>';
      if(j.source_files&&j.source_files.length){
        h+='<h3>来源单据</h3>';
        j.source_files.forEach(function(f){
          h+='<div class="srccard">'+esc(f.name)+
            ' <a href="'+esc(f.open)+'" target="_blank">查看原图 →</a></div>';
        });
      }
      $('tr-body').innerHTML=h;
      Array.prototype.forEach.call($('tr-body').querySelectorAll('[data-locate]'),function(a){
        a.onclick=function(){
          var url=a.getAttribute('data-locate');
          if(!url)return;
          api(url).then(function(o){
            window.open('/preview?embed=1&file='+o.file_id+'&index='+o.record_index,'_blank');
          }).catch(function(e){err(e.message);});
        };
      });
    }).catch(function(e){
      $('tr-body').innerHTML='<div class="banner err">'+esc(e.message)+'</div>';
    });
  }
  function openReplay(scope,vid){
    $('tr-title').textContent='结果复核';
    $('tr-body').innerHTML='<div class="empty">复核中…</div>';
    openEl('trace');
    api('/api/'+scope+'/value/'+vid+'/replay').then(function(j){
      var h='<div class="banner '+(j.consistent?'info':'err')+'">'+
        (j.consistent?'复核一致：按当前配置重算，结果与存储值相符。':
          '复核不一致：重算结果与存储值有差异，请核查配置或数据是否变化。')+'</div>';
      h+='<table class="cmp"><thead><tr><th>项目</th><th>存储值</th><th>重算值</th><th>结果</th></tr></thead><tbody>';
      Object.keys(j.checks).forEach(function(k){
        var c=j.checks[k];
        h+='<tr><td>'+esc(labelOf(k))+'</td><td><code>'+esc(String(c.stored).slice(0,90))+
          '</code></td><td><code>'+esc(String(c.recomputed).slice(0,90))+'</code></td>'+
          '<td class="'+(c.match?'ok':'bad')+'">'+(c.match?'一致':'不一致')+'</td></tr>';
      });
      h+='</tbody></table><p class="hint">'+esc(j.note||'')+'</p>';
      $('tr-body').innerHTML=h;
    }).catch(function(e){
      $('tr-body').innerHTML='<div class="banner err">'+esc(e.message)+'</div>';
    });
  }
  function labelOf(k){return {value:'计算结果',outcome:'结论',score:'得分',detail:'明细'}[k]||k;}

  loadDatasources();
  loadAll();
})();
