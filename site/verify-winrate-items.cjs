const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),{pathToFileURL}=require('node:url');
const context={window:{}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'winrates.js'),'utf8')+'\n'+fs.readFileSync(path.join(__dirname,'winrates-choices.js'),'utf8'),context);
const aggregate=context.window.WinrateItems.aggregate;
const item={id:'archer',name:'Archer',civs:['english']};
const group=(extra={})=>({mode:'rm_4v4',civ:'english',ratingBand:'1400plus',games:4,wins:2,units:{games:4,wins:2,items:{archer:{uses:2,wins:1,shareSum:.6,winShareSum:.4,lossShareSum:.2,bands:[{games:1,wins:0,shareSum:.2},{games:1,wins:1,shareSum:.4}]}}},technologies:{games:4,wins:2,items:{wheelbarrow:{uses:3,wins:2}}},landmarks:{games:4,wins:2,items:{council:{uses:4,wins:2}}},...extra});
const data={schemaVersion:2,items:{units:[item],technologies:[{id:'wheelbarrow',name:'Wheelbarrow',civs:['english']}],landmarks:[{id:'council',name:'Council Hall',civs:['english']}]},groups:[group()]};
let row=aggregate(data,'units',{}).thin[0];
assert.equal(row.games,4);assert.equal(row.uses,2);assert.equal(row.rate,.5);assert.equal(row.usage,.5);
assert.ok(Math.abs(row.share-.15)<1e-10);assert.equal(row.winShare,.2);assert.equal(row.lossShare,.1);assert.equal(row.difference,.1);
const extra=group({games:1,wins:1,units:{games:1,wins:1,items:{}}});
row=aggregate({...data,groups:[group(),extra,group({civ:'french'})]},'units',{}).thin[0];
assert.equal(row.games,5);assert.ok(Math.abs(row.share-.12)<1e-10);assert.ok(Math.abs(row.winShare-.4/3)<1e-10);assert.equal(row.lossShare,.1);assert.equal(row.usage,.4);
assert.equal(row.bands[0].games,1);assert.equal(row.bands[1].wins,1);
assert.equal(aggregate(data,'units',{mode:'rm_1v1'}).thin.length,0);
assert.equal(aggregate(data,'units',{mode:'team'}).thin.length,1);
assert.equal(aggregate(data,'units',{civ:'french'}).thin.length,0);
assert.equal(aggregate(data,'units',{rating:'unknown'}).thin.length,0);
assert.equal(aggregate(data,'technologies',{}).thin[0].rate,2/3);
assert.equal(aggregate(data,'landmarks',{}).thin[0].uses,4);
row=aggregate({...data,groups:[group({units:{games:0,wins:0,items:{}}}),group()]},'units',{}).thin[0];
assert.equal(row.games,4,'Unavailable mappings must not become non-use games');
assert.equal(aggregate({...data,groups:[group({units:{games:2,wins:2,items:{archer:{uses:1,wins:1,shareSum:.4,winShareSum:.4,lossShareSum:0}}}})]},'units',{}).thin[0].difference,null);
console.log('Aggregate checks passed: zero-use denominators, win/loss share averages, metadata eligibility, mode/rating filters, missing mapping and band sums.');
const app=process.argv[2];
if(app)(async()=>{
  const puppeteer=require(require.resolve('puppeteer',{paths:[__dirname,path.resolve(__dirname,'../..')]}));
  const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
  try{
    const page=await browser.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    await page.setViewport({width:1440,height:1000});
    await page.emulateMediaFeatures([{name:'prefers-reduced-motion',value:'reduce'}]);
    await page.goto(pathToFileURL(path.resolve(app)).href+'#winrates',{waitUntil:'load'});
    await page.waitForSelector('.wr-board');
    const civData=await page.evaluate(()=>({games:WINRATES.ranks[WINRATES.bands[0].id].games,solo:wrBoard('solo'),team:wrBoard('team')}));
    assert.ok(civData.games>=29478,'Keep the existing large civilization dataset');
    assert.deepEqual(await page.$$eval('.wr-board',nodes=>nodes.map(node=>node.dataset.wrMode)),['solo','team']);
    const verifyCivilizationRows=async()=>{
      const mismatches=await page.evaluate(()=>[...document.querySelectorAll('.wr-board')].flatMap(board=>{
        const expected=wrBoard(board.dataset.wrMode),rows=[...(expected.total?[expected.total]:[]),...expected.ranked,...expected.thin];
        return [...board.querySelectorAll('[data-wr-row]')].flatMap(node=>{
          const row=rows.find(row=>row.key===node.dataset.wrRow);
          return !row||node.querySelector('.wr-games').textContent!==wrNumber(row.games)||node.querySelector('.wr-rate').textContent!==(row.games?wrPercent(row.rate):'–')?[node.dataset.wrRow]:[];
        });
      }));
      assert.deepEqual(mismatches,[]);
    };
    await verifyCivilizationRows();
    await page.click('[data-wr-view="sizes"]');assert.equal(await page.$$eval('.wr-board',nodes=>nodes.length),4);await verifyCivilizationRows();
    await page.evaluate(()=>{const select=document.querySelector('#wr-map');select.value=[...select.options].find(option=>option.value).value;select.dispatchEvent(new Event('change',{bubbles:true}));});await verifyCivilizationRows();
    await page.evaluate(()=>{const select=document.querySelector('#wr-civ');select.value='english';select.dispatchEvent(new Event('change',{bubbles:true}));});
    assert.equal(await page.$eval('#wr-map',select=>select.value),'');assert.ok(await page.$('.wr-total'));await verifyCivilizationRows();
    await page.evaluate(()=>{const select=document.querySelector('#wr-civ');select.value='';select.dispatchEvent(new Event('change',{bubbles:true}));});
    await page.click('[data-wr-view="overall"]');
    const output=path.join(__dirname,'shots/winrate-items');fs.mkdirSync(output,{recursive:true});
    const screenshot=async options=>{await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));await page.screenshot(options);};
    await screenshot({path:path.join(output,'civilizations.png'),fullPage:true});
    for(const type of ['units','technologies','landmarks']){
      await page.click(`[data-wr-category="${type}"]`);await page.waitForSelector('.wc-board');
      const checked=await page.evaluate(type=>{
        const expected=wcAggregate(wcData(),type,{...wcState,civ:wrState.civ}),rows=[...expected.ranked,...expected.thin];
        return {rendered:document.querySelectorAll('[data-wc-row]').length,expected:rows.length,names:[...document.querySelectorAll('.wc-item>span:first-of-type')].map(node=>node.textContent),generic:[...document.querySelectorAll('.wc-table th')].some(node=>node.textContent.trim()==='Choice'),images:document.querySelectorAll('.wc-item img').length};
      },type);
      assert.equal(checked.rendered,checked.expected);assert.equal(checked.generic,false);assert.ok(checked.rendered>0,`${type} has actual observed items`);assert.ok(checked.images>0,`${type} has authentic icons`);
      await page.click('[data-wc-detail]');assert.equal(await page.$eval('[data-wc-detail-row]',row=>row.hidden),false);
      if(type==='units')assert.equal(await page.$$eval('.wc-band-table tbody tr',rows=>rows.length)>0,true);
      await screenshot({path:path.join(output,`${type}.png`),fullPage:false});
      await page.select('#wc-civ','english');
      assert.equal(await page.evaluate(type=>[...document.querySelectorAll('[data-wc-row]')].every(row=>{const item=wcData().items[type].find(item=>item.id===row.dataset.wcRow);return !item.civs?.length||item.civs.includes('english');}),type),true);
      await page.select('#wc-civ','');
    }
    await page.click('[data-wr-category="units"]');
    await page.click('#lang-toggle');await page.waitForFunction(()=>document.documentElement.lang==='zh-CN');
    assert.match(await page.$eval('.wc-board h2',node=>node.textContent),/单位/);
    assert.match(await page.$eval('.wc-table thead',node=>node.textContent),/生产占比/);
    await screenshot({path:path.join(output,'units-zh.png'),fullPage:false});
    await page.click('#lang-toggle');await page.waitForFunction(()=>document.documentElement.lang==='en');
    await page.evaluate(()=>{const select=document.querySelector('#theme');select.value='light';select.dispatchEvent(new Event('change',{bubbles:true}));});
    await screenshot({path:path.join(output,'units-light.png'),fullPage:false});
    await page.setViewport({width:390,height:844});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'No page overflow');
    await screenshot({path:path.join(output,'units-mobile.png'),fullPage:false});
    await page.click('[data-wr-category="civilizations"]');await page.waitForSelector('.wr-board');
    assert.equal(await page.evaluate(()=>WINRATES.ranks[WINRATES.bands[0].id].games),civData.games);
    assert.deepEqual(errors,[]);
    console.log('Headless integration passed: preserved civilization counts and filters, category rows, names/icons, civ filters, details, Chinese, both themes and mobile.');
  }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
