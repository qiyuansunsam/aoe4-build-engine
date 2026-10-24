const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const A=require('../site/observed-army.js'),read=p=>JSON.parse(fs.readFileSync(path.join(__dirname,'..',p),'utf8').replace(/^\uFEFF/,''));
const catalog=read('data/game-catalog.json'),library=read('data/game-library.json'),byPbg=new Map(catalog.units.map(u=>[String(u.source.pbgid),u]));
let snapshots=0;
for(const game of library.games.filter(g=>g.buildId)){
 let militarySeen=false;
 for(const m of game.snapshots){
  const result=A.summarize(m,byPbg);assert.equal(result.coverage.complete,true,game.buildId);assert.equal(result.totalValue,result.units.reduce((n,u)=>n+u.value,0));
  for(const unit of result.units){const source=m.unitCounts.find(u=>String(u.pbgid)===unit.id);assert.equal(unit.count,source.produced-source.lost);assert.equal(unit.value,unit.count*A.RESOURCES.reduce((n,r)=>n+unit.record.cost[r],0));assert.ok(unit.count>0);militarySeen=true;}
  assert.equal(result.totalValue,A.RESOURCES.reduce((n,r)=>n+result.resourceValue[r],0));snapshots++;
 }
 assert.ok(militarySeen,game.buildId);
}
assert.equal(A.summarize({unitCounts:[]},byPbg).totalValue,0);
assert.equal(A.summarize({},byPbg).totalValue,null);
const fake={x:{name:'Test',classes:['military'],cost:{food:0,wood:0,gold:0,stone:0}}};
assert.equal(A.summarize({unitCounts:[{pbgid:'x',produced:3,lost:1,balance:999}]},fake).totalValue,0);
assert.equal(A.summarize({unitCounts:[{pbgid:'x',produced:3,lost:1,balance:999}]},fake).units[0].count,2);
assert.equal(A.summarize({unitCounts:[{pbgid:'missing',balance:2}]},fake).totalValue,null);
assert.equal(A.summarize({unitCounts:[{pbgid:'x',balance:2}]},{x:{classes:['military'],cost:{food:50}}}).totalValue,null);
assert.equal(A.summarize({unitCounts:[{pbgid:'x',balance:-1}]},fake).totalValue,0);
assert.equal(A.summarize({unitCounts:[{pbgid:'x',balance:NaN}]},fake).totalValue,null);
console.log(`Observed base-cost army estimates: ${snapshots} snapshots across four references, conservation, missing data and zero-cost cases passed.`);
