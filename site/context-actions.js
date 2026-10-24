/* Build-scoped local notes and contextual navigation. */
(()=>{
const storageKey='aoe-crafter-build-comments-v1';
let menu=null,returnFocus=null;
const allBuilds=()=>[...theory,...BUILD_LIBRARY.builds];
const buildById=id=>allBuilds().find(b=>b.id===id);
const slotContext=path=>{const b=buildById(state.slots[path]?.id);return b?{id:b.id,title:b.title,url:'#builds/'+encodeURIComponent(b.id),time:state.time}:null;};
function contextFor(el){
 const item=el.closest('.build-item'),link=item?.querySelector('a[href^="#builds/"]');
 if(link){const id=decodeURIComponent(link.hash.slice(8)),b=buildById(id);return b?{id,title:b.title,url:link.hash}:null;}
 const db=el.closest('a[href^="#database/"]');if(db)return {title:db.textContent.trim(),url:db.hash};
 if(route==='builds'&&buildDetail){const b=buildById(buildDetail);return b?{id:b.id,title:b.title,url:'#builds/'+encodeURIComponent(b.id),time:buildPreview?.time}:null;}
 if(route!=='workspace')return null;
 const slot=el.closest('.slot');if(slot)return slotContext(Number(slot.querySelector('[data-slot]')?.dataset.slot||0));
 const target=el.closest('[data-event-path],[data-object-path],[data-path]');
 const path=Number(target?.dataset.eventPath??target?.dataset.objectPath??target?.dataset.path??detailPath??0);
 if(el.closest('.comparison-board'))return slotContext(path===1?1:0);
 return null;
}
function closeMenu(restore=false){menu?.remove();menu=null;if(restore&&returnFocus?.isConnected)returnFocus.focus();}
function showMenu(context,x,y,trigger){
 if(!context)return;closeMenu();returnFocus=trigger;
 menu=document.createElement('div');menu.className='object-context-menu';menu.setAttribute('role','menu');menu.setAttribute('aria-label',context.title+' actions');
 const open=document.createElement('a');open.href=context.url;open.target='_blank';open.rel='noopener';open.setAttribute('role','menuitem');open.textContent='Open in new tab';open.onclick=()=>closeMenu(true);menu.append(open);
 if(context.id){const comment=document.createElement('button');comment.type='button';comment.setAttribute('role','menuitem');comment.textContent='Build comments';comment.onclick=()=>{closeMenu();showComments(context);};menu.append(comment);}
 document.body.append(menu);const rect=menu.getBoundingClientRect();menu.style.left=Math.max(8,Math.min(x,innerWidth-rect.width-8))+'px';menu.style.top=Math.max(8,Math.min(y,innerHeight-rect.height-8))+'px';
 menu.onkeydown=e=>{const items=[...menu.querySelectorAll('[role=menuitem]')],i=items.indexOf(document.activeElement);if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();items[e.key==='Home'?0:e.key==='End'?items.length-1:(i+(e.key==='ArrowDown'?1:-1)+items.length)%items.length].focus();}if(e.key==='Escape'){e.preventDefault();closeMenu(true);}if(e.key==='Tab')closeMenu();};open.focus();
}
function readComments(){try{const data=JSON.parse(localStorage.getItem(storageKey)||'{}');return data&&typeof data==='object'&&!Array.isArray(data)?data:{};}catch{return {};}}
function showComments(context){
 const dialog=document.createElement('dialog');dialog.className='build-comments-dialog';dialog.setAttribute('aria-labelledby','build-comments-title');
 dialog.innerHTML='<form method="dialog" class="comments-heading"><h2 id="build-comments-title"></h2><button aria-label="Close comments">×</button></form><p class="comments-scope"></p><div class="build-comments-list"></div><form class="comment-composer"><label for="build-comment-text">Comment</label><textarea id="build-comment-text" maxlength="4000" required placeholder="Add a build note…"></textarea><div class="comment-footer"><small>Saved in this browser</small><button class="primary" type="submit">Save comment</button></div><p class="comment-error" role="alert"></p></form>';
 dialog.querySelector('h2').textContent='Build comments';dialog.querySelector('.comments-scope').textContent=context.title;
 function render(){const list=dialog.querySelector('.build-comments-list'),notes=readComments()[context.id];list.replaceChildren();if(!Array.isArray(notes)||!notes.length){const empty=document.createElement('p');empty.className='comments-empty';empty.textContent='No comments yet';list.append(empty);return;}
 notes.forEach(note=>{const article=document.createElement('article'),meta=document.createElement('small'),text=document.createElement('p');meta.textContent=(Number.isFinite(note.time)?mm(note.time)+' · ':'')+new Date(note.created).toLocaleString();text.textContent=String(note.text||'');article.append(meta,text);list.append(article);});}
 dialog.querySelector('.comment-composer').onsubmit=e=>{e.preventDefault();const input=dialog.querySelector('textarea'),text=input.value.trim();if(!text)return;const data=readComments(),list=Array.isArray(data[context.id])?data[context.id]:[];data[context.id]=[...list,{text,time:context.time,created:new Date().toISOString()}];try{localStorage.setItem(storageKey,JSON.stringify(data));input.value='';render();announce('Comment saved for '+context.title);input.focus();}catch{dialog.querySelector('.comment-error').textContent='Could not save in this browser. Your comment is preserved.';}};
 dialog.addEventListener('close',()=>{dialog.remove();if(returnFocus?.isConnected)returnFocus.focus();});document.body.append(dialog);render();dialog.showModal();dialog.querySelector('textarea').focus();
}
const relevant='.slot,.compare-track,#object-detail,#overview-chart,.build-item,.record-toolbar,#build-overview-chart,#build-inspector,a[href^="#database/"]';
document.addEventListener('contextmenu',e=>{if(e.target.closest('input,textarea,select,[contenteditable=true],.select-options')||e.target.closest('.custom-select')&&!e.target.closest('.slot'))return;const target=e.target.closest(relevant);if(!target)return;const context=contextFor(e.target);if(!context)return;e.preventDefault();showMenu(context,e.clientX,e.clientY,e.target.closest('button,a,[tabindex]')||target);});
document.addEventListener('pointerdown',e=>{if(menu&&!menu.contains(e.target))closeMenu();});
window.addEventListener('hashchange',()=>closeMenu());
// Actions open with a normal right-click (or the context-menu key) on any clickable build object; no ⋯ buttons.
})();
