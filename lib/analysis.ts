export type Tx={id:string;date:string;price:number;area:number;rooms:number|null;type:string;nature:string;code:string;commune:string;address:string;lon:number;lat:number;ppm:number;dependencies:boolean};
export type Point={id:string;name:string;city:string;lon:number;lat:number;kind:string;address:string;source:string;status?:string;year?:number;capacity?:number;description?:string;precision?:string};
export type Filters={budget:number;totalBudget:number;minArea:number;maxArea:number;type:string;year:string;rooms:string;minSample:number;rentHC:number;minYield:number;maxDistance:number;campus:string;strategy:string;weights:number[]};
export type Zone={id:string;name:string;lon:number;lat:number;bounds:number[][];transactions:Tx[];median:number;q1:number;q3:number;price:number;count:number;history:{year:string;median:number;count:number}[];trend:number|null;campusDistance:number|null;nearestCampus:Point|null;stopDistance:number|null;stop:any;score:number|null;parts:{label:string;value:number;weight:number}[];yield:number|null;rent:any;code:string};
export const median=(a:number[])=>quantile(a,.5);
export function quantile(a:number[],q:number){if(!a.length)return 0;const v=[...a].sort((a,b)=>a-b),i=(v.length-1)*q,l=Math.floor(i);return v[l]+(v[Math.ceil(i)]-v[l])*(i-l)}
export function distance(a:number[],b:number[]){const rad=Math.PI/180,dlat=(b[1]-a[1])*rad,dlon=(b[0]-a[0])*rad;const h=Math.sin(dlat/2)**2+Math.cos(a[1]*rad)*Math.cos(b[1]*rad)*Math.sin(dlon/2)**2;return 6371000*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h))}
export function inPolygon(p:number[],polygon:number[][]){let inside=false;for(let i=0,j=polygon.length-1;i<polygon.length;j=i++){const [xi,yi]=polygon[i],[xj,yj]=polygon[j];if((yi>p[1])!==(yj>p[1])&&p[0]<(xj-xi)*(p[1]-yi)/(yj-yi)+xi)inside=!inside}return inside}
export function inGeometry(p:number[],g:any){const polygons=g.type==='Polygon'?[g.coordinates]:g.type==='MultiPolygon'?g.coordinates:[];return polygons.some((rings:number[][][])=>inPolygon(p,rings[0])&&!rings.slice(1).some(r=>inPolygon(p,r)))}
export function observedRents(data:any,f:Filters){if(!data?.oll)return {type:'FeatureCollection',features:[]};const typ=f.type==='Tous'?'':f.type;const piece=f.rooms==='all'?'':typ==='Appartement'?'Appart '+f.rooms+'P'+(f.rooms==='4'?'+':''):typ==='Maison'?'Maison '+(Number(f.rooms)<4?'1-3P':'4P+'):'Ensemble '+f.rooms+'P';return {...data.oll.features,features:data.oll.features.features.map((feature:any)=>{const row=data.oll.rows.find((r:any)=>r.Zone_calcul===feature.properties.id&&r.Type_habitat===typ&&r.nombre_pieces_homogene===piece&&!r.Zone_complementaire&&!r.epoque_construction_local&&!r.epoque_construction_homogene&&!r.anciennete_locataire_local&&!r.anciennete_locataire_homogene&&!r.nombre_pieces_local);return {...feature,properties:{...feature.properties,kind:'oll',year:2024,value:row?.loyer_median??null,monthly:row?.loyer_mensuel_median??null,surface:row?.surface_moyenne??null,count:row?.nombre_observations??null,type:typ||'Ensemble',rooms:f.rooms,q1:row?.loyer_1_quartile??null,q3:row?.loyer_3_quartile??null,source:data.oll.source}}})}}
export function filtered(tx:Tx[],f:Filters){return tx.filter(t=>(f.type==='Tous'||t.type===f.type)&&t.area>=f.minArea&&t.area<=f.maxArea&&(f.rooms==='all'||t.rooms===Number(f.rooms))&&(f.year==='all'||t.date.startsWith(f.year))&&t.nature==='Vente')}
export function buildZones(data:any,points:Point[],f:Filters,polygon:number[][]=[],radius:{center:number[];meters:number}|null=null):Zone[]{
 const tx=filtered(data.transactions,f).filter((t:Tx)=>(polygon.length<3||inPolygon([t.lon,t.lat],polygon))&&(!radius||distance([t.lon,t.lat],radius.center)<=radius.meters));
 const mid=data.config.center,dy=750/111320,dx=750/(111320*Math.cos(mid[1]*Math.PI/180));const groups=new Map<string,Tx[]>();
 tx.forEach((t:Tx)=>{const x=Math.floor((t.lon-mid[0])/dx),y=Math.floor((t.lat-mid[1])/dy),id=x+':'+y;groups.set(id,[...(groups.get(id)||[]),t])});
 const campuses=points.filter(p=>p.kind==='campus'&&p.city===data.config.name.toLowerCase()),stops=data.transport?.stops?.features||[];
 return [...groups].map(([id,items])=>{const [x,y]=id.split(':').map(Number),lon=mid[0]+(x+.5)*dx,lat=mid[1]+(y+.5)*dy;
  const nearestCampus=campuses.length?[...campuses].sort((a,b)=>distance([lon,lat],[a.lon,a.lat])-distance([lon,lat],[b.lon,b.lat]))[0]:null;
  const target=f.campus?campuses.find(p=>p.id===f.campus)||nearestCampus:nearestCampus;
  const nearby=stops.map((s:any)=>({s,d:distance([lon,lat],s.geometry.coordinates)})).sort((a:any,b:any)=>a.d-b.d)[0];
  const streets=items.reduce((m:Record<string,number>,t:Tx)=>{const street=t.address.replace(/^\d+\s*(?:[A-Z]\s+)?/, '');m[street]=(m[street]||0)+1;return m},{});const street=Object.keys(streets).sort((a,b)=>streets[b]-streets[a])[0];
  const code=items.reduce((m:Record<string,number>,t:Tx)=>{m[t.code]=(m[t.code]||0)+1;return m},{});const dominant=Object.keys(code).sort((a,b)=>code[b]-code[a])[0];
  const ppm=median(items.map(t=>t.ppm)),price=ppm*((f.minArea+f.maxArea)/2);
  const history=['2021','2022','2023','2024','2025'].map(year=>{const rows=items.filter(t=>t.date.startsWith(year));return {year,median:median(rows.map(t=>t.ppm)),count:rows.length}});
  const recent=history.filter(h=>h.count>=8),trend=recent.length>=2?(recent.at(-1)!.median/recent[0].median-1)*100:null;
  const cd=target?distance([lon,lat],[target.lon,target.lat]):null;
  const cost=Math.max(0,Math.min(100,100*(1-price/(f.budget*1.5))));
  const accessibility=cd===null?null:Math.max(0,100*(1-cd/5000));
  // Volume measures observation depth, not sale speed or predicted vacancy.
  const depth=Math.min(100,items.length/40*100);
  const values=[cost,accessibility,depth];const labels=['Coût d’entrée indicatif','Proximité du campus','Profondeur des comparables'];
  const parts=values.flatMap((v,i)=>v===null?[]:[{label:labels[i],value:Math.round(v),weight:f.weights[i]}]);const sum=parts.reduce((s,p)=>s+p.weight,0);
  const score=items.length>=f.minSample&&parts.length===3&&sum>0?Math.round(parts.reduce((s,p)=>s+p.value*p.weight,0)/sum):null;
  const rentKind=f.type==='Maison'?'maison':f.rooms==='1'||f.rooms==='2'?'app12':f.rooms==='3'||f.rooms==='4'?'app3':'app';
  const rent=(data.rentReferences?.[rentKind]||data.rents).find((r:any)=>String(r.INSEE_C||r.insee_c||r.code_insee||r.INSEE)==dominant);
  const yieldValue=f.rentHC>0?f.rentHC*12/price*100:null;
  return {id,name:items[0].commune+' · '+(street||id),lon,lat,bounds:[[mid[0]+x*dx,mid[1]+y*dy],[mid[0]+(x+1)*dx,mid[1]+(y+1)*dy]],transactions:items,median:ppm,q1:quantile(items.map(t=>t.ppm),.25),q3:quantile(items.map(t=>t.ppm),.75),price,count:items.length,history,trend,campusDistance:cd,nearestCampus:target,stopDistance:nearby?.d??null,stop:nearby?.s??null,score,parts,yield:yieldValue,rent,code:dominant};
 }).filter(z=>z.price<=f.budget&&(f.totalBudget<=0||z.price*1.08<=f.totalBudget)&&(f.maxDistance<=0||z.campusDistance!==null&&z.campusDistance<=f.maxDistance)&&(f.minYield<=0||z.yield!==null&&z.yield>=f.minYield)).sort((a,b)=>(b.score??-1)-(a.score??-1)||b.count-a.count)
}
export function loan(principal:number,annualRate:number,years:number){if(!Number.isFinite(principal)||principal<0||years<=0)return 0;const n=years*12,r=annualRate/1200;return r===0?principal/n:principal*r/(1-Math.pow(1+r,-n))}
export function simulate(v:Record<string,number>){const cost=v.price+v.fees+v.works+v.furniture,annual=v.rent*12*(1-v.vacancy/100),expenses=v.charges+v.tax+v.insurance+v.maintenance+annual*v.management/100,capital=Math.max(0,cost-v.deposit),monthly=loan(capital,v.rate,v.years),insurance=capital*v.loanInsurance/1200;return {cost,annual,expenses,capital,monthly,insurance,brut:v.price>0?v.rent*12/v.price*100:0,brutTotal:cost>0?v.rent*12/cost*100:0,net:cost>0?(annual-expenses)/cost*100:0,cashflow:(annual-expenses)/12-monthly-insurance}}
