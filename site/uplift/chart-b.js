/* chart-b.js: motion hooks (expressive timings) for the comparison chart and the build chart. Adds classes and Web Animations only;
   never touches state, data or behaviour. Every hook is guarded. */
(function(){
'use strict';
var V={draw:700,drawEase:'cubic-bezier(.4,0,.2,1)',glide:320,pulse:10,stagger:50,fillDelay:480};
var EASE='cubic-bezier(.23,1,.32,1)';
var reduce=function(){try{return matchMedia('(prefers-reduced-motion: reduce)').matches;}catch(e){return false;}};
var num=function(v){var n=parseFloat(v);return isFinite(n)?n:null;};

function tagSvg(svg){
  if(!svg||svg.classList.contains('u-chart'))return;
  svg.classList.add('u-chart');
  svg.querySelectorAll('line').forEach(function(l){
    if(l.classList.contains('build-time-cursor')||l.getAttribute('x1')===l.getAttribute('x2'))l.classList.add('u-cursor');else l.classList.add('u-grid');
  });
  svg.querySelectorAll('text').forEach(function(t){t.classList.add(t.getAttribute('font-size')==='11'?'u-axis':'u-note');});
  svg.querySelectorAll('polygon').forEach(function(p){p.classList.add('u-fill');});
  svg.querySelectorAll('polyline').forEach(function(p){p.classList.add('u-series');});
  svg.querySelectorAll('circle').forEach(function(c){c.classList.add('u-marker');});
}

function drawIn(svg){
  var rm=reduce();
  svg.querySelectorAll('polyline.u-series').forEach(function(p,i){
    try{
      if(rm){p.animate([{opacity:0},{opacity:1}],{duration:300,fill:'backwards'});return;}
      var L=p.getTotalLength();if(!L)return;
      p.animate([{strokeDasharray:L+' '+L,strokeDashoffset:L},{strokeDasharray:L+' '+L,strokeDashoffset:0}],{duration:V.draw,delay:i*60,easing:V.drawEase,fill:'backwards'});
    }catch(e){}
  });
  svg.querySelectorAll('polygon.u-fill').forEach(function(p,i){
    try{p.animate([{opacity:0},{opacity:1}],{duration:450,delay:V.fillDelay+i*60,easing:'ease-out',fill:'backwards'});}catch(e){}
  });
  svg.querySelectorAll('.u-axis').forEach(function(t){
    try{t.animate([{opacity:0},{opacity:1}],{duration:280,easing:'ease-out',fill:'backwards'});}catch(e){}
  });
  svg.querySelectorAll('circle.u-marker').forEach(function(c){
    try{
      if(rm){c.animate([{opacity:0},{opacity:1}],{duration:200,delay:V.draw,fill:'backwards'});return;}
      c.animate([{opacity:0,transform:'scale(.4)'},{opacity:1,transform:'scale(1)'}],{duration:260,delay:V.draw-120,easing:EASE,fill:'backwards'});
    }catch(e){}
  });
}

function revealEvents(host){
  if(reduce())return;
  var items=host.querySelectorAll('.graph-events > .graph-event, .graph-events > .graph-event-cluster');
  items.forEach(function(el,i){
    try{el.animate([{opacity:0,translate:'0 5px'},{opacity:1,translate:'0 0'}],{duration:240,delay:120+Math.min(i,14)*V.stagger,easing:EASE,fill:'backwards'});}catch(e){}
  });
}

function glideCursor(line,prevX){
  if(!line)return null;
  var x=num(line.getAttribute('x1'));if(x==null)return null;
  if(prevX!=null&&Math.abs(prevX-x)>.5&&!reduce()){
    try{line.animate([{transform:'translateX('+(prevX-x)+'px)'},{transform:'translateX(0)'}],{duration:V.glide,easing:EASE});}catch(e){}
  }
  return x;
}

function glideMarker(c,prev){
  var cx=num(c.getAttribute('cx')),cy=num(c.getAttribute('cy'));
  if(cx==null||cy==null)return null;
  if(prev&&(Math.abs(prev.cx-cx)>.5||Math.abs(prev.cy-cy)>.5)){
    try{
      if(reduce()){c.animate([{opacity:.3},{opacity:1}],{duration:200});}
      else{
        c.animate([{transform:'translate('+(prev.cx-cx)+'px,'+(prev.cy-cy)+'px)'},{transform:'translate(0,0)'}],{duration:V.glide,easing:EASE});
        c.animate([{r:'5px'},{r:V.pulse+'px',offset:.45},{r:'5px'}],{duration:360,delay:V.glide-80,easing:'ease-out'});
      }
    }catch(e){}
  }
  return {cx:cx,cy:cy};
}

function tickLabel(el,text){
  if(!el)return text;
  if(text!=null&&el.textContent!==text&&!reduce()){
    try{el.animate([{opacity:.35,transform:'translateY(-3px)'},{opacity:1,transform:'none'}],{duration:160,easing:EASE});}catch(e){}
  }
  return el.textContent;
}

/* Comparison chart */
var cmp={key:null,cursorX:null,markers:{},time:null,title:null};
if(typeof drawChart==='function'){
  var _drawChart=drawChart;
  drawChart=function(){
    var before=null;
    try{before={time:document.getElementById('time-label')&&document.getElementById('time-label').textContent,title:document.getElementById('metric-title')&&document.getElementById('metric-title').textContent};}catch(e){}
    var out=_drawChart.apply(this,arguments);
    try{
      var host=document.getElementById('overview-chart');if(!host)return out;
      var svg=host.querySelector('svg');
      if(!svg){cmp.key=null;cmp.cursorX=null;cmp.markers={};return out;}
      tagSvg(svg);
      var key='';
      try{key=JSON.stringify([state.slots,(typeof previewMetric!=='undefined'&&previewMetric)||state.metric,host.clientWidth]);}catch(e){key=String(Math.random());}
      var cursor=svg.querySelector('line.u-cursor'),markers=svg.querySelectorAll('circle[data-chart-marker]');
      if(key!==cmp.key){
        cmp.key=key;drawIn(svg);revealEvents(host);
        cmp.cursorX=cursor?num(cursor.getAttribute('x1')):null;cmp.markers={};
        markers.forEach(function(c){cmp.markers[c.dataset.chartMarker]={cx:num(c.getAttribute('cx')),cy:num(c.getAttribute('cy'))};});
        var title=document.getElementById('metric-title');
        if(title&&before&&before.title!==null&&before.title!==title.textContent){try{title.animate(reduce()?[{opacity:0},{opacity:1}]:[{opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'none'}],{duration:220,easing:EASE});}catch(e){}}
      }else{
        cmp.cursorX=glideCursor(cursor,cmp.cursorX);
        var next={};
        markers.forEach(function(c){next[c.dataset.chartMarker]=glideMarker(c,cmp.markers[c.dataset.chartMarker]);});
        cmp.markers=next;
      }
    }catch(e){}
    return out;
  };
}

if(typeof drawTimeline==='function'){
  var _drawTimeline=drawTimeline;
  drawTimeline=function(){
    var prev=null;try{var el=document.getElementById('time-label');prev=el?el.textContent:null;}catch(e){}
    var out=_drawTimeline.apply(this,arguments);
    try{var label=document.getElementById('time-label');if(label&&prev!==null&&prev!==label.textContent&&!reduce())label.animate([{opacity:.35,transform:'translateY(-3px)'},{opacity:1,transform:'none'}],{duration:160,easing:EASE});}catch(e){}
    return out;
  };
}

/* One orchestrated reveal when the workspace renders */
if(typeof renderWorkspace==='function'){
  var _renderWorkspace=renderWorkspace;
  renderWorkspace=function(){
    var out=_renderWorkspace.apply(this,arguments);
    try{var pane=document.querySelector('.chart-pane');if(pane){pane.classList.add('u-enter');setTimeout(function(){try{pane.classList.remove('u-enter');}catch(e){}},900);}}catch(e){}
    return out;
  };
}

/* Build page chart */
var bld={svg:null,cursorX:null,label:null};
if(typeof drawBuildPreview==='function'){
  var _drawBuildPreview=drawBuildPreview;
  drawBuildPreview=function(){
    var prevLabel=null;try{var l=document.getElementById('build-time-label');prevLabel=l?l.textContent:null;}catch(e){}
    var out=_drawBuildPreview.apply(this,arguments);
    try{
      var label=document.getElementById('build-time-label');
      if(label&&prevLabel!==null&&prevLabel!==label.textContent&&!reduce())label.animate([{opacity:.35,transform:'translateY(-3px)'},{opacity:1,transform:'none'}],{duration:160,easing:EASE});
      var host=document.getElementById('build-overview-chart');if(!host)return out;
      var svg=host.querySelector('svg');if(!svg){bld.svg=null;bld.cursorX=null;return out;}
      var cursor=svg.querySelector('.build-time-cursor');
      if(svg!==bld.svg){bld.svg=svg;tagSvg(svg);drawIn(svg);revealEvents(host);bld.cursorX=cursor?num(cursor.getAttribute('x1')):null;}
      else bld.cursorX=glideCursor(cursor,bld.cursorX);
    }catch(e){}
    return out;
  };
}
})();
