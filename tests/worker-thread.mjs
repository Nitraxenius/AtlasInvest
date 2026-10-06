import {parentPort,workerData} from 'node:worker_threads';
// Browser worker globals supplied by the test host; MapLibre's worker code is unchanged.
globalThis.WorkerGlobalScope=class extends EventTarget {};
globalThis.self=new WorkerGlobalScope();
self.postMessage=value=>parentPort.postMessage(value);
globalThis.location={origin:'https://test.local'};
await import(workerData.url);
if(!self.worker)throw Error('MapLibre worker failed to initialise');
const result=[];
for(const [name,data] of workerData.sources){
 const source=self.worker._getWorkerSource('test','geojson',name);
 await source.loadData({type:'geojson',source:name,data,geojsonVtOptions:{maxZoom:18,extent:8192,buffer:128,tolerance:3}});
 const [lon,lat]=workerData.center,z=13,n=2**z,x=Math.floor((lon+180)/360*n),y=Math.floor((1-Math.asinh(Math.tan(lat*Math.PI/180))/Math.PI)/2*n);
 const tile=source._geoJSONIndex.getTile(z,x,y)||source._geoJSONIndex.getTile(0,0,0);
 if(!tile?.features?.length)throw Error('No features indexed for '+name);
 result.push({name,features:tile.features.length});
}
parentPort.postMessage({result});
