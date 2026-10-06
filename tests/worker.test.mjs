import {Worker} from 'node:worker_threads';
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
for(const file of ['maplibre-gl-worker.mjs','maplibre-gl-shared.mjs'])assert.deepEqual(readFileSync('public/maplibre/'+file),readFileSync('node_modules/maplibre-gl/dist/'+file));
const points=JSON.parse(readFileSync('public/data/points.json'));
for(const city of ['laval','tours']){
 const d=JSON.parse(readFileSync('public/data/'+city+'.json'));
 const sources=[['lines',d.transport.lines],['stops',d.transport.stops],['communes',d.communes],['points',{type:'FeatureCollection',features:points.filter(p=>p.city===city).map(p=>({type:'Feature',properties:{id:p.id},geometry:{type:'Point',coordinates:[p.lon,p.lat]}}))}]];
 const result=await new Promise((resolve,reject)=>{const w=new Worker(new URL('./worker-thread.mjs',import.meta.url),{workerData:{center:d.config.center,url:new URL('../public/maplibre/maplibre-gl-worker.mjs',import.meta.url).href,sources}});const timer=setTimeout(()=>{w.terminate();reject(Error('Worker timeout'))},15000);w.on('error',e=>{clearTimeout(timer);reject(e)});w.on('message',msg=>{if(msg.result){clearTimeout(timer);w.terminate();resolve(msg.result)}});w.on('exit',code=>{if(code!==0){clearTimeout(timer);reject(Error('Worker exit '+code))}})});
 assert.equal(result.length,4);console.log(city+': vrai worker livré — '+JSON.stringify(result));
}
