/* web/shell.js — 列表页共用小件：转义 / 格式化 / 缩略图 /
   状态徽标 / 全屏预览。各页面自己的交互仍在各自 js 里。 */
function escHtml(s){
  return String(s==null?'':s).replace(/[&<>"]/g,function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
  });
}
function fmtSize(n){
  n=Number(n)||0;
  if(n>=1024*1024) return (n/1024/1024).toFixed(1)+' MB';
  return Math.max(1,Math.round(n/1024))+' KB';
}
function fmtTime(s){
  if(!s) return '—';
  var d=new Date(s);
  if(isNaN(d.getTime())) return String(s);
  function p(n){ return (n<10?'0':'')+n; }
  return p(d.getMonth()+1)+'-'+p(d.getDate())+' '+p(d.getHours())+':'+p(d.getMinutes());
}
function kindOf(name){
  var e=(String(name).split('.').pop()||'').toLowerCase();
  if(['png','jpg','jpeg','bmp','webp','tif','tiff'].indexOf(e)>=0) return 'image';
  if(e==='pdf') return 'pdf';
  return 'text';
}
var KIND_LABEL={image:'图片',pdf:'PDF',text:'文本'};
/* 缩略图：图片可点击放大（data-full），PDF/文本角标新窗口打开 */
function thumbHtml(name,url){
  var k=kindOf(name);
  if(k==='image')
    return '<img class="thumb" src="'+escHtml(url)+'" data-full="'+escHtml(url)+
      '" alt="'+escHtml(name)+'" title="'+escHtml(name)+'">';
  var label=(k==='pdf'?'PDF':(String(name).split('.').pop()||'FILE').toUpperCase());
  return '<a class="thumb file" href="'+escHtml(url)+'" target="_blank" title="'+
    escHtml(name)+'"><span>'+escHtml(label.slice(0,4))+'</span></a>';
}
var STATE_LABEL={
  pending:['待处理','gray'], extracting:['提取中','blue'],
  previewed:['已预览','green'], reviewed:['已校验','purple'],
  loading:['入库中','blue'], loaded:['已入库','green'],
  failed:['失败','red'], partial:['部分入库','yellow'],
  edited:['已修改','yellow'], confirmed:['已确认','green'],
  rejected:['已拒绝','red']
};
function stateBadge(st){
  var it=STATE_LABEL[st]||[st||'—','gray'];
  return '<span class="badge '+it[1]+'">'+escHtml(it[0])+'</span>';
}
/* 全屏预览：页面里放 <div class="lightbox" id="lb" hidden>… 即可复用 */
function bindLightbox(){
  var lb=document.getElementById('lb');
  if(!lb) return;
  var img=lb.querySelector('img');
  lb.addEventListener('click',function(e){
    var t=e.target.closest?e.target.closest('img.thumb'):null;
    if(t){ img.src=t.getAttribute('data-full'); lb.hidden=false; return; }
    if(e.target===lb||e.target.closest('.lbclose')){
      lb.hidden=true; img.removeAttribute('src');
    }
  });
  document.addEventListener('keydown',function(e){
    if(!lb.hidden&&e.key==='Escape'){ lb.hidden=true; img.removeAttribute('src'); }
  });
}
/* 文件产物链接（/files/<task_file_id>/…，白名单挂载，raw 不会出现） */
function fileUrl(rfId,rel){
  return '/files/'+rfId+'/'+encodeURIComponent(rel);
}
function shortName(name){
  return String(name||'');
}
/* File → base64（上传/登记共用） */
function b64(file){
  return new Promise(function(ok,no){
    var r=new FileReader();
    r.onload=function(){ok(r.result.split(',')[1]);};
    r.onerror=no;
    r.readAsDataURL(file);
  });
}
/* 入库回执/隔离抽屉（P2，tasks/staging 共用）：
   页面放 #receipt/#rctitle/#rcbody/#rcclose 即可复用。只读。 */
function closeReceiptDrawer(){
  var r=document.getElementById('receipt');
  if(r) r.hidden=true;
}
function openReceiptDrawer(taskId){
  var drawer=document.getElementById('receipt');
  if(!drawer) return;
  document.getElementById('rctitle').textContent='任务 #'+taskId+' · 入库回执';
  document.getElementById('rcbody').innerHTML='<div class="empty">加载中…</div>';
  drawer.hidden=false;
  Promise.all([
    fetch('/api/tasks/'+taskId+'/load-log').then(function(r){return r.json();}),
    fetch('/api/tasks/'+taskId+'/quarantine').then(function(r){return r.json();})
  ]).then(function(res){
    var logs=(res[0].items||[]), qs=(res[1].items||[]).filter(function(q){
      return q.stage==='load';
    });
    var html='<div class="msg" style="margin-bottom:6px">回执 '+logs.length+
      ' 条（重跑幂等：已有回执的记录跳过）</div>';
    html+=logs.length?
      '<table class="list"><thead><tr><th>task_file</th><th>记录</th><th>动作</th>'+
      '<th>目标主键</th><th>时间</th></tr></thead><tbody>'+
      logs.map(function(l){
        return '<tr><td class="mono">'+l.task_file_id+'</td>'+
          '<td class="num">'+(l.record_index+1)+'</td>'+
          '<td>'+escHtml(l.action)+'</td>'+
          '<td><code class="mono">'+escHtml(l.target_pk)+'</code></td>'+
          '<td class="num">'+fmtTime(l.loaded_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">还没有回执</div>';
    html+='<div class="msg" style="margin:12px 0 6px">隔离 '+qs.length+
      ' 条（本轮只读；重新入库会重试无回执记录）</div>';
    html+=qs.length?
      '<table class="list"><thead><tr><th>task_file</th><th>记录</th><th>原因</th>'+
      '<th>时间</th></tr></thead><tbody>'+
      qs.map(function(q){
        return '<tr><td class="mono">'+q.task_file_id+'</td>'+
          '<td class="num">'+(q.record_index+1)+'</td>'+
          '<td>'+escHtml(q.reason)+'</td>'+
          '<td class="num">'+fmtTime(q.created_at)+'</td></tr>';
      }).join('')+'</tbody></table>':
      '<div class="empty">无隔离记录</div>';
    document.getElementById('rcbody').innerHTML=html;
  }).catch(function(){
    document.getElementById('rcbody').innerHTML=
      '<div class="empty">读取失败：平台库不可用</div>';
  });
}
/* ---- 列表分页共用组件（资料/任务/模板/校验台账/入库，规约：每页 20，
   不足一页自动隐藏；翻页后滚回列表顶部；筛选变化由各页自行回第 1 页）。
   markup 约定：
     <div class="pager" id="…" hidden><span class="pginfo"></span>
       <button type="button" class="pgprev">上一页</button>
       <button type="button" class="pgnext">下一页</button></div>
   用法：var pg=bindPager(el,function(d){page+=d;render();});
        pg.render(pageSlice(list,page))  // 前端分页
        pg.render({page:p,pages:ps,total:total})  // 服务端分页（资料页） */
var LIST_PER=20;
function pageSlice(list,page){
  var pages=Math.max(1,Math.ceil(list.length/LIST_PER));
  var p=Math.min(Math.max(1,page||1),pages);
  return {rows:list.slice((p-1)*LIST_PER,p*LIST_PER),page:p,pages:pages,total:list.length};
}
function bindPager(el,onGo){
  var prev=el.querySelector('.pgprev'),next=el.querySelector('.pgnext');
  function go(d){
    onGo(d);
    if(el.parentNode) el.parentNode.scrollIntoView({behavior:'smooth',block:'start'});
  }
  prev.onclick=function(){ if(!prev.disabled) go(-1); };
  next.onclick=function(){ if(!next.disabled) go(1); };
  return {render:function(info){
    el.hidden=info.total<=LIST_PER;
    el.querySelector('.pginfo').textContent=
      '共 '+info.total+' 条 · 第 '+info.page+'/'+info.pages+' 页';
    prev.disabled=info.page<=1;
    next.disabled=info.page>=info.pages;
  }};
}
(function(){
  var r=document.getElementById('receipt');
  if(!r) return;
  var c=document.getElementById('rcclose');
  if(c) c.onclick=closeReceiptDrawer;
  r.addEventListener('click',function(e){ if(e.target===r) closeReceiptDrawer(); });
  document.addEventListener('keydown',function(e){
    if(e.key==='Escape') closeReceiptDrawer();
  });
})();
/* P2c 入库目标抽屉（tasks/staging 共用）：未绑定任务入库时选数据源＋映射。
    markup 动态注入；映射按 数据源×任务模板 双过滤；门禁计数可见预期；
   服务端校验/门禁/预检全过才登记目标并写入，失败内联显示且不登记（可另选）。
   选择内存保留：门禁失败修完校验重开不必重选。 */
var ltCtx=null, ltAll={ds:[],maps:[]}, ltKeep={ds:'',lt:''};
function closeLoadTargetDrawer(){
  var d=document.getElementById('ltdrawer');
  if(d) d.hidden=true;
}
function ltGateText(c){
  c=c||{};
  var blocked=(c.pending||0)+(c.edited||0)+(c.rejected||0);
  return blocked?
    ('门禁：待校验 '+c.pending+' · 已修改未确认 '+c.edited+' · 已拒绝 '+c.rejected+
     ' · 已确认 '+(c.confirmed||0)+'（须全部确认）'):
    ('门禁通过：全部 '+(c.confirmed||0)+' 条已确认，可入库');
}
function ltRefreshMaps(){
  var dsSel=document.getElementById('ltds'), mapSel=document.getElementById('ltmap');
  var go=document.getElementById('ltgo');
  var list=ltAll.maps.filter(function(m){
    return String(m.template_id)===String(ltCtx.templateId)&&
           String(m.datasource_id)===String(dsSel.value);
  });
  mapSel.innerHTML=list.length?list.map(function(m){
    return '<option value="'+m.id+'">'+escHtml(m.target_table+' · '+m.write_mode)+'</option>';
  }).join(''):'<option value="">无匹配映射（到入库页新建）</option>';
  if(ltKeep.lt&&list.some(function(m){return String(m.id)===ltKeep.lt;}))
    mapSel.value=ltKeep.lt;
  ltKeep.lt=mapSel.value;
  go.disabled=!mapSel.value;
}
function openLoadTargetDrawer(taskId,templateId,onDone){
  ltCtx={taskId:taskId,templateId:templateId,onDone:onDone};
  var d=document.getElementById('ltdrawer');
  if(!d){
    d=document.createElement('div');
    d.className='drawer'; d.id='ltdrawer';
    d.innerHTML='<div class="dpanel">'+
      '<div class="dhead"><h2 id="lttitle">选择入库目标</h2><span class="spacer"></span>'+
      '<button type="button" class="dclose" id="ltclose">关闭 (Esc)</button></div>'+
      '<div class="dbody">'+
      '<div class="banner err" id="lterr" hidden></div>'+
      '<div class="ltrow"><label for="ltds">数据源</label><select id="ltds"></select></div>'+
      '<div class="ltrow"><label for="ltmap">映射</label><select id="ltmap"></select></div>'+
      '<div class="msg" id="ltgate" style="margin-top:8px"></div>'+
      '<div class="msg" style="margin-top:6px">映射＝数据源×表×模板的绑定，在 '+
      '<a href="/load" target="_blank">入库页</a> 管理。校验/门禁/预检全过才登记目标并写入；'+
      '未通过不登记，下次可另选。</div>'+
      '</div>'+
      '<div class="dfoot"><span class="spacer" style="flex:1"></span>'+
      '<button type="button" class="btn" id="ltgo">入库</button></div>'+
      '</div>';
    document.body.appendChild(d);
    document.getElementById('ltclose').onclick=closeLoadTargetDrawer;
    d.addEventListener('click',function(e){ if(e.target===d) closeLoadTargetDrawer(); });
    document.addEventListener('keydown',function(e){
      if(e.key==='Escape') closeLoadTargetDrawer();
    });
    document.getElementById('ltds').onchange=function(){
      ltKeep.ds=this.value; ltRefreshMaps();
    };
    document.getElementById('ltmap').onchange=function(){ ltKeep.lt=this.value; };
    document.getElementById('ltgo').onclick=function(){
      var btn=this, err=document.getElementById('lterr');
      var dsSel=document.getElementById('ltds'), mapSel=document.getElementById('ltmap');
      if(!dsSel.value||!mapSel.value) return;
      btn.disabled=true; err.hidden=true;
      fetch('/api/tasks/'+ltCtx.taskId+'/load',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({load_datasource_id:Number(dsSel.value),
                             load_table_id:Number(mapSel.value)})
      }).then(function(r){
        return r.json().catch(function(){return {};}).then(function(j){
          return {s:r.status,j:j};
        });
      }).then(function(o){
        btn.disabled=false;
        if(!o.j.ok){
          err.textContent='不能入库：'+(o.j.error||('HTTP '+o.s));
          err.hidden=false; return;
        }
        closeLoadTargetDrawer();
        if(ltCtx.onDone) ltCtx.onDone();
      }).catch(function(){
        btn.disabled=false;
        err.textContent='入库请求失败：平台库不可用'; err.hidden=false;
      });
    };
  }
  document.getElementById('lttitle').textContent='任务 #'+taskId+' · 选择入库目标';
  document.getElementById('lterr').hidden=true;
  document.getElementById('ltgate').textContent='加载数据源与门禁计数…';
  document.getElementById('ltgo').disabled=true;
  d.hidden=false;
  Promise.all([
    fetch('/api/load/datasources').then(function(r){return r.json();}),
    fetch('/api/load/tables').then(function(r){return r.json();}),
    fetch('/api/tasks/'+taskId+'/gate').then(function(r){return r.json();})
  ]).then(function(res){
    if(!ltCtx||ltCtx.taskId!==taskId) return;
    ltAll.ds=res[0].items||[]; ltAll.maps=res[1].items||[];
    var dsSel=document.getElementById('ltds');
    dsSel.innerHTML=ltAll.ds.length?ltAll.ds.map(function(x){
      return '<option value="'+x.id+'">'+escHtml(x.name+' · '+x.host+'/'+x.db_name)+'</option>';
    }).join(''):'<option value="">暂无数据源（到入库页新建）</option>';
    if(ltKeep.ds&&ltAll.ds.some(function(x){return String(x.id)===ltKeep.ds;}))
      dsSel.value=ltKeep.ds;
    ltKeep.ds=dsSel.value;
    document.getElementById('ltgate').textContent=ltGateText(res[2]);
    ltRefreshMaps();
  }).catch(function(){
    document.getElementById('ltgate').textContent='';
    var err=document.getElementById('lterr');
    err.textContent='读取失败：平台库不可用'; err.hidden=false;
  });
}