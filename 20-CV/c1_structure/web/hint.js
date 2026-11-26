/* web/hint.js — 共享「?」悬浮说明：.hint[data-tip] 悬停/聚焦显示气泡。
   事件委托，动态渲染的参数项也生效；fixed 定位 + 视口内收敛，滚动时隐藏。 */
(function(){
  var tip=document.createElement('div');
  tip.id='hinttip'; tip.hidden=true; document.body.appendChild(tip);
  function show(el){
    var t=el.getAttribute('data-tip'); if(!t) return;
    tip.textContent=t; tip.hidden=false;
    var r=el.getBoundingClientRect();
    var tw=tip.offsetWidth, th=tip.offsetHeight;
    var left=Math.max(8,Math.min(r.left, innerWidth-tw-8));
    var top=r.bottom+6;
    if(top+th>innerHeight-8) top=Math.max(8,r.top-th-6);
    tip.style.left=left+'px'; tip.style.top=top+'px';
  }
  function hide(){ tip.hidden=true; }
  document.addEventListener('mouseover',function(e){
    var el=e.target.closest?e.target.closest('[data-tip]'):null;
    if(el) show(el); else hide();
  });
  document.addEventListener('focusin',function(e){
    var el=e.target.closest?e.target.closest('[data-tip]'):null;
    if(el) show(el);
  });
  document.addEventListener('focusout',function(e){
    var el=e.target.closest?e.target.closest('[data-tip]'):null;
    if(el) hide();
  });
  window.addEventListener('scroll',hide,true);
})();