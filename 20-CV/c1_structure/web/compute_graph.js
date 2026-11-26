/* web/compute_graph.js — 原生 Pointer Events 流程图；定义关系由调用方提供。 */
(function(){
  'use strict';
  var WIDTH=220, HEIGHT=102, PORT_Y=48;
  var SCOPES=['index','rule','frame'];
  var LABEL={index:'指标',rule:'规则',frame:'框架'};

  function Graph(canvas,callbacks){
    this.canvas=canvas;
    this.world=canvas.querySelector('.graph-world');
    this.nodesEl=canvas.querySelector('.graph-nodes');
    this.edgesEl=canvas.querySelector('.graph-edges');
    this.empty=canvas.querySelector('.graph-empty');
    this.cb=callbacks||{};
    this.defs={index:[],rule:[],frame:[]};
    this.positions={};
    this.nodeEls={};
    this.scale=1;
    this.pan={x:30,y:30};
    this.selectedEdge=null;
    this.drag=null;
    this.connect=null;
    this.bind();
  }
  Graph.prototype.key=function(scope,id){return scope+':'+id;};
  Graph.prototype.def=function(scope,id){
    return (this.defs[scope]||[]).filter(function(d){return d.id===id;})[0];
  };
  Graph.prototype.edgeKey=function(e){return e.from.scope+':'+e.from.id+'>'+e.to.scope+':'+e.to.id;};
  Graph.prototype.edges=function(){
    var out=[],self=this;
    ['rule','frame'].forEach(function(scope){
      (self.defs[scope]||[]).forEach(function(d){
        var refs=scope==='rule'?d.index_refs_json:d.rule_refs_json;
        (refs||[]).forEach(function(ref){
          var fromScope=scope==='rule'?'index':'rule';
          var id=scope==='rule'?ref.index_id:ref.rule_id;
          if(self.def(fromScope,id)) out.push({
            from:{scope:fromScope,id:id},to:{scope:scope,id:d.id},ref:ref});
        });
      });
    });
    return out;
  };
  Graph.prototype.setData=function(defs,positions){
    this.defs=defs;
    this.positions=positions||{};
    var found={};
    SCOPES.forEach(function(s){
      (defs[s]||[]).forEach(function(d,i){
        var k=s+':'+d.id;
        if(!found[k]) found[k]={scope:s,id:d.id,
          x:SCOPES.indexOf(s)*300,y:40+i*150};
      });
    });
    this.positions={};
    Object.keys(found).forEach(function(k){
      this.positions[k]=(positions||{})[k]||found[k];
    },this);
    if(this.selectedEdge&&!this.edges().some(function(e){
      return this.edgeKey(e)===this.selectedEdge;
    },this)) this.selectEdge(null);
    this.render();
  };
  Graph.prototype.render=function(){
    this.nodesEl.replaceChildren();
    this.edgesEl.replaceChildren();
    this.nodeEls={};
    var total=0,self=this;
    SCOPES.forEach(function(s){
      (self.defs[s]||[]).forEach(function(d){self.renderNode(d);total++;});
    });
    this.empty.hidden=total!==0;
    this.renderEdges();
    this.applyTransform();
  };
  Graph.prototype.renderNode=function(d){
    var self=this,k=this.key(d._scope,d.id),pos=this.positions[k];
    var el=document.createElement('div');
    el.className='graph-node scope-'+d._scope;
    el.dataset.key=k;
    el.style.left=pos.x+'px';el.style.top=pos.y+'px';
    el.innerHTML='<div class="node-top"><span class="node-scope">'+LABEL[d._scope]+'</span>'+
      '<b>'+escHtml(d.name)+'</b></div><div class="node-detail">'+escHtml(this.detail(d))+'</div>'+
      '<div class="node-actions">'+
      '<button type="button" data-act="view">查看</button><button type="button" data-act="edit">编辑</button>'+
      '<button type="button" data-act="trace"'+(d._latest?'':' disabled')+'>追溯</button>'+
      '<button type="button" data-act="run">运行</button></div>'+
      (d._scope!=='index'?'<span class="node-port input" title="输入"></span>':'')+
      (d._scope!=='frame'?'<span class="node-port output" title="拖出连线"></span>':'');
    this.nodesEl.appendChild(el);this.nodeEls[k]=el;
    el.addEventListener('pointerdown',function(e){self.nodePointer(e,d);});
    Array.prototype.forEach.call(el.querySelectorAll('[data-act]'),function(btn){
      btn.addEventListener('pointerdown',function(e){e.stopPropagation();});
      btn.addEventListener('click',function(e){
        e.stopPropagation();
        self.cb.action(d._scope,d.id,btn.dataset.act,d._latest);
      });
    });
    var out=el.querySelector('.output');
    if(out) out.addEventListener('pointerdown',function(e){self.startConnect(e,d);});
  };
  Graph.prototype.detail=function(d){
    if(d._scope==='index') return d.source_table+(d.source_column?' · '+d.source_column:'')+' · '+d._agg;
    if(d._scope==='rule') return (d.conditions_json||[]).length+' 个条件 · '+(d.combine==='all'?'全部满足':'任一满足');
    return d._combine+' · '+(d.rule_refs_json||[]).length+' 条规则';
  };
  Graph.prototype.renderEdges=function(){
    var self=this,edges=this.edges();
    edges.forEach(function(e){self.renderEdge(e);});
    if(this.connect) this.renderWire(this.connect.from,this.connect.point,true);
  };
  Graph.prototype.path=function(a,b){
    var dx=Math.max(70,Math.abs(b.x-a.x)*.45);
    return 'M '+a.x+' '+a.y+' C '+(a.x+dx)+' '+a.y+', '+(b.x-dx)+' '+b.y+', '+b.x+' '+b.y;
  };
  Graph.prototype.port=function(p){
    var pos=this.positions[this.key(p.scope,p.id)];
    return {x:pos.x+(p.scope==='frame'?0:WIDTH),y:pos.y+PORT_Y};
  };
  Graph.prototype.renderEdge=function(e){
    var self=this,path=document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d',this.path(this.port(e.from),this.port(e.to)));
    path.setAttribute('class','graph-edge'+(this.selectedEdge===this.edgeKey(e)?' selected':''));
    path.addEventListener('pointerdown',function(ev){ev.stopPropagation();self.selectEdge(self.edgeKey(e));});
    this.edgesEl.appendChild(path);
    var hit=document.createElementNS('http://www.w3.org/2000/svg','path');
    hit.setAttribute('d',path.getAttribute('d'));hit.setAttribute('class','graph-edge-hit');
    hit.addEventListener('pointerdown',function(ev){ev.stopPropagation();self.selectEdge(self.edgeKey(e));});
    this.edgesEl.appendChild(hit);
  };
  Graph.prototype.renderWire=function(from,point,preview){
    var path=document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d',this.path(this.port(from),point));
    path.setAttribute('class','graph-edge'+(preview?' preview':''));
    this.edgesEl.appendChild(path);
  };
  Graph.prototype.point=function(e){
    var r=this.canvas.getBoundingClientRect();
    return {x:(e.clientX-r.left-this.pan.x)/this.scale,
      y:(e.clientY-r.top-this.pan.y)/this.scale};
  };
  Graph.prototype.nodePointer=function(e,d){
    if(e.button!==0||e.target.closest('.node-port'))return;
    var self=this,k=this.key(d._scope,d.id),p=this.positions[k];
    this.drag={kind:'node',key:k,id:e.pointerId,start:this.point(e),x:p.x,y:p.y,moved:false};
    this.canvas.setPointerCapture(e.pointerId);
    this.selectEdge(null);
    e.preventDefault();
  };
  Graph.prototype.startConnect=function(e,d){
    this.connect={from:{scope:d._scope,id:d.id},point:this.point(e)};
    this.drag={kind:'connect',id:e.pointerId};
    this.canvas.setPointerCapture(e.pointerId);
    this.renderEdges();e.preventDefault();e.stopPropagation();
  };
  Graph.prototype.bind=function(){
    var self=this;
    this.canvas.addEventListener('pointerdown',function(e){
      if(e.button!==0||e.target.closest('.graph-node,.graph-edge-hit,.graph-edge'))return;
      self.drag={kind:'pan',id:e.pointerId,start:{x:e.clientX,y:e.clientY},x:self.pan.x,y:self.pan.y};
      self.canvas.setPointerCapture(e.pointerId);self.selectEdge(null);
    });
    this.canvas.addEventListener('pointermove',function(e){
      if(!self.drag||self.drag.id!==e.pointerId)return;
      if(self.drag.kind==='pan'){
        self.pan.x=self.drag.x+e.clientX-self.drag.start.x;
        self.pan.y=self.drag.y+e.clientY-self.drag.start.y;
        self.applyTransform();
      }else if(self.drag.kind==='node'){
        var p=self.point(e),pos=self.positions[self.drag.key];
        pos.x=Math.round(self.drag.x+p.x-self.drag.start.x);
        pos.y=Math.round(self.drag.y+p.y-self.drag.start.y);
        self.drag.moved=true;
        self.nodeEls[self.drag.key].style.left=pos.x+'px';
        self.nodeEls[self.drag.key].style.top=pos.y+'px';
        self.renderEdges();
      }else if(self.drag.kind==='connect'){
        self.connect.point=self.point(e);self.renderEdges();
      }
    });
    function up(e){
      if(!self.drag||self.drag.id!==e.pointerId)return;
      var drag=self.drag;self.drag=null;
      if(drag.kind==='connect'){
        var from=self.connect.from,hit=document.elementFromPoint(e.clientX,e.clientY);
        var target=hit&&hit.closest?hit.closest('.graph-node'):null;
        var valid=target&&self.defs;
        if(valid){
          var parts=target.dataset.key.split(':'),scope=parts[0],id=Number(parts[1]);
          valid=(from.scope==='index'&&scope==='rule')||(from.scope==='rule'&&scope==='frame');
        }
        self.connect=null;
        if(valid) self.cb.connect(from.scope,from.id,scope,id);
      }else if(drag.kind==='node'&&drag.moved&&self.cb.layout){
        self.cb.layout(self.positions);
      }
      self.renderEdges();
    }
    this.canvas.addEventListener('pointerup',up);
    this.canvas.addEventListener('pointercancel',up);
    this.canvas.addEventListener('wheel',function(e){
      e.preventDefault();var before=self.point(e);
      self.scale=Math.max(.25,Math.min(2,self.scale*(e.deltaY<0?1.1:1/1.1)));
      var after=self.point(e);
      self.pan.x+=after.x*self.scale-before.x*self.scale;
      self.pan.y+=after.y*self.scale-before.y*self.scale;
      self.applyTransform();
    },{passive:false});
    this.canvas.addEventListener('keydown',function(e){
      if((e.key==='Delete'||e.key==='Backspace')&&self.selectedEdge){
        var edge=self.edges().filter(function(x){return self.edgeKey(x)===self.selectedEdge;})[0];
        if(edge) self.cb.disconnect(edge);
        e.preventDefault();
      }
    });
    if(window.ResizeObserver){
      this.observer=new ResizeObserver(function(){self.applyTransform();});
      this.observer.observe(this.canvas);
    }
  };
  Graph.prototype.applyTransform=function(){
    this.world.style.transform='translate('+this.pan.x+'px,'+this.pan.y+'px) scale('+this.scale+')';
    var label=document.getElementById('zoom-label');
    if(label)label.textContent=Math.round(this.scale*100)+'%';
  };
  Graph.prototype.zoom=function(factor){
    var r=this.canvas.getBoundingClientRect(),cx=r.width/2,cy=r.height/2;
    var old=this.scale;this.scale=Math.max(.25,Math.min(2,old*factor));
    this.pan.x=cx-(cx-this.pan.x)*this.scale/old;
    this.pan.y=cy-(cy-this.pan.y)*this.scale/old;
    this.applyTransform();
  };
  Graph.prototype.bounds=function(){
    var ps=Object.keys(this.positions).map(function(k){return this.positions[k];},this);
    if(!ps.length)return null;
    return {x:Math.min.apply(null,ps.map(function(p){return p.x;})),
      y:Math.min.apply(null,ps.map(function(p){return p.y;})),
      right:Math.max.apply(null,ps.map(function(p){return p.x+WIDTH;})),
      bottom:Math.max.apply(null,ps.map(function(p){return p.y+HEIGHT;}))};
  };
  Graph.prototype.fit=function(){
    var b=this.bounds();if(!b)return;
    var r=this.canvas.getBoundingClientRect(),pad=50;
    this.scale=Math.max(.25,Math.min(1.5,(r.width-pad*2)/(b.right-b.x),(r.height-pad*2)/(b.bottom-b.y)));
    this.pan.x=(r.width-(b.right-b.x)*this.scale)/2-b.x*this.scale;
    this.pan.y=(r.height-(b.bottom-b.y)*this.scale)/2-b.y*this.scale;
    this.applyTransform();
  };
  Graph.prototype.autoLayout=function(){
    var self=this;
    SCOPES.forEach(function(s,i){
      (self.defs[s]||[]).forEach(function(d,j){
        self.positions[self.key(s,d.id)]={scope:s,id:d.id,x:40+i*300,y:40+j*150};
      });
    });
    this.render();this.fit();if(this.cb.layout)this.cb.layout(this.positions);
  };
  Graph.prototype.focus=function(scope,id){
    var k=this.key(scope,id),pos=this.positions[k],old=this.nodeEls[k];
    if(!pos)return;
    if(old)old.classList.remove('flash');
    this.scale=Math.max(this.scale,.8);
    var r=this.canvas.getBoundingClientRect();
    this.pan.x=r.width/2-(pos.x+WIDTH/2)*this.scale;
    this.pan.y=r.height/2-(pos.y+HEIGHT/2)*this.scale;
    this.applyTransform();
    if(old){void old.offsetWidth;old.classList.add('flash');}
  };
  Graph.prototype.selectEdge=function(key){
    this.selectedEdge=key;
    var btn=document.getElementById('edge-del');if(btn)btn.hidden=!key;
    this.renderEdges();
  };
  Graph.prototype.deleteSelected=function(){
    var self=this,edge=this.edges().filter(function(e){return self.edgeKey(e)===this.selectedEdge;},this)[0];
    if(edge)this.cb.disconnect(edge);
  };
  window.ComputeGraph=Graph;
})();
