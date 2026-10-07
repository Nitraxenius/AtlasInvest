"""Bounded Sitadel centre-commune connector, preserving deterministic status interpretation."""
import json
import time
from urllib.parse import quote
from scripts.collect import num

def refresh(city,cfg,codes,client,meta):
    resources=[r for r in meta['resources'] if r.get('format')=='csv' and 'créant des logements' in r.get('title','').lower()]
    if not resources:raise ValueError('No Sitadel housing resource')
    res=max(resources,key=lambda r:r.get('last_modified') or '')
    rows=[]
    for page in range(1,101):
        url=f"https://tabular-api.data.gouv.fr/api/resources/{res['id']}/data/?COMM__exact={cfg['commune']}&page_size=100&page={page}"
        value=json.loads(client.fetch(url,max_age=604800));batch=value.get('data')
        if not isinstance(batch,list):raise ValueError('Sitadel schema changed')
        rows.extend(batch)
        if len(batch)<100:break
    else:raise ValueError('Sitadel pagination limit')
    if not rows or not {'NUM_DAU','COMM','ETAT_DAU','NB_LGT_TOT_CREES','DATE_REELLE_AUTORISATION'}.issubset(rows[0]):raise ValueError('Invalid/empty Sitadel response')
    points=[];failures=[]
    for row in rows:
        if str(row['COMM'])!=cfg['commune']:raise ValueError('Sitadel outside requested centre')
        if (row.get('DATE_REELLE_AUTORISATION') or '')<'2023-01-01' or (num(row['NB_LGT_TOT_CREES']) or 0)<20 or row['ETAT_DAU'] not in [2,5,6]:continue
        address=' '.join(str(row.get(k) or '') for k in ['ADR_NUM_TER','ADR_LIBVOIE_TER','ADR_LOCALITE_TER','ADR_CODPOST_TER']).strip()
        if not row.get('ADR_LIBVOIE_TER'):continue
        try:
            response=json.loads(client.fetch('https://data.geopf.fr/geocodage/search?limit=1&q='+quote(address),max_age=30*86400))
            feature=response['features'][0]
            if feature['properties'].get('citycode') not in codes:raise ValueError('Geocode outside EPCI')
            lon,lat=feature['geometry']['coordinates']
            if not -6<lon<10 or not 41<lat<52:raise ValueError('Invalid coordinates')
            status={2:'autorisé',5:'commencé dans Sitadel',6:'terminé dans Sitadel'}[row['ETAT_DAU']]
            points.append(dict(id=row['NUM_DAU'],city=city,kind='housing',name='Programme de logements · '+str(row['NB_LGT_TOT_CREES'])+' logements',lon=lon,lat=lat,address=address,precision=feature['properties'].get('type'),geocodeScore=feature['properties'].get('score'),source='https://www.data.gouv.fr/datasets/'+meta['id'],status=status,capacity=row['NB_LGT_TOT_CREES'],year=None,description=f"Permis {row['NUM_DAU']}, autorisation {row.get('DATE_REELLE_AUTORISATION')}. Livraison non confirmée. Offre potentielle, aucune demande supplémentaire déduite.",permit=row))
        except Exception as error:failures.append({'id':row['NUM_DAU'],'error':str(error)[:160]})
        time.sleep(.15)
    return points,res,failures
