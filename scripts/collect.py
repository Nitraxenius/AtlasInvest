#!/usr/bin/env python3
"""Snapshots reproductibles. stdlib uniquement. python scripts/collect.py [--refresh]."""
import csv, io, json, gzip, zipfile, urllib.request, concurrent.futures, datetime, pathlib, sys, re, math
ROOT=pathlib.Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'; OUT=ROOT/'public/data'
RAW.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
NOW=datetime.datetime.now(datetime.timezone.utc).isoformat()
REFRESH='--refresh' in sys.argv
SOURCES=[]
CONFIG={'laval':{'name':'Laval','epci':'200083392','department':'53','center':[-0.770,48.076],'budget':120000,'gtfs':'offre-de-transport-du-reseau-de-laval-agglomeration-gtfs'},'tours':{'name':'Tours','epci':'243700754','department':'37','center':[0.684,47.386],'budget':150000,'gtfs':'fil-bleu-syndicat-des-mobilites-gtfs-gtfs-rt'}}
def fetch(url,name):
 p=RAW/name
 if p.exists() and not REFRESH: return p.read_bytes()
 print('GET',name,flush=True)
 req=urllib.request.Request(url,headers={'User-Agent':'AtlasInvest/1.0 (open-data research)'})
 for attempt in range(3):
  try:
   with urllib.request.urlopen(req,timeout=90) as r: b=r.read()
   p.write_bytes(b); return b
  except Exception:
   if attempt==2: raise
def source(id,title,producer,url,resource='',license='Licence Ouverte 2.0',period='',scale='',method='',limits='',status='importé',updated=None):
 SOURCES.append(dict(id=id,title=title,producer=producer,url=url,resource=resource,license=license,period=period,scale=scale,method=method,limits=limits,status=status,retrieved=NOW,updated=updated))
def num(v):
 try:return float(str(v).replace(',','.'))
 except:return None
def parse_csv(b):
 try:s=b.decode('utf-8-sig')
 except UnicodeDecodeError:s=b.decode('cp1252')
 delim=';' if s.splitlines()[0].count(';')>s.splitlines()[0].count(',') else ','
 return list(csv.DictReader(io.StringIO(s),delimiter=delim))
def normalize(rows):
 """Conservative: only one distinct residential local signature per mutation."""
 groups={}; stats={'rawRows':len(rows),'mutations':0,'accepted':0,'excluded':{}}
 for r in rows: groups.setdefault(r.get('id_mutation',''),[]).append(r)
 result=[]
 def reject(reason): stats['excluded'][reason]=stats['excluded'].get(reason,0)+1
 for mid,rs in groups.items():
  stats['mutations']+=1
  if not mid: reject('identifiant absent');continue
  if rs[0]['nature_mutation'] not in ['Vente',"Vente en l’état futur d’achèvement","Vente en l'état futur d'achèvement"]: reject('autre nature');continue
  vals={num(r['valeur_fonciere']) for r in rs}
  if len(vals)!=1 or None in vals: reject('prix absent ou ambigu');continue
  price=next(iter(vals))
  signatures={}
  for r in rs:
   if r.get('type_local') in ['Appartement','Maison']:
    # Exact repeats caused by land/culture rows collapse; separate lots/parcels retained.
    sig=tuple(r.get(k,'') for k in ['id_parcelle','adresse_numero','adresse_suffixe','adresse_code_voie','type_local','surface_reelle_bati','nombre_pieces_principales','lot1_numero','lot2_numero','lot3_numero','lot4_numero','lot5_numero'])
    signatures[sig]=r
  if len(signatures)!=1: reject('multi-biens ou sans logement');continue
  r=next(iter(signatures.values()))
  if any(x.get('type_local')=='Local industriel. commercial ou assimilé' for x in rs):reject('local mixte');continue
  # Distinct built rows with identical signatures cannot be unambiguously resolved.
  if len({x.get('numero_disposition') for x in rs})>1:reject('plusieurs dispositions');continue
  area=num(r['surface_reelle_bati']);lon=num(r['longitude']);lat=num(r['latitude'])
  if not area or area<=0 or price is None or price<=0:reject('surface ou prix invalide');continue
  if lon is None or lat is None:reject('sans coordonnées');continue
  ppm=price/area
  if not 200<=ppm<=15000:reject('prix/m² atypique (200–15 000)');continue
  addr=' '.join(x for x in [r.get('adresse_numero'),r.get('adresse_suffixe'),r.get('adresse_nom_voie')] if x)
  result.append({'id':mid,'date':r['date_mutation'],'price':price,'area':area,'rooms':num(r['nombre_pieces_principales']),'type':r['type_local'],'nature':r['nature_mutation'],'code':r['code_commune'],'commune':r['nom_commune'],'address':addr,'lon':lon,'lat':lat,'ppm':round(ppm),'dependencies':any(x.get('type_local')=='Dépendance' for x in rs)})
 stats['accepted']=len(result); return result,stats
def gtfs(city,cfg):
 meta=json.loads(fetch('https://www.data.gouv.fr/api/1/datasets/'+cfg['gtfs']+'/',city+'-gtfs-meta.json'))
 res=next(r for r in meta['resources'] if r['format'] in ['gtfs','zip'])
 z=zipfile.ZipFile(io.BytesIO(fetch(res['url'],city+'-gtfs.zip')))
 names={pathlib.PurePosixPath(n).name:n for n in z.namelist()}
 def rows(f):return parse_csv(z.read(names[f])) if f in names else []
 routes={r['route_id']:r for r in rows('routes.txt')};trips={r['trip_id']:r for r in rows('trips.txt')}
 stops={r['stop_id']:r for r in rows('stops.txt')}; calendars=rows('calendar.txt');exceptions=rows('calendar_dates.txt')
 date=datetime.date.today(); service=set();weekday=['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][date.weekday()];ds=date.strftime('%Y%m%d')
 for r in calendars:
  if r['start_date']<=ds<=r['end_date'] and r.get(weekday)=='1':service.add(r['service_id'])
 for r in exceptions:
  if r['date']==ds:
   if r['exception_type']=='1':service.add(r['service_id'])
   else:service.discard(r['service_id'])
 perstop={}; times=rows('stop_times.txt')
 for r in times:
  trip=trips.get(r['trip_id']);sid=r['stop_id']
  if not trip:continue
  ps=perstop.setdefault(sid,{'routes':set(),'departures':[]});ps['routes'].add(trip['route_id'])
  if trip['service_id'] in service:
   t=r.get('departure_time') or r.get('arrival_time')
   if t:
    h,m,*_=map(int,t.split(':'));ps['departures'].append([h*60+m,trip['route_id'],trip.get('direction_id','')])
 features=[]
 for sid,r in stops.items():
  lon=num(r.get('stop_lon'));lat=num(r.get('stop_lat'));ps=perstop.get(sid,{'routes':set(),'departures':[]})
  if lon is None or lat is None or not ps['routes']:continue
  features.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'id':sid,'name':r['stop_name'],'routes':sorted(ps['routes']),'departures':sorted(ps['departures'])}})
 shapes={}
 for r in rows('shapes.txt'):shapes.setdefault(r['shape_id'],[]).append((int(r['shape_pt_sequence']),[float(r['shape_pt_lon']),float(r['shape_pt_lat'])]))
 lines=[]; seen=set()
 for trip in trips.values():
  key=(trip['route_id'],trip.get('shape_id'))
  if key in seen or key[1] not in shapes:continue
  seen.add(key);r=routes[key[0]]
  lines.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[p for _,p in sorted(shapes[key[1]])]},'properties':{'id':key[0],'name':r.get('route_short_name') or r.get('route_long_name'),'color':'#'+(r.get('route_color') or '748294'),'mode':r.get('route_type')}})
 compactRoutes={k:{'name':r.get('route_short_name') or r.get('route_long_name'),'longName':r.get('route_long_name'),'color':'#'+(r.get('route_color') or '748294'),'mode':r.get('route_type')} for k,r in routes.items()}
 source(city+'-gtfs','Horaires théoriques '+cfg['name'],meta.get('organization',{}).get('name','Réseau local'),'https://transport.data.gouv.fr/datasets/'+cfg['gtfs'],res['url'],str(meta.get('license')),ds,'arrêt / ligne','GTFS : calendrier et exceptions du jour ; départs par arrêt, route et direction.','Pas de temps réel ni d’itinéraires à pied. Les départs sont des horaires théoriques.',updated=res.get('last_modified'))
 return {'stops':{'type':'FeatureCollection','features':features},'lines':{'type':'FeatureCollection','features':lines},'routes':compactRoutes,'serviceDate':date.isoformat(),'activeServices':len(service)}
def run():
 data={};jobs=[]
 for city,cfg in CONFIG.items():
  geo=json.loads(fetch(f"https://geo.api.gouv.fr/epcis/{cfg['epci']}/communes?fields=nom,code,population,centre,contour&format=geojson&geometry=contour",city+'-communes.json'))
  data[city]={'config':cfg,'communes':geo};codes={f['properties']['code'] for f in geo['features']}
  source(city+'-geo','Communes de '+cfg['name'],'API Découpage administratif',f"https://geo.api.gouv.fr/epcis/{cfg['epci']}/communes",period='référentiel récupéré le '+NOW[:10],scale='commune',method='Périmètre EPCI officiel. Population du référentiel, millésime non indiqué par cet endpoint.',limits='Les contours communaux ne sont pas des quartiers.')
  data[city]['codes']=codes
  for y in range(2021,2026):jobs.append((city,y,f"https://files.data.gouv.fr/geo-dvf/latest/csv/{y}/departements/{cfg['department']}.csv.gz"))
 def getjob(job):
  city,y,url=job;b=fetch(url,f'{city}-dvf-{y}.csv.gz');rows=parse_csv(gzip.decompress(b));ids={r['id_mutation'] for r in rows if r['code_commune'] in data[city]['codes']};subset=[r for r in rows if r['id_mutation'] in ids]
  tx,stats=normalize(subset);return city,y,tx,stats,url
 for city in data:data[city].update(transactions=[],audit={})
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  for city,y,tx,stats,url in pool.map(getjob,jobs):
   data[city]['transactions']+=tx;data[city]['audit'][str(y)]=stats
   source(f'{city}-dvf-{y}',f'DVF géolocalisées {y} — '+CONFIG[city]['name'],'DGFiP / data.gouv.fr','https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees',url,period=str(y),scale='mutation géolocalisée',method='Mutation unique, un logement distinct, surface positive ; exclusion multi-biens, prix ambigus et valeurs hors 200–15 000 €/m².',limits='Prix peut inclure des dépendances ; géolocalisation à la parcelle. Plusieurs locaux identiques peuvent rester indiscernables. Ni état, étage, ni DPE. Dernier fichier disponible vérifié au téléchargement.')
 renturl='https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144934/pred-app12-mef-dhup.csv'
 rentrows=parse_csv(fetch(renturl,'rent-app12-2025.csv'))
 variants={'app':('https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145010/pred-app-mef-dhup.csv','appartement toutes typologies, non meublé, 52 m²'), 'app3':('https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-144951/pred-app3-mef-dhup.csv','appartement 3 pièces et plus, non meublé, 72 m²'), 'maison':('https://static.data.gouv.fr/resources/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025/20251211-145039/pred-mai-mef-dhup.csv','maison non meublée, 92 m²'), 'app12':(renturl,'appartement 1–2 pièces, non meublé, 37 m²')}
 def getrent(pair):
  key,(url,template)=pair;return key,parse_csv(fetch(url,'rent-'+key+'-2025.csv')),template
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:rentvariants=list(pool.map(getrent,variants.items()))
 print('RENT COLUMNS',list(rentrows[0]),flush=True)
 for city,cfg in CONFIG.items():
  data[city]['rents']=[r for r in rentrows if any(str(v) in data[city]['codes'] for k,v in r.items() if k.lower() in ['insee_c','code_insee','insee','code_commune'])]
  for r in data[city]['rents']:
   for key in ['loypredm2','lwr.IPm2','upr.IPm2','nbobs_com','nbobs_mail','R2_adj']:r[key]=num(r.get(key))
  data[city]['rentReferences']={}
  for kind,rows,template in rentvariants:
   selected=[{**r,'template':template} for r in rows if r['INSEE_C'] in data[city]['codes']]
   for r in selected:
    for key in ['loypredm2','lwr.IPm2','upr.IPm2','nbobs_com','nbobs_mail','R2_adj']:r[key]=num(r.get(key))
   data[city]['rentReferences'][kind]=selected
  data[city].pop('codes');
  try:data[city]['transport']=gtfs(city,cfg)
  except Exception as e:
   data[city]['transport']=None;source(city+'-gtfs','GTFS '+cfg['name'],'Réseau local','https://transport.data.gouv.fr/datasets/'+cfg['gtfs'],status='indisponible',limits=str(e))
  (OUT/(city+'.json')).write_text(json.dumps(data[city],ensure_ascii=False,separators=(',',':')))
  print('SAVED',city,len(data[city]['transactions']),len(data[city]['rents']),flush=True)
 source('rent','Loyers d’annonce 1–2 pièces 2025','ANIL / Ministère du Logement','https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025',renturl,period='3e trimestre 2025',scale='commune',method='Modèle de loyers d’annonce, charges comprises, pour logement type 1–2 pièces. Valeurs originales et indicateurs de qualité conservés.',limits='Ni loyer HC, ni observation de quartier. Pas de conversion automatique en rendement. Millésimes non utilisés pour une tendance.',updated='2025-12-11')
 for key,(url,template) in variants.items():
  if key=='app12':continue
  source('rent-'+key,'Loyers d’annonce 2025 — '+template,'ANIL / Ministère du Logement','https://www.data.gouv.fr/datasets/carte-des-loyers-indicateurs-de-loyers-dannonce-par-commune-en-2025',url,period='3e trimestre 2025',scale='commune ou maille de communes',method='Estimation CC pour '+template,limits='Pas une moyenne ni un loyer de bail HC. Aucune extrapolation automatique par surface.',updated='2025-12-11')
 (OUT/'sources.json').write_text(json.dumps({'retrieved':NOW,'sources':SOURCES},ensure_ascii=False,indent=2))
if __name__=='__main__':run()
