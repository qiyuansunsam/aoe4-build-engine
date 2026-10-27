// Simplified Chinese localisation crawl. Loads every route and the key detail views in zh mode, lists
// visible text (and title/placeholder/aria-label values) that still contains Latin letters, sorted into
// "remaining" and "allowed" (player names, brand, untranslated 17.0 preview names, ids, numbers, units),
// and takes one screenshot per view into site/shots/i18n-<view>.png. Then checks English mode: it is the
// default even for a zh-CN browser, shows no Chinese outside the language switch, and a zh -> en switch
// restores the English page text exactly. Writes site/shots/i18n-report.json.
// Needs the server on 127.0.0.1:8765 and a fresh build (python -X utf8 site/build.py).
// Usage: node site/verify-i18n.cjs [--views name,name] [--no-shots]
const {chromium}=require('C:/Users/Sam/projects/codex-setup/browser-tools/node_modules/playwright');
const fs=require('node:fs'),path=require('node:path');
const BASE='http://127.0.0.1:8765/';
const args=process.argv.slice(2),only=args.includes('--views')?(args[args.indexOf('--views')+1]||'').split(',').filter(Boolean):[],shots=!args.includes('--no-shots');
const shotDir=path.join(__dirname,'shots');fs.mkdirSync(shotDir,{recursive:true});

const settle=async p=>{await p.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));};
const go=async(p,hash)=>{await p.evaluate(h=>{if(location.hash===h)window.dispatchEvent(new HashChangeEvent('hashchange'));else location.hash=h;},hash);await settle(p);};
const track=key=>async p=>{await go(p,'#workspace');await p.evaluate(()=>{state.time=960;});await go(p,'#workspace');await p.locator(`[data-track-row="${key}"][data-path="0"]`).click();await p.locator('.slot-strip').hover();await settle(p);await p.locator('#object-detail').scrollIntoViewIfNeeded();};
const VIEWS=[
 {name:'workspace',run:p=>go(p,'#workspace')},
 {name:'workspace-villagers',run:track('villagers'),scope:'#object-detail'},
 {name:'workspace-income',run:track('income'),scope:'#object-detail'},
 {name:'workspace-bank',run:async p=>{await track('income')(p);await p.evaluate(()=>selectObject('metric','bank',0));await settle(p);},scope:'#object-detail'},
 {name:'workspace-gathered',run:track('gathered'),scope:'#object-detail'},
 {name:'workspace-spent',run:track('spent'),scope:'#object-detail'},
 {name:'workspace-technologies',run:track('technologies'),scope:'#object-detail'},
 {name:'workspace-army',run:track('army'),scope:'#object-detail'},
 {name:'workspace-unit',run:async p=>{await track('army')(p);await p.evaluate(()=>selectObject('unit','camel',0));await settle(p);},scope:'#object-detail'},
 {name:'workspace-observed',run:async p=>{await go(p,'#workspace');await p.evaluate(async()=>{await applyBuild('observed:'+BUILD_LIBRARY.builds[0].id,1);state.time=1200;});await go(p,'#workspace');await p.evaluate(()=>selectObject('metric','army',1));await settle(p);}},
 {name:'workspace-observed-units',run:async p=>{await p.evaluate(()=>{detailMode='units';selection=null;drawDetail();});await settle(p);await p.locator('#object-detail').scrollIntoViewIfNeeded();},scope:'#object-detail'},
 {name:'workspace-menus',run:async p=>{await go(p,'#workspace');await p.evaluate(()=>{document.querySelectorAll('#page details').forEach(d=>{if(!d.classList.contains('graph-event-cluster'))d.open=true;});const c=document.querySelector('#overview-chart .graph-event-cluster');if(c)c.open=true;});await settle(p);}},
 {name:'builds',run:p=>go(p,'#builds')},
 {name:'build-context-menu',run:async p=>{await go(p,'#builds');await p.locator('.build-item').first().click({button:'right'});await settle(p);}},
 {name:'build-comments',run:async p=>{await go(p,'#builds');await p.locator('.build-item').first().click({button:'right'});await p.locator('.object-context-menu [role=menuitem]').nth(1).click();await settle(p);}},
 {name:'build-page',run:async p=>{const id=await p.evaluate(()=>BUILD_LIBRARY.builds[0].id);await go(p,'#builds/'+encodeURIComponent(id));await p.waitForTimeout(400);await settle(p);}},
 {name:'build-page-theory',run:async p=>{await go(p,'#builds/culture');await settle(p);}},
 {name:'games',run:async p=>{await go(p,'#games');await p.locator('#game-search').waitFor();}},
 {name:'games-player',run:async p=>{await go(p,'#games');await p.locator('[data-player-search]').first().click();await p.waitForTimeout(300);await settle(p);}},
 {name:'game-detail',run:async p=>{await go(p,'#games');if(await p.locator('#remove-player-tag').count())await p.locator('#remove-player-tag').click();await p.locator('#game-search').fill('254499081');await p.locator('.match-open').first().click();await p.locator('[data-craft-game]').first().waitFor({timeout:15000}).catch(()=>{});await p.locator('#summary-chart,.summary-retry,.match-summary-order').first().waitFor({timeout:20000}).catch(()=>{});await settle(p);}},
 {name:'library',run:p=>go(p,'#database')},
 {name:'library-current',run:async p=>{await go(p,'#database');await p.locator('[data-catalog-patch="current"]').first().click();await settle(p);await p.evaluate(()=>{dbKind='units';dbCiv='mongols';renderDatabase();enhanceSelects();});await settle(p);}},
 {name:'library-civ',run:async p=>{await go(p,'#database');await p.evaluate(()=>{dbKind='civilizations';dbCiv='';renderDatabase();enhanceSelects();});await settle(p);await p.locator('[data-civ-open="abbasid"]').click();await settle(p);}},
 {name:'library-buildings',run:async p=>{await go(p,'#database');await p.evaluate(()=>{dbKind='buildings';dbCiv='english';renderDatabase();enhanceSelects();});await settle(p);}},
 {name:'library-technologies',run:async p=>{await go(p,'#database');await p.evaluate(()=>{dbKind='technologies';dbCiv='french';renderDatabase();enhanceSelects();});await settle(p);}},
 {name:'library-unit',run:p=>go(p,'#database/unit_archer_2_abb')},
 {name:'library-technology',run:async p=>{const id=await p.evaluate(()=>GAME_CATALOG.technologies.find(t=>/wheelbarrow/.test(t.id)&&t.civilization!=='vikings'&&t.civilization!=='scots').id);await go(p,'#database/'+id);}},
 {name:'library-building',run:p=>go(p,'#database/building_town_center_abb')},
 {name:'library-preview-unit',run:async p=>{const id=await p.evaluate(()=>GAME_CATALOG.units.find(u=>u.civilization==='vikings'&&/spearman/.test(u.id))?.id||GAME_CATALOG.units.find(u=>u.civilization==='vikings').id);await go(p,'#database/'+id);}},
 {name:'crafter',run:p=>go(p,'#ai')},
 {name:'guide',run:p=>go(p,'#model')},
].filter(v=>!only.length||only.includes(v.name));

// Runs in the page: Latin-letter text, split into remaining and allowed by reason.
function collect(scope){
 const root=scope?document.querySelector(scope)||document.body:document.body,names=new Set();
 for(const g of GAME_LIBRARY.games||[])if(g.playerName)names.add(g.playerName.trim());
 for(const m of GAME_LIBRARY.matches||[])for(const pl of m.players||[])if(pl.name)names.add(String(pl.name).trim());
 const norm=s=>String(s||'').replace(/\s+/g,' ').trim();
 const previewRecords=GAME_CATALOG.units.concat(GAME_CATALOG.buildings,GAME_CATALOG.technologies,GAME_CATALOG.civilizations).filter(r=>r.preview||['vikings','scots'].includes(r.civilization)||['vikings','scots'].includes(r.id));
 const preview=new Set(previewRecords.map(r=>r.name)),previewText=new Set(),sourceNames=new Set();
 for(const r of previewRecords){if(r.description){previewText.add(norm(r.description));for(const line of String(r.description).split('\n'))previewText.add(norm(line));}for(const f of Object.values(r.preview?.fields||{}))for(const s of (f.sources||[]).concat(f.dissent||[]))for(const w of String(s).split(/[\s();,]+/))if(/[A-Za-z]/.test(w))sourceNames.add(w);}
 const patchText=new Set([...(PATCH_NEXT.entries||[]),...(PATCH_NEXT.textChanges||[])].map(e=>norm(e.noteText)).filter(Boolean));
 const BRAND=/^(Mathmatically Correct|AoE IV|AoE 4|Mathmatically Correct AoE 4|AoE4 World|AoE4World|aoe4world(\.com)?|VS Code|Steam|Relic|YouTube|Bilibili|jeandogaming(\.com)?|Fluffy|Codex|Claude|AI|APM|ID|UTC|MODEL\.md|PARAMS\.md|data\/INSTALLED_DATA\.md)$/i;
 // Latin runs left inside otherwise translated text must all be proper names, ids or versions.
 const properRun=w=>BRAND.test(w)||names.has(w)||preview.has(w)||sourceNames.has(w)||/^(?:[A-Z]{2,5}|[A-Z]\d|\d+v\d+|v?\d+(?:\.\d+)+[a-z]?|[a-z0-9]+(?:[_-][a-z0-9]+)+)$/.test(w)||w.split(/\s+/).every(x=>/^[\d.:]+$/.test(x)||BRAND.test(x)||names.has(x)||sourceNames.has(x)||preview.has(x));
 const reason=t=>{
  t=t.replace(/^[↗←→‹›]\s*|\s*[↗←→‹›]$/g,'').trim();
  if(names.has(t))return 'player name';
  if(preview.has(t))return '17.0 preview name (not in 16.3 locale)';
  if(previewText.has(t))return '17.0 preview text (not in 16.3 locale)';
  if(patchText.has(t))return 'official 17.0 patch-note quote';
  if(BRAND.test(t))return 'brand or source name';
  if(/[㐀-鿿]/.test(t)){const runs=t.match(/[A-Za-z][\w'’.\-]*(?: [A-Za-z0-9][\w'’.\-]*)*/g)||[];if(runs.every(properRun))return 'proper names inside translated text';}
  if(/^[^㐀-鿿]*$/.test(t)&&t.split(/\s*[·,;|]\s*/).every(x=>!/[A-Za-z]{2}/.test(x)||properRun(x)||names.has(x)))return 'names, sources or ids';
  if(/^(https?:\/\/|www\.)|\.(md|json|js|cjs|py|rgd|sga|ucs)\b|[\\/][a-z_]+[\\/]/i.test(t))return 'path, file or URL';
  if(/^[a-z0-9]+(?:[_-][a-z0-9]+)+$/i.test(t)&&/[_\d]/.test(t)||/^[0-9a-f]{12,}$/i.test(t))return 'id';
  if(/^[\d\s.,:%+\-−–×x\/()|·]*(?:s|px|v\d|k|m)?[\d\s.,:%+\-−–×x\/()|·]*$/i.test(t))return 'number or unit';
  if(/^(?:[A-Z]{2,5}|[A-Z]\d|\d+v\d+|v?\d+(?:\.\d+)+[a-z]?)$/.test(t))return 'acronym or version';
  if(/^[\w.\-]+$/.test(t)&&[...t.split(/[ ·,]+/)].every(x=>names.has(x)))return 'player name';
  return null;
 };
 const visible=el=>{for(let e=el;e&&e!==document.documentElement;e=e.parentElement){const cs=getComputedStyle(e);if(cs.display==='none'||cs.visibility==='hidden'||e.hidden)return false;}return el.getClientRects().length>0;};
 const out={remaining:{},allowed:{},hidden:{}};
 const add=(bucket,t,why)=>{const k=why?why+' :: '+t:t;bucket[k]=(bucket[k]||0)+1;};
 const tw=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
 for(let n=tw.nextNode();n;n=tw.nextNode()){
  const p=n.parentElement;if(!p||p.closest('script,style,[data-i18n-skip],textarea'))continue;
  const t=n.data.replace(/\s+/g,' ').trim();if(!/[A-Za-z]{2}/.test(t))continue;
  const why=reason(t);
  if(!visible(p)){if(!why)add(out.hidden,t);continue;}
  why?add(out.allowed,t,why):add(out.remaining,t);
 }
 for(const el of root.querySelectorAll('[title],[placeholder],[aria-label]')){
  if(el.closest('[data-i18n-skip]'))continue;
  for(const a of ['title','placeholder','aria-label']){const v=el.getAttribute(a);if(!v||!/[A-Za-z]{2}/.test(v))continue;const t=v.replace(/\s+/g,' ').trim(),why=reason(t);why?add(out.allowed,'@'+a+' '+t,why):add(out.remaining,'@'+a+' '+t);}
 }
 if(!scope&&/[A-Za-z]{2}/.test(document.title)&&!reason(document.title))add(out.remaining,'@document.title '+document.title);
 return out;
}

(async()=>{
 const browser=await chromium.launch(),report={views:{},english:{},errors:[]};
 const mock=async ctx=>{await ctx.route('**/api/players/search?*',r=>r.fulfill({json:{players:[]}}));await ctx.route('**/api/players/*/games?*',r=>r.fulfill({json:{matches:[],page:1,hasMore:false}}));};
 // zh pass
 const zh=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',locale:'en-US'});await mock(zh);
 await zh.addInitScript(()=>{try{localStorage.setItem('aoe-crafter-lang','zh');}catch{}});
 const p=await zh.newPage();p.on('pageerror',e=>report.errors.push('zh: '+e.message));
 await p.goto(BASE+'#workspace',{waitUntil:'networkidle'});
 if(await p.evaluate(()=>document.documentElement.lang)!=='zh-CN')report.errors.push('zh mode did not set <html lang="zh-CN">');
 for(const v of VIEWS){
  await p.keyboard.press('Escape');await p.evaluate(()=>document.querySelectorAll('dialog[open]').forEach(d=>d.close()));
  try{await v.run(p);}catch(err){report.errors.push(`${v.name}: ${err.message.split('\n')[0]}`);}
  const r=await p.evaluate(collect,v.scope||null);
  r.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
  report.views[v.name]=r;
  if(shots){await p.waitForTimeout(500);await p.screenshot({path:path.join(shotDir,`i18n-${v.name}.png`)});}
  const remaining=Object.entries(r.remaining).sort((a,b)=>b[1]-a[1]),allowed=Object.keys(r.allowed).length,hidden=Object.keys(r.hidden).length;
  console.log(`\n[${v.name}] remaining ${remaining.length} · allowed ${allowed} · hidden-untranslated ${hidden}${r.overflow?' · HORIZONTAL OVERFLOW':''}`);
  for(const [t,c] of remaining.slice(0,60))console.log(`   ${c>1?c+'× ':''}${t.slice(0,160)}`);
  if(remaining.length>60)console.log(`   … ${remaining.length-60} more`);
 }
 // Narrow screen: the language switch sits in the compact sidebar row; no horizontal overflow.
 await p.keyboard.press('Escape');await p.setViewportSize({width:390,height:844});await go(p,'#workspace');
 report.narrow={zh:await p.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,toggle:document.getElementById('lang-toggle').getBoundingClientRect().toJSON()}))};
 if(shots){await p.waitForTimeout(600);await p.screenshot({path:path.join(shotDir,'i18n-narrow-workspace.png')});}
 await p.setViewportSize({width:1440,height:1000});
 // Library render cost in each language
 const timeLibrary=page=>page.evaluate(async()=>{dbKind='units';dbCiv='';dbQuery='';dbDetail=null;const t0=performance.now();renderDatabase();enhanceSelects();await Promise.resolve();await new Promise(r=>setTimeout(r));return Math.round(performance.now()-t0);});
 await go(p,'#database');report.libraryRenderMs={zh:await timeLibrary(p)};
 // zh -> en restore
 const textOf=page=>page.evaluate(()=>document.querySelector('#page').innerText+'\n'+document.querySelector('.sidebar').innerText);
 await zh.close();
 const en=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',locale:'zh-CN'});await mock(en);
 const q=await en.newPage();q.on('pageerror',e=>report.errors.push('en: '+e.message));
 await q.goto(BASE+'#workspace',{waitUntil:'networkidle'});
 report.english.defaultLang=await q.evaluate(()=>document.documentElement.lang);
 report.english.navigatorLanguage=await q.evaluate(()=>navigator.language);
 report.english.toggle=await q.evaluate(()=>{const b=document.getElementById('lang-toggle');return {tag:b?.tagName,text:b?.textContent,aria:b?.getAttribute('aria-label')};});
 report.libraryRenderMs.en=await (async()=>{await go(q,'#database');return timeLibrary(q);})();
 const cjk=/[\u3400-\u9fff]/;
 report.english.leaks={};report.english.restore={};report.english.overflow={};
 for(const v of VIEWS){
  await q.keyboard.press('Escape');await q.evaluate(()=>document.querySelectorAll('dialog[open]').forEach(d=>d.close()));
  try{await v.run(q);}catch(err){report.errors.push(`en ${v.name}: ${err.message.split('\n')[0]}`);continue;}
  // A leak is Chinese text that is one of our translations (the English app itself shows some Chinese:
  // player names, video-source names and a fullwidth "＋" glyph).
  const leaks=await q.evaluate(re=>{const z=window.I18N_ZH||{},ours=new Set([z.game?.terms,z.game?.text,z.ui?.strings,z.ui?.data,z.ui?.overrides].flatMap(o=>Object.values(o||{})).map(v=>String(v).replace(/\s+/g,' ').trim()));const hit=s=>{s=String(s).replace(/\s+/g,' ').trim();return new RegExp(re).test(s)&&(ours.has(s)||/[㐀-鿿]{2,}/.test(s)&&[...ours].some(v=>v.length>3&&s.includes(v)));};const out=[],tw=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);for(let n=tw.nextNode();n;n=tw.nextNode()){if(n.parentElement?.closest('#lang-toggle,script,style'))continue;if(hit(n.data))out.push(n.data.trim());}for(const el of document.querySelectorAll('[title],[aria-label],[placeholder]')){if(el.id==='lang-toggle')continue;for(const a of ['title','aria-label','placeholder']){const x=el.getAttribute(a);if(x&&hit(x))out.push('@'+a+' '+x);}}return out.concat(document.documentElement.lang!=='en'?['<html lang='+document.documentElement.lang+'>']:[]);},cjk.source);
  if(leaks.length)report.english.leaks[v.name]=leaks.slice(0,20);
  report.english.overflow[v.name]=await q.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);
 }
 // switch to zh and back on a few views; English text must come back exactly
 for(const v of VIEWS.filter(v=>['workspace','library','library-unit','games','guide','build-page'].includes(v.name))){
  await v.run(q);const before=await textOf(q);
  await q.locator('#lang-toggle').click();await settle(q);const zhText=await textOf(q);
  await q.locator('#lang-toggle').click();await settle(q);await v.run(q);const after=await textOf(q);
  report.english.restore[v.name]={same:before===after,zhDiffers:zhText!==before};
  if(before!==after){const a=before.split('\n'),b=after.split('\n');report.english.restore[v.name].firstDiff=a.findIndex((x,i)=>x!==b[i]);report.english.restore[v.name].sample=[a.find((x,i)=>x!==b[i]),b.find((x,i)=>x!==a[i])];}
 }
 if(shots){await go(q,'#workspace');await q.waitForTimeout(600);await q.screenshot({path:path.join(shotDir,'i18n-english-workspace.png')});}
 report.english.savedAfterToggle=await q.evaluate(()=>localStorage.getItem('aoe-crafter-lang'));
 await browser.close();
 fs.writeFileSync(path.join(shotDir,'i18n-report.json'),JSON.stringify(report,null,1));
 console.log('\nEnglish mode:',JSON.stringify({defaultLang:report.english.defaultLang,navigatorLanguage:report.english.navigatorLanguage,toggle:report.english.toggle,leaks:report.english.leaks,restore:report.english.restore,overflow:Object.entries(report.english.overflow).filter(([,v])=>v).map(([k])=>k)},null,1));
 console.log('Library render ms:',JSON.stringify(report.libraryRenderMs));
 console.log('Errors:',report.errors.length?report.errors:'none');
 console.log('Totals: remaining',Object.values(report.views).reduce((s,r)=>s+Object.keys(r.remaining).length,0));
})().catch(e=>{console.error(e);process.exit(1);});
