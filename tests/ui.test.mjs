import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';
import {createRequire} from 'node:module';
import * as analysis from '../lib/analysis.ts';
const require=createRequire(import.meta.url);
const spec=require(require.resolve('@maplibre/maplibre-gl-style-spec',{paths:[require.resolve('maplibre-gl/package.json')]}));
const data=Object.fromEntries(['laval','tours'].map(c=>[c,JSON.parse(fs.readFileSync('public/data/'+c+'.json'))]));
const points=JSON.parse(fs.readFileSync('public/data/points.json'));
const filters={budget:150000,totalBudget:0,minArea:25,maxArea:50,type:'Appartement',year:'all',rooms:'all',minSample:8,rentHC:0,minYield:0,maxDistance:0,campus:'',strategy:'equilibre',weights:[45,35,20]};
const jsx=(type,props)=>({type,props:props||{}});
function harness(file,overrides={}){
 let cells=[],index=0,pending=[],dirty=false,tree,props={},observers=[];
 const same=(a,b)=>a&&b&&a.length===b.length&&a.every((x,i)=>Object.is(x,b[i]));
 const react={useState(init){const i=index++;cells[i]??={value:typeof init==='function'?init():init};return [cells[i].value,v=>{cells[i].value=typeof v==='function'?v(cells[i].value):v;dirty=true}]},useRef(init){const i=index++;return cells[i]??=( {current:init})},useMemo(fn,deps){const i=index++;if(!same(cells[i]?.deps,deps))cells[i]={value:fn(),deps};return cells[i].value},useEffect(fn,deps){const i=index++;if(!same(cells[i]?.deps,deps)){const old=cells[i];cells[i]={deps,cleanup:old?.cleanup};pending.push(()=>{old?.cleanup?.();cells[i].cleanup=fn()})}}};
 const exported={};const code=ts.transpileModule(fs.readFileSync(file,'utf8')+(file.endsWith('page.tsx')?'\nexport {Simulator,PointDetail};':''),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
 const storage=new Map(),downloads=[];
 const modules=new Proxy({}, {get:(_,key)=>key});
 const sandbox={exports:exported,require:id=>id==='react'?react:id==='react/jsx-runtime'?{jsx,jsxs:jsx,Fragment:'Fragment'}:id==='maplibre-gl'?overrides.maplibre:id==='@/lib/analysis'?analysis:id==='next/dynamic'?{default:()=> 'MapView',__esModule:true}:id.endsWith('.css')?{}:modules,
  ResizeObserver:class {constructor(cb){this.cb=cb;observers.push(this)}observe(el){this.el=el}disconnect(){this.disconnected=true}},
  process:{env:{}},window:{matchMedia:()=>({matches:false})},document:{modelContext:null,createElement:()=>({click(){downloads.push(this)}})},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},fetch:async url=>({ok:true,json:async()=>url==='/data/points.json'?points:url==='/data/sources.json'?{retrieved:'2026-10-06',sources:[]}:url.startsWith('/api/')?{features:[{geometry:{coordinates:[-.77,48.076]},properties:{label:'Adresse test'}}]}:data[url.includes('tours')?'tours':'laval']}),URL:class extends URL {static createObjectURL(blob){downloads.push(blob);return 'blob:test'}static revokeObjectURL(){}},Blob,AbortController,console,...overrides.globals};
 vm.runInNewContext(code,sandbox,{filename:file});
 const render=(next=props,component=exported.default)=>{props=next;do{dirty=false;index=0;tree=component(props);nodes(tree,n=>!!n.props?.ref).forEach(n=>{n.props.ref.current??={}});pending.splice(0).forEach(fn=>fn())}while(dirty);return tree};
 return {exports:exported,render,storage,downloads,observers,get tree(){return tree},async settle(component=exported.default){for(let i=0;i<5;i++){await new Promise(r=>setImmediate(r));render(props,component)}},cleanup(){cells.forEach(c=>c?.cleanup?.())},attachRefs(t=tree){if(!t||typeof t!=='object')return;if(t.props?.ref)t.props.ref.current={};for(const c of [t.props?.children].flat(Infinity))this.attachRefs(c)}};
}
function nodes(tree,predicate){const result=[];function walk(t){if(!t||typeof t!=='object')return;if(predicate(t))result.push(t);for(const c of [t.props?.children].flat(Infinity))walk(c)}walk(tree);return result}
const find=(h,p)=>{const n=nodes(h.tree,p)[0];assert.ok(n,'Contrôle introuvable');return n};
class FakeMap {static all=[];constructor(options){this.options=options;this.sources={};this.layers=[];this.events=[];this.visibility={};this.flights=[];FakeMap.all.push(this)}addControl(){}on(event,layer,fn){this.events.push({event,layer:typeof layer==='string'?layer:null,fn:fn||layer})}addSource(id,source){this.sources[id]={...source,setData:d=>this.sources[id].data=JSON.parse(JSON.stringify(d))}}getSource(id){assert.ok(this.sources[id],id);return this.sources[id]}addLayer(layer){this.layers.push(layer)}setLayoutProperty(id,key,value){assert.ok(this.layers.some(l=>l.id===id),id);this.visibility[id]=value}flyTo(v){this.flights.push(v)}getCanvas(){return {style:{}}}resize(){this.resized=true}remove(){this.removed=true}emit(event,layer,eventData){for(const e of this.events)if(e.event===event&&e.layer===layer)e.fn(eventData)}}
let configuredWorker;const maplibre={setWorkerUrl:url=>configuredWorker=url,Map:FakeMap,NavigationControl:class {},ScaleControl:class {}};
for(const city of ['laval','tours']){
 const h=harness('app/map.tsx',{maplibre});let selected,point,polygon,radius;
 const props={data:data[city],zones:analysis.buildZones(data[city],points,filters),points,layer:'price',observed:analysis.observedRents(data[city],filters),showStops:true,showLines:true,showCampus:true,showServices:true,showProjects:true,selected:'',onSelect:id=>selected=id,onPoint:p=>point=p,focus:{lon:data[city].config.center[0],lat:data[city].config.center[1]},polygon:[],setPolygon:p=>polygon=p,draw:false,radius:null,setRadius:r=>radius=r,radiusMode:false};
 hostMapAssertions(h,props,city);
}
function hostMapAssertions(h,props,city){
 h.render(props);const m=FakeMap.all.at(-1);assert.ok(m);assert.equal(configuredWorker,'/maplibre/maplibre-gl-worker.mjs');m.emit('load',null);h.render(props);
 assert.equal(spec.validateStyleMin({version:8,sources:Object.fromEntries(Object.entries(m.sources).map(([k,v])=>[k,{type:'geojson',data:v.data}])),layers:m.layers}).length,0);
 assert.equal(m.sources.lines.data.features.length,data[city].transport.lines.features.length);
 assert.equal(m.sources.stops.data.features.length,data[city].transport.stops.features.length);
 assert.equal(m.sources.zones.data.features.length,props.zones.length);assert.ok(m.sources.points.data.features.length>0);
 assert.equal(m.visibility['lines-layer'],'visible');assert.equal(m.visibility['lines-casing'],'visible');assert.equal(m.visibility['stops-layer'],'visible');
 h.render({...props,showLines:false,showStops:false,showCampus:false,showServices:false,showProjects:false});assert.equal(m.visibility['lines-layer'],'none');assert.equal(m.visibility['lines-casing'],'none');assert.equal(m.visibility['stops-layer'],'none');assert.equal(m.sources.points.data.features.length,0);
 for(const kind of ['campus','service','project']){h.render({...props,showCampus:kind==='campus',showServices:kind==='service',showProjects:kind==='project'});assert.ok(m.sources.points.data.features.length>0);assert.ok(m.sources.points.data.features.every(f=>kind==='campus'?f.properties.kind==='campus':kind==='service'?['service','employment'].includes(f.properties.kind):['project','housing'].includes(f.properties.kind)))}
 for(const layer of ['price','trend','volume','rent','yield','score','transactions','rentObserved']){h.render({...props,layer});assert.equal(m.visibility['zone-fill'],layer==='rentObserved'?'none':'visible');assert.equal(m.sources.oll.data.features.length,layer==='rentObserved'&&city==='tours'?3:0);assert.equal(m.sources.transactions.data.features.length,layer==='transactions'?props.zones.flatMap(z=>z.transactions).length:0);assert.ok(m.sources.zones.data.features.every(f=>/^#[0-9a-f]{6}$/i.test(f.properties.color)))}
 assert.equal(m.layers.find(l=>l.id==='tx-layer').minzoom,11);
 let p,z,drawn,rad;h.render({...props,onPoint:v=>p=v,onSelect:v=>z=v,setPolygon:v=>drawn=v,setRadius:v=>rad=v});
 m.emit('click','lines-layer',{features:[{properties:{id:'route-1',name:'A'}}]});assert.equal(p.kind,'route');
 m.emit('click','stops-layer',{features:[{properties:{name:'Arrêt',routes:'["a"]'}}]});assert.equal(p.kind,'stop');
 m.emit('click','points-layer',{features:[{properties:{kind:'campus',name:'Campus'}}]});assert.equal(p.kind,'campus');
 m.emit('click','zone-fill',{features:[{properties:{id:props.zones[0].id}}]});assert.equal(z,props.zones[0].id);
 h.render({...props,draw:true,setPolygon:v=>drawn=v});m.emit('click',null,{lngLat:{lng:1,lat:2}});assert.equal(JSON.stringify(drawn),'[[1,2]]');
 h.render({...props,radiusMode:true,setRadius:v=>rad=v});m.emit('click',null,{lngLat:{lng:1,lat:2}});assert.equal(rad.meters,1000);
 h.render({...props,selected:props.zones[0].id,polygon:[[0,0],[1,0],[1,1]],radius:{center:props.data.config.center,meters:1000}});assert.equal(m.sources.selection.data.features.length,3);
 const other=city==='laval'?'tours':'laval';h.render({...props,data:data[other],focus:null});assert.equal(m.sources.lines.data.features.length,data[other].transport.lines.features.length);assert.deepEqual(m.flights.at(-1).center,data[other].config.center);
 h.observers[0].cb();assert.ok(m.resized);h.cleanup();assert.ok(m.removed);assert.ok(h.observers[0].disconnected);
 console.log(city+': données, 8 couches, interrupteurs, clics, dessin, rayon, changement de ville et redimensionnement OK');
}
// Page interactions use real snapshots and analysis, with mocked host controls/network only.
const home=harness('app/page.tsx');home.render();await home.settle();
const map=()=>find(home,n=>n.type==='MapView');assert.equal(map().props.data.config.name,'Laval');assert.equal(map().props.showLines,true);assert.equal(map().props.showStops,true);
const pick=label=>find(home,n=>n.props.label===label&&typeof n.props.onChange==='function');
pick('Ville').props.onChange('tours');home.render();await home.settle();assert.equal(map().props.data.config.name,'Tours');
pick('Nombre de pièces').props.onChange('2');home.render();assert.ok(map().props.zones.every(z=>z.transactions.every(t=>t.rooms===2)));
const switchLine=find(home,n=>n.type==='Switch'&&n.props['aria-label']?.startsWith('Bus & tram'));switchLine.props.onCheckedChange(false);home.render();assert.equal(map().props.showLines,false);
pick('Couche cartographique').props.onChange('transactions');home.render();assert.equal(map().props.layer,'transactions');
map().props.onSelect(map().props.zones[0].id);home.render();let detail=find(home,n=>typeof n.type==='function'&&n.type.name==='ZoneDetail');detail.props.toggleFavorite();home.render();assert.ok(home.storage.get('atlas-favorites').includes('tours:'));detail=find(home,n=>typeof n.type==='function'&&n.type.name==='ZoneDetail');detail.props.toggleCompare();home.render();assert.equal(find(home,n=>n.props.className==='compare-dialog').props.children[2].props.children.length,1);
find(home,n=>n.props.title==='Exporter en CSV').props.onClick();assert.ok(home.downloads.some(d=>d instanceof Blob));const csv=await home.downloads.find(d=>d instanceof Blob).text();assert.ok(csv.includes('mediane_eur_m2'));assert.ok(csv.split('\r\n').length>1);
map().props.setRadius({center:[.684,47.386],meters:1000});home.render();assert.ok(map().props.zones.every(z=>z.transactions.every(t=>analysis.distance([t.lon,t.lat],[.684,47.386])<=1000)));
const tabs=find(home,n=>n.type==='Tabs');for(const page of ['projects','sources','simulator','explorer']){tabs.props.onValueChange(page);home.render();assert.ok(home.tree)}
// Exercise the rendered simulator controls and memo invalidation without a browser.
const sim=harness('app/page.tsx');const simProps={city:'tours',onCity:()=>{},data:data.tours,selectedZone:analysis.buildZones(data.tours,points,filters)[0]};sim.render(simProps,sim.exports.Simulator);const before=nodes(sim.tree,n=>n.props.className==='comparable').length;find(sim,n=>n.props.label==='Pièces').props.onChange(1);sim.render(simProps,sim.exports.Simulator);const expected=data.tours.transactions.filter(t=>t.type==='Appartement'&&t.nature==='Vente'&&Math.abs(t.area-35)<=10&&t.rooms===1&&analysis.distance([simProps.selectedZone.lon,simProps.selectedZone.lat],[t.lon,t.lat])<1000).slice(0,15).length;assert.equal(nodes(sim.tree,n=>n.props.className==='comparable').length,expected);
// Route identifiers include colons in Tours: never split a route ID to get direction.
assert.deepEqual(analysis.departureGroups([[420,'TTR:LINE:2','0'],[440,'TTR:LINE:2','0'],[430,'TTR:LINE:2','1'],[540,'TTR:LINE:2','0']]).map(g=>[g.route,g.direction,g.times.length]),[['TTR:LINE:2','0',2],['TTR:LINE:2','1',1]]);
console.log('Filtres, changement de ville, favoris, comparaison, CSV, rayon, navigation et comparables du simulateur OK');
// Search, saved filters and city reset.
const search=harness('app/page.tsx');search.render();await search.settle();find(search,n=>n.type==='CommandInput').props.onValueChange('Calmette');search.render();await find(search,n=>n.props.className==='primary-button'&&n.props.disabled===false).props.onClick();search.render();const addressItem=find(search,n=>n.type==='CommandItem'&&n.props.children==='Adresse test');addressItem.props.onSelect();search.render();assert.equal(find(search,n=>n.type==='MapView').props.radius.meters,1000);
find(search,n=>n.props.label==='Ville').props.onChange('tours');search.render();await search.settle();assert.equal(find(search,n=>n.type==='MapView').props.radius,null);assert.equal(find(search,n=>n.type==='MapView').props.focus,null);
const buttons=()=>nodes(search.tree,n=>n.type==='button');buttons().find(n=>n.props.children==='Enregistrer').props.onClick();assert.ok(search.storage.has('atlas-filters-tours'));find(search,n=>n.props.label==='Nombre de pièces').props.onChange('1');search.render();buttons().find(n=>n.props.children==='Restaurer').props.onClick();search.render();assert.equal(find(search,n=>n.props.label==='Nombre de pièces').props.value,'all');
for(const city of ['laval','tours']){
 for(const collection of [data[city].transport.lines,data[city].transport.stops])for(const feature of collection.features){assert.ok(feature.geometry.coordinates.length);const coords=feature.geometry.type==='Point'?[feature.geometry.coordinates]:feature.geometry.coordinates;assert.ok(coords.every(([x,y])=>Number.isFinite(x)&&Number.isFinite(y)&&x>=-180&&x<=180&&y>=-90&&y<=90))}
 for(const t of data[city].transactions)assert.ok(t.price>0&&t.area>0&&Number.isFinite(t.ppm));
 const low=analysis.buildZones(data[city],points,{...filters,budget:80000,rooms:'1',year:'2025',totalBudget:85000});assert.ok(low.every(z=>z.transactions.every(t=>t.rooms===1&&t.date.startsWith('2025'))&&z.price<=80000&&z.price*1.08<=85000));
 const f={...filters,rentHC:650,minYield:7,maxDistance:1500};const income=analysis.buildZones(data[city],points,f);assert.ok(income.every(z=>z.yield>=7&&z.campusDistance<=1500));
}
const route=harness('app/api/geocode/route.ts',{globals:{Response,Request,fetch:async()=>({ok:true,json:async()=>({features:[]})})}});assert.equal((await route.exports.GET(new Request('https://local/api/geocode?q=ab'))).status,400);assert.equal((await route.exports.GET(new Request('https://local/api/geocode?q=Tours'))).status,200);
const failed=harness('app/api/geocode/route.ts',{globals:{Response,Request,fetch:async()=>{throw Error('Unavailable')}}});assert.equal((await failed.exports.GET(new Request('https://local/api/geocode?q=Tours'))).status,503);
console.log('Recherche, enregistrement/restauration, géométries, filtres combinés et erreurs API OK');
