import assert from 'node:assert/strict';
import fs from 'node:fs';
import {loan,simulate,median,inGeometry,buildZones,observedRents} from '../lib/analysis.ts';
assert.equal(loan(120000,0,10),1000);
assert.equal(median([1,2,100,101]),51);
const sim=simulate({price:100000,fees:0,works:0,furniture:0,rent:1000,charges:1000,tax:500,insurance:100,maintenance:400,vacancy:10,management:10,deposit:100000,rate:0,years:10,loanInsurance:0});
assert.equal(sim.annual,10800);assert.equal(sim.expenses,3080);assert.equal(sim.monthly,0);assert.ok(Math.abs(sim.cashflow-7720/12)<1e-8);
const g={type:'Polygon',coordinates:[[[0,0],[4,0],[4,4],[0,4],[0,0]],[[1,1],[2,1],[2,2],[1,2],[1,1]]]};assert.equal(inGeometry([.5,.5],g),true);assert.equal(inGeometry([1.5,1.5],g),false);
const f={budget:150000,totalBudget:0,minArea:25,maxArea:50,type:'Appartement',year:'all',rooms:'all',minSample:8,rentHC:0,minYield:0,maxDistance:0,campus:'',strategy:'equilibre',weights:[45,35,20]};
for(const city of ['laval','tours']){const data=JSON.parse(fs.readFileSync(new URL('../public/data/'+city+'.json',import.meta.url))),points=JSON.parse(fs.readFileSync(new URL('../public/data/points.json',import.meta.url)));const zs=buildZones(data,points,f);assert.ok(zs.length>0);assert.ok(zs.every(z=>z.yield===null));assert.ok(zs.every(z=>z.count>=8||z.score===null));assert.ok(zs.every(z=>z.price<=f.budget));assert.ok(zs.every(z=>z.rent===undefined||Number.isFinite(z.rent.loypredm2)));const empty=buildZones({...data,transactions:[]},points,f);assert.equal(empty.length,0);const missing=buildZones(data,[],f);assert.ok(missing.every(z=>z.score===null));if(city==='tours'){const oll=observedRents(data,{...f,rooms:'2'});assert.equal(oll.features.length,3);assert.ok(oll.features.every(f=>f.properties.value>0))}console.log(city,zs.length,'secteurs vérifiés')}
console.log('Calculs, données manquantes, géométries et snapshots : OK');
