/* rail-b motion hooks (same hooks as rail-a; the expressive differences live in rail-b.css). Wraps drawMoment / drawDetail: tweens rail numbers and stat values when the
   time or a preview changes, fills progress bars, marks soft vs hard detail swaps, links rail hover to
   the chart series. Adds only classes, data attributes and text tweens; never touches state or data. */
(function(){
'use strict';
const reduce=()=>{try{return matchMedia('(prefers-reduced-motion: reduce)').matches;}catch{return false;}};
const ease=t=>1-Math.pow(1-t,3);
const parseNum=s=>{s=String(s??'');if(!/\d/.test(s))return NaN;const n=Number(s.replace(/[^\d.-]/g,''));return Number.isFinite(n)?n:NaN;};
function tween(ms,onFrame,onDone){let start=null,id=0;const step=now=>{if(start===null)start=now;const t=Math.min(1,(now-start)/ms);onFrame(ease(t),t);if(t<1)id=requestAnimationFrame(step);else if(onDone)onDone();};id=requestAnimationFrame(step);return ()=>cancelAnimationFrame(id);}

/* 1. Rail values tween to their new numbers (≤ 400 ms, cancelable, instant under reduced motion). */
const railKey=b=>{const btn=b.parentElement;return btn?btn.getAttribute('aria-label')||'':'';};
function snapshotRail(){const map=new Map();document.querySelectorAll('#inspector .track-row>b').forEach(b=>{const k=railKey(b);if(k)map.set(k,b.textContent);});return map;}
function tweenRail(before){if(!before.size)return;document.querySelectorAll('#inspector .track-row>b').forEach(b=>{const k=railKey(b),oldText=before.get(k),newText=b.textContent;if(oldText==null||oldText===newText)return;const from=parseNum(oldText),to=parseNum(newText);b.classList.add('is-changing');b.closest('.compare-track')?.classList.add('is-changing');const finish=()=>{if(!b.isConnected)return;b.textContent=newText;b.classList.remove('is-changing');b.closest('.compare-track')?.classList.remove('is-changing');};if(reduce()||!Number.isFinite(from)||!Number.isFinite(to)){setTimeout(finish,reduce()?0:400);return;}if(b._railCancel)b._railCancel();b._railCancel=tween(Math.min(400,220+Math.min(180,Math.abs(to-from)/40)),e=>{if(!b.isConnected)return;b.textContent=Math.round(from+(to-from)*e).toLocaleString();},finish);});}

/* 2. Hovering or focusing a rail value highlights its path on the chart (class-only). */
function hookRailHover(){document.querySelectorAll('#inspector .track-row').forEach(btn=>{if(btn._railHover)return;btn._railHover=true;const path=btn.dataset.path??btn.dataset.unitPath;const on=()=>{document.documentElement.dataset.railHover=path;},off=()=>{if(document.documentElement.dataset.railHover===path)delete document.documentElement.dataset.railHover;};btn.addEventListener('pointerenter',on);btn.addEventListener('focus',on);btn.addEventListener('pointerleave',off);btn.addEventListener('blur',off);});}

if(typeof drawMoment==='function'){const _prevMoment=drawMoment;drawMoment=function(){let before=new Map();try{before=snapshotRail();}catch{}const r=_prevMoment.apply(this,arguments);try{tweenRail(before);hookRailHover();}catch{}return r;};}

/* 3. Detail panel: hard swap (new object) animates in via CSS; soft swap (same object, new time or
   preview) keeps the layout still and tweens stat values and progress bars instead. */
const statKey=s=>s.dataset.stat||s.querySelector('small')?.textContent||'';
function snapshotStats(){const map=new Map();document.querySelectorAll('#object-detail .stat').forEach(s=>{const k=statKey(s),v=s.querySelector('strong');if(k&&v)map.set(k,v.textContent);});return map;}
function tweenStats(before){document.querySelectorAll('#object-detail .stat').forEach(s=>{const k=statKey(s),v=s.querySelector('strong');if(!v)return;const oldText=before.get(k),newText=v.textContent;if(oldText==null||oldText===newText)return;const from=parseNum(oldText),to=parseNum(newText);s.classList.add('is-changing');const done=()=>{if(!v.isConnected)return;v.textContent=newText;setTimeout(()=>s.classList.remove('is-changing'),260);};if(reduce()||!Number.isFinite(from)||!Number.isFinite(to)){done();return;}const decimals=(newText.split('.')[1]||'').replace(/\D/g,'').length;tween(360,e=>{if(!v.isConnected)return;v.textContent=(from+(to-from)*e).toFixed(decimals);},done);});}
function snapshotProgress(){const map=new Map();document.querySelectorAll('#object-detail progress').forEach(p=>{const k=p.getAttribute('aria-label');if(k)map.set(k,p.value);});return map;}
function fillProgress(before){if(reduce())return;document.querySelectorAll('#object-detail progress').forEach(p=>{const target=p.value,from=before.get(p.getAttribute('aria-label'))??0;if(target===from)return;p.value=from;tween(300,e=>{if(p.isConnected)p.value=from+(target-from)*e;},()=>{if(p.isConnected)p.value=target;});});}
if(typeof drawDetail==='function'){const _prevDetail=drawDetail;let lastKey=null;drawDetail=function(){let key=null,beforeStats=new Map(),beforeProgress=new Map();try{key=[typeof detailMode!=='undefined'?detailMode:'',typeof detailPath!=='undefined'?detailPath:'',typeof selection!=='undefined'&&selection?selection.type+':'+selection.name+':'+selection.path:''].join('|');beforeStats=snapshotStats();beforeProgress=snapshotProgress();}catch{}const r=_prevDetail.apply(this,arguments);try{const host=document.getElementById('object-detail');if(host){const soft=key!==null&&key===lastKey&&host.children.length>0;host.dataset.railSwap=soft?'soft':'hard';lastKey=key;if(soft)tweenStats(beforeStats);fillProgress(beforeProgress);}}catch{}return r;};}
})();
