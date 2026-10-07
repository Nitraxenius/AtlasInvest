"""Isolated per-source updates, bounded official discovery, and one release commit."""
import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import shutil
import time
import traceback
import uuid
from pathlib import Path
import xml.etree.ElementTree as ET
from scripts.collect import parse_csv, normalize, num
from service.download import Downloader, unzip
from service.store import Store, ROOT, FILES, config, now, encode
from service.transport import normalize as gtfs_normalize

KINDS = ('geo','dvf','gtfs','anil','oll','lovac','risks','documents','sitadel')

def dvf_years(listing):
    years=sorted(set(int(y) for y in re.findall(r'href=["\'][^"\']*?(20\d{2})/',listing)))[-5:]
    if not years:raise ValueError('No DVF vintages in official index')
    return years

def dataset(client, slug):
    return json.loads(client.fetch('https://www.data.gouv.fr/api/1/datasets/'+slug+'/', max_age=86400))

def discover(client, query, predicate):
    result=json.loads(client.fetch('https://www.data.gouv.fr/api/1/datasets/?page_size=20&q='+__import__('urllib.parse',fromlist=['quote']).quote(query),max_age=86400))
    matches=[d for d in result.get('data',[]) if predicate(d)]
    if not matches: raise ValueError('No matching official dataset')
    return max(matches,key=lambda d:d.get('last_modified') or '')

def provenance(kind, city, meta, resource, period, method, limits, client):
    record=next((r for r in reversed(client.records) if r['url']==resource['url']),{})
    return dict(id=city+'-'+kind if city else kind,title=meta.get('title',kind),producer=(meta.get('organization') or {}).get('name','Official source'),url='https://www.data.gouv.fr/datasets/'+meta['id'] if meta.get('id') else meta.get('url'),resource=resource['url'],resourceId=resource.get('id'),license=meta.get('license'),period=period,scale='agglomération / voir méthode',retrieved=now(),updated=resource.get('last_modified'),hash=record.get('sha256'),schemaVersion=1,method=method,limits=limits,status='importé')

def bounded_gunzip(body):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as f:
        value=f.read(220*1024*1024+1)
    if len(value)>220*1024*1024: raise ValueError('DVF decompression limit')
    return value

def run(store, selected=None, city=None, force=False, dry=False):
    selected=selected or list(KINDS); cfg=config()['cities']
    cities=[city] if city else list(cfg)
    if any(c not in cfg for c in cities) or any(s not in KINDS for s in selected): raise ValueError('Unknown source/city')
    if not store.current(): store.bootstrap()
    run_id=uuid.uuid4().hex; started=time.perf_counter(); errors=[]; results=[]
    with store.lock():
        with store.db() as db: db.execute('INSERT INTO runs VALUES(?,?,NULL,?,?)',(run_id,now(),'running','{}'))
        stage=store.path/'staging'/run_id; stage.mkdir()
        current=store.current()
        for name in FILES: shutil.copy2(store.file(name,current),stage/name)
        catalog=json.loads((stage/'sources.json').read_text(encoding='utf-8'))
        client=Downloader(store.path/'raw')
        client.force=force
        def record(source):
            catalog['sources']=[s for s in catalog['sources'] if s['id']!=source['id']]+[source]
        try:
            for c in cities:
                data=json.loads((stage/(c+'.json')).read_text(encoding='utf-8')); codes={f['properties']['code'] for f in data['communes']['features']}
                for kind in selected:
                    # Source updates operate on an independent copy. A failure cannot leak partial mutations.
                    candidate=json.loads(json.dumps(data)); before=len(client.records)
                    try:
                        sources=[]
                        if kind=='geo':
                            url=f"https://geo.api.gouv.fr/epcis/{cfg[c]['epci']}/communes?fields=nom,code,population,centre,contour&format=geojson&geometry=contour"
                            geo=json.loads(client.fetch(url,force=force,max_age=604800))
                            if cfg[c]['commune'] not in {f['properties']['code'] for f in geo['features']}: raise ValueError('Centre outside EPCI')
                            candidate['communes']=geo; candidate['config']=cfg[c]
                            codes={f['properties']['code'] for f in geo['features']}
                            sources=[dict(id=c+'-geo',title='Périmètre '+cfg[c]['name'],producer='API Découpage administratif',url=url,resource=url,license='Licence Ouverte 2.0',period='Référentiel courant',scale='commune',retrieved=now(),method='Périmètre EPCI officiel',limits='Contours administratifs, aucun quartier fictif',status='importé')]
                        elif kind=='dvf':
                            listing=client.fetch('https://files.data.gouv.fr/geo-dvf/latest/csv/',max_age=604800,force=force).decode()
                            years=dvf_years(listing)
                            tx=[]; audits={}; periods={}
                            for year in years:
                                url=f"https://files.data.gouv.fr/geo-dvf/latest/csv/{year}/departements/{cfg[c]['department']}.csv.gz"
                                rows=parse_csv(bounded_gunzip(client.fetch(url,force=force,max_age=604800)))
                                required={'id_mutation','code_commune','valeur_fonciere','date_mutation','surface_reelle_bati','longitude','latitude'}
                                if not rows or not required.issubset(rows[0]): raise ValueError('DVF schema changed')
                                ids={r['id_mutation'] for r in rows if r['code_commune'] in codes}
                                values,audit=normalize([r for r in rows if r['id_mutation'] in ids])
                                values=[t for t in values if t['code'] in codes]
                                tx+=values;audits[str(year)]=audit
                                max_date=max(r['date_mutation'] for r in rows)
                                periods[str(year)]={'lastObservation':max_date,'partial':max_date<f'{year}-12-01','hash':client.records[-1]['sha256']}
                                sources.append(provenance('dvf-'+str(year),c,{'title':'DVF géolocalisées '+str(year),'organization':{'name':'DGFiP / data.gouv.fr'},'url':'https://www.data.gouv.fr/datasets/demandes-de-valeurs-foncieres-geolocalisees','license':'Licence Ouverte 2.0'},{'url':url},str(year),'Mutation unique, un logement distinct, prix non additionné.','Dernière date observée ne prouve pas la complétude ; année partielle exclue des tendances.',client))
                            if not tx: raise ValueError('Empty DVF scope')
                            candidate.update(transactions=list({t['id']:t for t in tx}.values()),audit=audits,dvfPeriods=periods)
                        elif kind=='gtfs':
                            meta=dataset(client,cfg[c]['gtfs'])
                            resources=[r for r in meta['resources'] if str(r.get('format','')).lower() in ('gtfs','zip') and 'rt' not in r.get('title','').lower()]
                            if not resources: raise ValueError('No static GTFS resource')
                            res=max(resources,key=lambda r:r.get('last_modified') or '')
                            candidate['transport']=gtfs_normalize(client.fetch(res['url'],force=force))
                            sources=[provenance(kind,c,meta,res,'Calendriers GTFS','Services recalculés à la date consultée ; sens et horaires après minuit conservés.',candidate['transport']['limits'],client)]
                        elif kind=='anil':
                            meta=discover(client,'carte des loyers',lambda d:'carte des loyers' in d.get('title','').lower() and ('annonce' in d.get('title','').lower()))
                            refs={};period=re.search(r'20\d{2}',meta['title']);period=period.group() if period else 'Non indiqué'
                            for key,pattern in [('app12','app12'),('app3','app3'),('app','pred-app-mef'),('maison','pred-mai')]:
                                resources=[r for r in meta['resources'] if pattern in (r.get('url','')+' '+r.get('title','')).lower() and '.csv' in r.get('url','').lower()]
                                if not resources: raise ValueError('Missing ANIL typology '+key)
                                res=max(resources,key=lambda r:r.get('last_modified') or '')
                                rows=parse_csv(client.fetch(res['url'],force=force,max_age=604800))
                                if not rows or not {'INSEE_C','loypredm2','TYPPRED'}.issubset(rows[0]): raise ValueError('ANIL schema changed')
                                chosen=[r for r in rows if r['INSEE_C'] in codes]
                                if not chosen: raise ValueError('No ANIL values for scope')
                                for row in chosen:
                                    for field in ['loypredm2','lwr.IPm2','upr.IPm2','nbobs_com','nbobs_mail','R2_adj']: row[field]=num(row.get(field))
                                    row['template']=dict(app12='appartement 1–2 pièces non meublé 37 m²',app3='appartement 3+ pièces non meublé 72 m²',app='appartement non meublé 52 m²',maison='maison non meublée 92 m²')[key]
                                refs[key]=chosen
                                sources.append(provenance('anil-'+key,c,meta,res,period,'Modèle de loyer CC pour logement de référence.','Ni loyer HC ni tendance ; aucune extrapolation par surface.',client))
                            candidate.update(rents=refs['app12'],rentReferences=refs)
                        elif kind=='lovac':
                            meta=discover(client,'logements vacants du parc prive',lambda d:'logements vacants du parc priv' in d.get('title','').lower())
                            resources=[r for r in meta['resources'] if 'communes' in (r.get('title','')+r.get('url','').rsplit('/',1)[-1]).lower() and '.csv' in r.get('url','').lower()]
                            if not resources: raise ValueError('No LOVAC commune resource')
                            res=max(resources,key=lambda r:r.get('last_modified') or '')
                            rows=parse_csv(client.fetch(res['url'],force=force,max_age=604800))
                            fields=[k for k in rows[0] if re.search(r'codgeo|insee|code.*commune',k,re.I)]
                            if not fields: raise ValueError('Unknown LOVAC INSEE column')
                            candidate['lovac']=[r for r in rows if any(r[k] in codes for k in fields)]
                            if not candidate['lovac']: raise ValueError('No LOVAC scope rows')
                            sources=[provenance(kind,c,meta,res,meta['title'],'Valeurs originales et secret statistique conservés.','Vacance administrative, pas vacance locative investisseur.',client)]
                        elif kind=='oll':
                            meta=discover(client,'resultats observatoires locaux loyers agglomeration',lambda d:'observatoires locaux des loyers' in d.get('title','').lower())
                            resources=[r for r in meta['resources'] if 'L3700' in r.get('url','') and r.get('url','').endswith('.zip')]
                            if c!='tours':
                                resources=[r for r in meta['resources'] if 'Laval' in r.get('title','')]
                                if not resources:
                                    results.append({'city':c,'source':kind,'status':'not-covered','details':'Aucune couverture OLL Laval détectée dans ce catalogue officiel.'})
                                    continue
                                raise ValueError('New Laval OLL connector requires reviewed territory mapping')
                            if not resources: raise ValueError('No Tours OLL CSV/contours archive')
                            res=max(resources,key=lambda r:r.get('last_modified') or r['url'])
                            archive=unzip(client.fetch(res['url'],force=force,max_age=604800));csvname=next(n for n in archive.namelist() if n.startswith('Base_OP_') and n.endswith('.csv'));kmlname=next(n for n in archive.namelist() if 'zone_cal' in n and n.endswith('.kml'))
                            rows=parse_csv(archive.read(csvname));ns={'k':'http://www.opengis.net/kml/2.2'};features=[]
                            for row in rows:
                                for field in row:
                                    if field.startswith('loyer_') or field in ['surface_moyenne','nombre_observations','nombre_logements','moyenne_loyer_mensuel']:row[field]=num(row[field])
                            for place in ET.fromstring(archive.read(kmlname)).findall('.//k:Placemark',ns):
                                vals={r.attrib.get('name'):r.text for r in place.findall('.//k:SimpleData',ns)};polys=[]
                                for poly in place.findall('.//k:Polygon',ns):
                                    rings=[[[float(x) for x in pair.split(',')[:2]] for pair in coords.text.strip().split()] for coords in poly.findall('.//k:coordinates',ns)]
                                    if rings:polys.append(rings)
                                features.append({'type':'Feature','geometry':{'type':'MultiPolygon','coordinates':polys},'properties':{'id':vals['VAR4'],'name':'Zone OLL '+vals['VAR4'].split('.')[-1]}})
                            year=int(re.search(r'20\d{2}',csvname)[0]);candidate['oll']={'features':{'type':'FeatureCollection','features':features},'rows':rows,'year':year,'source':'https://www.data.gouv.fr/datasets/'+meta['id']}
                            sources=[provenance(kind,c,meta,res,str(year),'CSV et contours officiels du même zip.','HC observé ; secret conservé, pas interpolation de quartier.',client)]
                        elif kind=='risks':
                            url='https://www.georisques.gouv.fr/api/v1/gaspar/risques?code_insee='+cfg[c]['commune']
                            value=json.loads(client.fetch(url,force=force,max_age=604800))
                            if not isinstance(value.get('data'),list): raise ValueError('GASPAR response schema unavailable')
                            candidate['risks']=value
                            sources=[dict(id=c+'-risks',title='Risques communaux '+cfg[c]['name'],producer='Géorisques / BRGM',url='https://www.georisques.gouv.fr/',resource=url,license='Conditions Géorisques',period='Référentiel courant',scale='commune centre',retrieved=now(),status='importé',method='API GASPAR',limits='Pas un rapport de risque du bien ; aucune absence de risque déduite.')]
                        elif kind=='documents':
                            from service.documents import refresh
                            candidate['documents']=refresh(c,client,store)
                            for error in candidate['documents']['errors']:errors.append({'city':c,'source':'document:'+error['id'],'error':error['error'],'retainedVersion':current})
                        elif kind=='sitadel':
                            from service.permits import refresh
                            meta=dataset(client,'liste-des-permis-de-construire-et-autres-autorisations-durbanisme')
                            points,res,failures=refresh(c,cfg[c],codes,client,meta)
                            existing=json.loads((stage/'points.json').read_text(encoding='utf-8'))
                            failed={r['id'] for r in failures}
                            preserved=[p for p in existing if p['city']!=c or p['kind']!='housing' or p['id'] in failed]
                            proposed=preserved+points
                            candidate['sitadelFailures']=failures
                            sources=[provenance(kind,c,meta,res,'Autorisations depuis 2023','Toutes lignes de la commune centre ; carte au moins 20 logements ; états 2/5/6. Géocodage IGN borné.','Commune centre seulement, pas EPCI complet. Livraison non confirmée sans preuve.',client)]
                            for error in failures:errors.append({'city':c,'source':'geocode:'+error['id'],'error':error['error'],'retainedVersion':current})
                        # Preserve idempotence: identical resources do not change provenance timestamps.
                        hashes=[r.get('sha256') for r in client.records[before:]]
                        fingerprint=hashlib.sha256(encode(hashes)).hexdigest()
                        old=data.get('connectorHashes',{}).get(kind)
                        if old!=fingerprint:
                            candidate.setdefault('connectorHashes',{})[kind]=fingerprint
                            data=candidate
                            for source in sources: record(source)
                            if kind=='sitadel':(stage/'points.json').write_bytes(encode(proposed))
                        results.append({'city':c,'source':kind,'status':'unchanged' if old==fingerprint else 'validated','hash':fingerprint})
                    except Exception as error:
                        errors.append({'city':c,'source':kind,'error':str(error)[:300],'retainedVersion':current})
                (stage/(c+'.json')).write_bytes(encode(data))
            # Status lives in runs, so an unchanged/failed run cannot create a false data publication.
            if any(r['status']=='validated' for r in results):catalog['retrieved']=now()
            (stage/'sources.json').write_bytes(encode(catalog))
            store.validate(stage)
            if dry: version,changed=current,False
            else: version,changed=store.promote(stage,{'run':run_id,'errors':errors,'results':results})
            if not dry:store.prune(config()['schedule']['retention'])
            outcome={'run':run_id,'version':version,'changed':changed,'dryRun':dry,'errors':errors,'results':results,'seconds':round(time.perf_counter()-started,2)}
            with store.db() as db: db.execute('UPDATE runs SET finished=?,status=?,details=? WHERE id=?',(now(),'partial' if errors else 'success',encode(outcome).decode(),run_id))
            return outcome
        except Exception as error:
            with store.db() as db: db.execute('UPDATE runs SET finished=?,status=?,details=? WHERE id=?',(now(),'failed',encode({'error':str(error)}).decode(),run_id))
            raise
        finally: shutil.rmtree(stage)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',action='append',choices=KINDS);parser.add_argument('--city',choices=list(config()['cities']));parser.add_argument('--force',action='store_true');parser.add_argument('--dry-run',action='store_true')
    args=parser.parse_args();print(json.dumps(run(Store(),args.source,args.city,args.force,args.dry_run),ensure_ascii=False))
