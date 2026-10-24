/* shell-a motion hooks: sliding sidebar indicator + orchestrated page reveal on route change.
   Adds classes/attributes only; never touches state or data. Every hook is guarded. */
(function(){
  'use strict';
  var VARIANT='a';
  var lastReveal=0;
  try{document.documentElement.dataset.shellVariant=VARIANT;}catch(e){}

  function ensureIndicator(){
    var nav=document.querySelector('.sidebar nav');if(!nav)return null;
    var ind=nav.querySelector('.nav-indicator');
    if(!ind){ind=document.createElement('span');ind.className='nav-indicator';ind.setAttribute('aria-hidden','true');nav.prepend(ind);nav.classList.add('has-indicator');}
    return ind;
  }
  function moveIndicator(){
    try{
      var nav=document.querySelector('.sidebar nav'),ind=ensureIndicator();if(!ind)return;
      var a=nav.querySelector('a[aria-current=page]');
      if(!a){ind.style.opacity='0';return;}
      var nr=nav.getBoundingClientRect(),r=a.getBoundingClientRect();
      ind.style.width=r.width+'px';ind.style.height=r.height+'px';
      ind.style.transform='translate('+(r.left-nr.left+nav.scrollLeft)+'px,'+(r.top-nr.top+nav.scrollTop)+'px)';
      ind.style.opacity='1';
      if(!ind.classList.contains('live')){ind.getBoundingClientRect();requestAnimationFrame(function(){ind.classList.add('live');});}
      if(VARIANT==='b'){a.classList.remove('nav-pop');void a.offsetWidth;a.classList.add('nav-pop');setTimeout(function(){a.classList.remove('nav-pop');},400);}
    }catch(e){}
  }
  function reveal(){
    try{
      var now=Date.now();if(now-lastReveal<60)return;lastReveal=now;
      var page=document.getElementById('page');if(!page)return;
      var i=0;
      Array.prototype.forEach.call(page.children,function(el){
        if(el.classList.contains('sr-only')||el.classList.contains('workspace-actions'))return;
        el.classList.remove('shell-reveal');
        el.style.setProperty('--i',String(Math.min(i++,6)));
        el.classList.add('shell-reveal');
        var done=function(ev){if(ev&&ev.target!==el)return;el.classList.remove('shell-reveal');el.style.removeProperty('--i');el.removeEventListener('animationend',done);};
        el.addEventListener('animationend',done);
        setTimeout(done,900);
      });
    }catch(e){}
  }
  function afterRoute(){moveIndicator();reveal();}

  try{
    if(typeof navigate==='function'){
      var _prevNavigate=navigate;
      navigate=function(){var r=_prevNavigate.apply(this,arguments);try{afterRoute();}catch(e){}return r;};
    }
  }catch(e){}
  try{window.addEventListener('hashchange',function(){afterRoute();});}catch(e){}
  try{var rs;window.addEventListener('resize',function(){clearTimeout(rs);rs=setTimeout(moveIndicator,120);});}catch(e){}
  try{if(document.fonts&&document.fonts.ready)document.fonts.ready.then(moveIndicator);}catch(e){}
  try{if(document.querySelector('.sidebar nav a[aria-current=page]'))afterRoute();}catch(e){}
})();
