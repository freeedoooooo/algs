/* web/compute_graph.js — 原生 Pointer Events 流程图；定义关系由调用方提供。 */
(function(){
  'use strict';
  var SCOPES=['document','source','index','rule','frame'];
  var SVG_NS='http://www.w3.org/2000/svg',graphSeq=0;
  var LABEL={document:'文档',source:'数据',index:'指标',rule:'规则',frame:'框架'};
  var SCOPE_ICON={
    document:'<path d="M4 1.5h5l3 3v10H4zM9 1.5v3h3M6 8h4M6 10.5h4"/>',
    source:'<ellipse cx="8" cy="3.5" rx="5.5" ry="2.2"/><path d="M2.5 3.5v4c0 1.2 2.5 2.2 5.5 2.2s5.5-1 5.5-2.2v-4M2.5 7.5v4c0 1.2 2.5 2.2 5.5 2.2s5.5-1 5.5-2.2v-4"/>',
    index:'<path d="M2 13V8M6 13V3M10 13V6M14 13V1"/>',
    rule:'<path d="M3 2h10M3 8h10M3 14h10"/><circle cx="6" cy="2" r="1.5" fill="currentColor" stroke="none"/><circle cx="10" cy="8" r="1.5" fill="currentColor" stroke="none"/><circle cx="6" cy="14" r="1.5" fill="currentColor" stroke="none"/>',
    frame:'<path d="m8 2 6 3-6 3-6-3 6-3ZM2 8l6 3 6-3M2 12l6 3 6-3"/>'
  };
  window.ComputeScopeIcon=function(scope,className){
    return '<svg class="'+(className||'scope-icon')+'" viewBox="0 0 16 16" aria-hidden="true">'+
      (SCOPE_ICON[scope]||SCOPE_ICON.index)+'</svg>';
  };

  function Graph(canvas,callbacks,options){
    this.canvas=canvas;
    this.world=canvas.querySelector('.graph-world');
    this.nodesEl=canvas.querySelector('.graph-nodes');
    this.edgesEl=canvas.querySelector('.graph-edges');
    this.empty=canvas.querySelector('.graph-empty');
    this.cb=callbacks||{};
    this.options=options||{};
    this.compact=!!this.options.compact;
    this.arrowId='compute-arrow-'+(++graphSeq);
    this.defs={document:[],source:[],index:[],rule:[],frame:[]};
    this.positions={};
    this.nodeEls={};
    this.scale=1;
    this.pan={x:30,y:30};
    this.selectedEdge=null;
    this.selectedNode=null;
    this.initialized=false;
    this.drag=null;
    this.clickTimer=null;
    this.lastClick=null;
    this.connect=null;
    this.bind();
  }
  Graph.prototype.nodeW=function(){return this.compact?142:156;};
  Graph.prototype.nodeH=function(){return this.compact?42:48;};
  Graph.prototype.key=function(scope,id){return scope+':'+id;};
  Graph.prototype.def=function(scope,id){
    return (this.defs[scope]||[]).filter(function(d){return d.id===id;})[0];
  };
  Graph.prototype.edgeKey=function(e){return e.from.scope+':'+e.from.id+'>'+e.to.scope+':'+e.to.id;};
  Graph.prototype.edges=function(){
    var out=[],self=this,seen={};
    function add(from,to,ref){
      var key=from.scope+':'+from.id+'>'+to.scope+':'+to.id;
      if(seen[key]||!self.def(from.scope,from.id)||!self.def(to.scope,to.id))return;
      seen[key]=true;out.push({from:from,to:to,ref:ref});
    }
    (this.defs.document||[]).forEach(function(d){
      (d.source_ids||[]).forEach(function(id){add({scope:'document',id:d.id},{scope:'source',id:id},d);});
    });
    (this.defs.source||[]).forEach(function(d){
      (d.index_ids||[]).forEach(function(id){add({scope:'source',id:d.id},{scope:'index',id:id},d);});
    });
    ['rule','frame'].forEach(function(scope){
      (self.defs[scope]||[]).forEach(function(d){
        var refs=scope==='rule'?d.index_refs_json:d.rule_refs_json;
        (refs||[]).forEach(function(ref){
          var fromScope=scope==='rule'?'index':'rule';
          var id=scope==='rule'?ref.index_id:ref.rule_id;
          add({scope:fromScope,id:id},{scope:scope,id:d.id},ref);
        });
      });
    });
    return out;
  };
  Graph.prototype.setData=function(defs,positions){
    this.defs=defs;this.positions=positions||{};
    var found={},gapX=this.compact?176:208,gapY=this.compact?62:82;
    SCOPES.forEach(function(s){
      (defs[s]||[]).forEach(function(d,i){
        var k=s+':'+d.id;
        if(!found[k])found[k]={scope:s,id:d.id,x:SCOPES.indexOf(s)*gapX,y:30+i*gapY};
      });
    });
    (defs.source||[]).forEach(function(d){
      var target=(positions||{})['index:'+(d.index_ids||[])[0]]||found['index:'+(d.index_ids||[])[0]];
      if(target)found['source:'+d.id]={scope:'source',id:d.id,x:target.x-gapX,y:target.y};
    });
    var documentSlots={};
    (defs.document||[]).forEach(function(d){
      var sourceId=(d.source_ids||[])[0],source=found['source:'+sourceId];if(!source)return;
      var slot=documentSlots['source:'+sourceId]||0;documentSlots['source:'+sourceId]=slot+1;
      found['document:'+d.id]={scope:'document',id:d.id,x:source.x-gapX,y:source.y+slot*gapY};
    });
    this.positions={};
    Object.keys(found).forEach(function(k){this.positions[k]=(positions||{})[k]||found[k];},this);
    if(this.selectedEdge&&!this.edges().some(function(e){return this.edgeKey(e)===this.selectedEdge;},this))this.selectEdge(null);
    if(this.selectedNode){
      var parts=this.selectedNode.split(':');
      if(!this.def(parts[0],Number(parts[1])))this.selectedNode=null;
    }
    this.render();
    if(!this.initialized){this.initialized=true;this.fit();}
  };
  Graph.prototype.render=function(){
    this.nodesEl.replaceChildren();this.edgesEl.replaceChildren();this.nodeEls={};
    var total=0,self=this;
    SCOPES.forEach(function(s){(self.defs[s]||[]).forEach(function(d){self.renderNode(d);total++;});});
    this.empty.hidden=total!==0;this.renderEdges();this.applyTransform();
  };
  Graph.prototype.renderNode=function(d){
    var self=this,k=this.key(d._scope,d.id),pos=this.positions[k],hasValue=!!d._latest,
      isSource=d._scope==='source',isDocument=d._scope==='document';
    var el=document.createElement('div');
    el.className='graph-node scope-'+d._scope+(hasValue?' has-value':'')+
      (isSource?' source-node':'')+(isDocument?' document-node':'')+
      (this.selectedNode===k?' selected':'');
    el.dataset.key=k;el.tabIndex=0;el.setAttribute('role','button');
    el.setAttribute('aria-label',LABEL[d._scope]+' '+d.name+(this.compact?'，双击查看详情':'，单击查看，双击追溯'));
    el.style.left=pos.x+'px';el.style.top=pos.y+'px';
    var h='<div class="node-name">'+window.ComputeScopeIcon(d._scope,'scope-icon node-scope-icon')+
      '<b>'+escHtml(d.name)+'</b></div>';
    if(this.compact){
      h+='<div class="node-detail" hidden>'+escHtml(this.detail(d))+'</div>'+
        '<button type="button" class="node-expand" data-tip="展开详情" aria-label="展开'+escHtml(d.name)+'详情" aria-expanded="false">⌄</button>';
    }else if(hasValue){
      h+='<div class="node-result">'+escHtml(d._value)+'</div>';
    }
    if(!this.compact){
      h+='<button type="button" class="icon-btn mini node-more" data-action-menu="compute-action-menu" '+
        'data-tip="更多操作" aria-haspopup="menu" aria-expanded="false" aria-label="'+escHtml(d.name)+'更多操作">⋯</button>';
    }
    if(!this.compact&&!isSource&&!isDocument)h+='<span class="node-port input" data-tip="上游输入"></span>';
    if(!this.compact&&d._scope!=='frame')h+='<span class="node-port output" data-tip="'+(isSource||isDocument?'来源节点':'拖动创建下游连线')+'"></span>';
    el.innerHTML=h;this.nodesEl.appendChild(el);this.nodeEls[k]=el;
    el.addEventListener('pointerdown',function(e){self.nodePointer(e,d);});
    var more=el.querySelector('.node-more');
    if(more){
      more.addEventListener('pointerdown',function(e){e.stopPropagation();});
      more.addEventListener('click',function(e){if(self.cb.menu)self.cb.menu(d._scope,d.id,d._latest,more);});
    }
    var expand=el.querySelector('.node-expand');
    if(expand)expand.addEventListener('click',function(e){
      e.stopPropagation();var detail=el.querySelector('.node-detail'),open=detail.hidden;
      detail.hidden=!open;expand.textContent=open?'⌃':'⌄';expand.setAttribute('aria-expanded',String(open));
      el.classList.toggle('expanded',open);self.renderEdges();
    });
    el.addEventListener('dblclick',function(e){
      if(e.target.closest('button,.node-port'))return;
      if(self.compact){
        if(self.cb.inspect)self.cb.inspect(d._scope,d.id);
        return;
      }
      clearTimeout(self.clickTimer);self.clickTimer=null;self.lastClick=null;
      self.selectNode(d._scope,d.id);
      if(self.cb.trace)self.cb.trace(d._scope,d.id);
    });
    el.addEventListener('keydown',function(e){
      if(e.key==='Enter'||e.key===' '){
        e.preventDefault();self.selectNode(d._scope,d.id);if(self.cb.select)self.cb.select(d._scope,d.id);
      }
    });
    var out=el.querySelector('.output');
    if(out&&!isSource&&!isDocument)out.addEventListener('pointerdown',function(e){self.startConnect(e,d);});
  };
  Graph.prototype.detail=function(d){
    if(d._scope==='document')return '资料 #'+d.id+' · '+d.row_count+' 行业务数据';
    if(d._scope==='source')return d.name+' · '+(d.index_ids||[]).length+' 个指标';
    if(d._scope==='index')return (d.table_comment||d.source_table)+(d.source_column?' · '+d.source_column:'')+' · '+d._agg;
    if(d._scope==='rule')return (d.conditions_json||[]).length+' 个条件 · '+(d.combine==='all'?'全部满足':'任一满足');
    return d._combine+' · '+(d.rule_refs_json||[]).length+' 条规则';
  };
  Graph.prototype.renderEdges=function(){
    var self=this;this.edgesEl.replaceChildren();this.renderArrow();
    this.edges().forEach(function(e){self.renderEdge(e);});
    if(this.connect)this.renderWire(this.connect.from,this.connect.point,true);
  };
  Graph.prototype.renderArrow=function(){
    var defs=document.createElementNS(SVG_NS,'defs');
    var marker=document.createElementNS(SVG_NS,'marker');
    marker.setAttribute('id',this.arrowId);
    marker.setAttribute('viewBox','0 0 8 8');
    marker.setAttribute('refX','8');marker.setAttribute('refY','4');
    marker.setAttribute('markerWidth','8');marker.setAttribute('markerHeight','8');
    marker.setAttribute('markerUnits','userSpaceOnUse');marker.setAttribute('orient','auto');
    var arrow=document.createElementNS(SVG_NS,'path');
    arrow.setAttribute('d','M 0 0 L 8 4 L 0 8 Z');
    arrow.setAttribute('fill','#7395c7');
    marker.appendChild(arrow);defs.appendChild(marker);this.edgesEl.appendChild(defs);
  };
  Graph.prototype.path=function(a,b){
    var dx=Math.max(20,Math.abs(b.x-a.x)*.42);
    return 'M '+a.x+' '+a.y+' C '+(a.x+dx)+' '+a.y+', '+(b.x-dx)+' '+b.y+', '+b.x+' '+b.y;
  };
  Graph.prototype.port=function(p,output){
    var pos=this.positions[this.key(p.scope,p.id)],h=this.nodeH();
    return {x:pos.x+(output?this.nodeW():0),y:pos.y+h/2};
  };
  Graph.prototype.renderEdge=function(e){
    var self=this,path=document.createElementNS(SVG_NS,'path');
    path.setAttribute('d',this.path(this.port(e.from,true),this.port(e.to,false)));
    path.setAttribute('marker-end','url(#'+this.arrowId+')');
    path.setAttribute('class','graph-edge'+(e.from.scope==='document'?' document-edge':e.from.scope==='source'?' source-edge':'')+
      (this.selectedEdge===this.edgeKey(e)?' selected':''));
    this.edgesEl.appendChild(path);
    if(!this.compact&&e.from.scope!=='document'&&e.from.scope!=='source'){
      path.style.pointerEvents='stroke';
      path.addEventListener('pointerdown',function(ev){ev.stopPropagation();self.selectEdge(self.edgeKey(e));});
    }
  };
  Graph.prototype.renderWire=function(from,point,preview){
    var path=document.createElementNS(SVG_NS,'path');
    path.setAttribute('d',this.path(this.port(from,true),point));path.setAttribute('class','graph-edge'+(preview?' preview':''));
    path.setAttribute('marker-end','url(#'+this.arrowId+')');
    this.edgesEl.appendChild(path);
  };
  Graph.prototype.point=function(e){
    var r=this.canvas.getBoundingClientRect();
    return {x:(e.clientX-r.left-this.pan.x)/this.scale,y:(e.clientY-r.top-this.pan.y)/this.scale};
  };
  Graph.prototype.nodePointer=function(e,d){
    if(e.button!==0||e.target.closest('.node-port,.node-more,.node-expand'))return;
    if(this.compact){
      this.selectNode(d._scope,d.id);if(this.cb.select)this.cb.select(d._scope,d.id);return;
    }
    clearTimeout(this.clickTimer);this.clickTimer=null;
    var self=this,k=this.key(d._scope,d.id),p=this.positions[k];
    this.drag={kind:'node',key:k,id:e.pointerId,start:this.point(e),
      startClient:{x:e.clientX,y:e.clientY},x:p.x,y:p.y,moved:false};
    this.canvas.setPointerCapture(e.pointerId);this.selectEdge(null);
  };
  Graph.prototype.startConnect=function(e,d){
    this.connect={from:{scope:d._scope,id:d.id},point:this.point(e)};
    this.drag={kind:'connect',id:e.pointerId};this.canvas.setPointerCapture(e.pointerId);
    this.renderEdges();e.preventDefault();e.stopPropagation();
  };
  Graph.prototype.bind=function(){
    var self=this;
    this.canvas.addEventListener('pointerdown',function(e){
      if(e.button!==0||e.target.closest('.graph-node,.graph-edge'))return;
      self.drag={kind:'pan',id:e.pointerId,start:{x:e.clientX,y:e.clientY},x:self.pan.x,y:self.pan.y};
      self.canvas.setPointerCapture(e.pointerId);self.selectEdge(null);
    });
    this.canvas.addEventListener('pointermove',function(e){
      if(!self.drag||self.drag.id!==e.pointerId)return;
      if(self.drag.kind==='pan'){
        self.pan.x=self.drag.x+e.clientX-self.drag.start.x;self.pan.y=self.drag.y+e.clientY-self.drag.start.y;self.applyTransform();
      }else if(self.drag.kind==='node'){
        if(!self.drag.moved&&Math.hypot(e.clientX-self.drag.startClient.x,
          e.clientY-self.drag.startClient.y)<4)return;
        self.drag.moved=true;
        var p=self.point(e),pos=self.positions[self.drag.key];
        pos.x=Math.round(self.drag.x+p.x-self.drag.start.x);pos.y=Math.round(self.drag.y+p.y-self.drag.start.y);
        self.nodeEls[self.drag.key].style.left=pos.x+'px';self.nodeEls[self.drag.key].style.top=pos.y+'px';self.renderEdges();
      }else if(self.drag.kind==='connect'){self.connect.point=self.point(e);self.renderEdges();}
    });
    function up(e){
      if(!self.drag||self.drag.id!==e.pointerId)return;
      var drag=self.drag;self.drag=null;
      if(drag.kind==='connect'){
        var from=self.connect.from,hit=document.elementFromPoint(e.clientX,e.clientY),target=hit&&hit.closest?hit.closest('.graph-node'):null;
        var valid=target&&self.defs;
        if(valid){var parts=target.dataset.key.split(':'),scope=parts[0],id=Number(parts[1]);valid=(from.scope==='index'&&scope==='rule')||(from.scope==='rule'&&scope==='frame');}
        self.connect=null;if(valid)self.cb.connect(from.scope,from.id,scope,id);
      }else if(drag.kind==='node'){
        if(drag.moved){
          self.lastClick=null;if(self.cb.layout)self.cb.layout(self.positions);
        }else if(e.type!=='pointercancel'){
          var parts=drag.key.split(':'),scope=parts[0],id=Number(parts[1]),now=Date.now();
          var dbl=self.lastClick&&self.lastClick.key===drag.key&&now-self.lastClick.time<260;
          clearTimeout(self.clickTimer);self.clickTimer=null;
          if(dbl){
            self.lastClick=null;self.selectNode(scope,id);
          }else{
            self.lastClick={key:drag.key,time:now};
            self.clickTimer=setTimeout(function(){
              self.clickTimer=null;self.selectNode(scope,id);if(self.cb.select)self.cb.select(scope,id);
            },280);
          }
        }else self.lastClick=null;
      }
      self.renderEdges();
    }
    this.canvas.addEventListener('pointerup',up);this.canvas.addEventListener('pointercancel',up);
    this.canvas.addEventListener('wheel',function(e){
      e.preventDefault();var before=self.point(e);self.scale=Math.max(.25,Math.min(2,self.scale*(e.deltaY<0?1.1:1/1.1)));
      var after=self.point(e);self.pan.x+=after.x*self.scale-before.x*self.scale;self.pan.y+=after.y*self.scale-before.y*self.scale;self.applyTransform();
    },{passive:false});
    this.canvas.addEventListener('keydown',function(e){
      if((e.key==='Delete'||e.key==='Backspace')&&self.selectedEdge){var edge=self.edges().filter(function(x){return self.edgeKey(x)===self.selectedEdge;})[0];if(edge)self.cb.disconnect(edge);e.preventDefault();}
    });
    if(window.ResizeObserver){this.observer=new ResizeObserver(function(){self.applyTransform();});this.observer.observe(this.canvas);}
  };
  Graph.prototype.applyTransform=function(){
    this.world.style.transform='translate('+this.pan.x+'px,'+this.pan.y+'px) scale('+this.scale+')';
    var label=document.getElementById('zoom-label');if(label)label.textContent=Math.round(this.scale*100)+'%';
  };
  Graph.prototype.zoom=function(factor){
    var r=this.canvas.getBoundingClientRect(),cx=r.width/2,cy=r.height/2,old=this.scale;
    this.scale=Math.max(.25,Math.min(2,old*factor));this.pan.x=cx-(cx-this.pan.x)*this.scale/old;this.pan.y=cy-(cy-this.pan.y)*this.scale/old;this.applyTransform();
  };
  Graph.prototype.bounds=function(){
    var ps=Object.keys(this.positions).map(function(k){return this.positions[k];},this);if(!ps.length)return null;
    return {x:Math.min.apply(null,ps.map(function(p){return p.x;})),y:Math.min.apply(null,ps.map(function(p){return p.y;})),
      right:Math.max.apply(null,ps.map(function(p){return p.x+this.nodeW();},this)),
      bottom:Math.max.apply(null,ps.map(function(p){return p.y+this.nodeH();},this))};
  };
  Graph.prototype.fit=function(){
    var b=this.bounds();if(!b)return;
    var r=this.canvas.getBoundingClientRect(),pad=r.width<500?18:34;
    this.scale=Math.max(.25,Math.min(1,(r.width-pad*2)/(b.right-b.x),(r.height-pad*2)/(b.bottom-b.y)));
    this.pan.x=(r.width-(b.right-b.x)*this.scale)/2-b.x*this.scale;this.pan.y=(r.height-(b.bottom-b.y)*this.scale)/2-b.y*this.scale;this.applyTransform();
  };
  Graph.prototype.autoLayout=function(){
    var self=this;SCOPES.forEach(function(s,i){(self.defs[s]||[]).forEach(function(d,j){
      self.positions[self.key(s,d.id)]={scope:s,id:d.id,x:30+i*(self.compact?176:208),y:30+j*(self.compact?62:82)};
    });});
    this.render();this.fit();if(!this.compact&&this.cb.layout)this.cb.layout(this.positions);
  };
  Graph.prototype.focus=function(scope,id){
    var k=this.key(scope,id),pos=this.positions[k],old=this.nodeEls[k];if(!pos)return;
    if(old)old.classList.remove('flash');this.scale=Math.max(this.scale,.8);
    var r=this.canvas.getBoundingClientRect();this.pan.x=r.width/2-(pos.x+this.nodeW()/2)*this.scale;this.pan.y=r.height/2-(pos.y+this.nodeH()/2)*this.scale;this.applyTransform();
    if(old){void old.offsetWidth;old.classList.add('flash');}
  };
  Graph.prototype.selectNode=function(scope,id){
    this.selectedNode=scope==null?null:this.key(scope,id);var self=this;
    Object.keys(this.nodeEls).forEach(function(k){self.nodeEls[k].classList.toggle('selected',k===self.selectedNode);});
  };
  Graph.prototype.selectEdge=function(key){
    this.selectedEdge=key;if(key)this.selectNode(null);var btn=document.getElementById('edge-del');if(btn)btn.hidden=!key;this.renderEdges();
  };
  Graph.prototype.deleteSelected=function(){
    var self=this,edge=this.edges().filter(function(e){return self.edgeKey(e)===self.selectedEdge;})[0];if(edge)this.cb.disconnect(edge);
  };
  window.ComputeGraph=Graph;
})();
