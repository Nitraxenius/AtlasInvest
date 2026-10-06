"""Loyers observés OLL et vacance résidentielle LOVAC (pas vacance locative)."""
from collect import *
import xml.etree.ElementTree as ET
def run():
 catalog=json.loads((OUT/'sources.json').read_text())
 z=zipfile.ZipFile(io.BytesIO(fetch('https://www.observatoires-des-loyers.org/datagouv/2024/Base_OP_2024_L3700.zip','oll-tours-2024.zip')))
 rs=parse_csv(z.read('Base_OP_2024_L3700.csv'))
 for r in rs:
  for k in r:
   if k.startswith('loyer_') or k in ['moyenne_loyer_mensuel','surface_moyenne','nombre_observations','nombre_logements']:r[k]=num(r[k])
 ns={'k':'http://www.opengis.net/kml/2.2'};root=ET.fromstring(z.read('L3700_zone_cal_2024_1.kml'));features=[]
 for place in root.findall('.//k:Placemark',ns):
  vals={r.attrib.get('name'):r.text for r in place.findall('.//k:SimpleData',ns)};polys=[]
  for poly in place.findall('.//k:Polygon',ns):
   rings=[]
   for coords in poly.findall('.//k:coordinates',ns):rings.append([[float(x) for x in pair.split(',')[:2]] for pair in coords.text.strip().split()])
   if rings:polys.append(rings)
  features.append({'type':'Feature','geometry':{'type':'MultiPolygon','coordinates':polys},'properties':{'id':vals['VAR4'],'name':'Zone OLL '+vals['VAR4'].split('.')[-1]}})
 data=json.loads((OUT/'tours.json').read_text());data['oll']={'features':{'type':'FeatureCollection','features':features},'rows':rs,'year':2024,'source':'https://www.data.gouv.fr/datasets/resultats-des-observatoires-locaux-des-loyers-par-agglomeration'};(OUT/'tours.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 catalog['sources'].append(dict(id='tours-oll',title='Loyers observés Tours — zones OLL 2024',producer='Observatoire local des loyers / ANIL',url=data['oll']['source'],resource='https://www.observatoires-des-loyers.org/datagouv/2024/Base_OP_2024_L3700.zip',license='Licence Ouverte ; attribution OLL / ANIL',retrieved=NOW,period='2024',scale='3 zones OLL ; typologie et ancienneté locataire',method='Polygones KML officiels ; statistiques HC par zone et type de logement. Aucun découpage fictif par quartier.',limits='Stock locatif observé, pas prédiction d’un nouveau bail. Population des biens différente d’ANIL. Les loyers mensuels concernent des surfaces moyennes différentes.',status='importé'))
 for city in CONFIG:
  catalog['sources'].append(dict(id=city+'-risks',title='Risques — '+CONFIG[city]['name'],producer='Géorisques / BRGM',url='https://www.georisques.gouv.fr/',resource='https://www.georisques.gouv.fr/api/v1/gaspar/risques?code_insee='+('53130' if city=='laval' else '37261'),license='Conditions Géorisques',retrieved=NOW,period='tentative du '+NOW[:10],scale='commune',method='Interrogation API GASPAR v1.',limits='La récupération a échoué (HTTP 502). Aucun score de risque ni absence de risque déduite. Consulter le rapport officiel à l’adresse.',status='indisponible'))
 lovac=json.loads((RAW/'lovac-meta.json').read_text());res=next(r for r in lovac['resources'] if 'Communes.csv' in r['title']);rs=parse_csv(fetch(res['url'],'lovac-2026.csv'));print('LOVAC FIELDS',list(rs[0]),flush=True)
 for city in CONFIG:
  d=json.loads((OUT/(city+'.json')).read_text());codes={f['properties']['code'] for f in d['communes']['features']}
  d['lovac']=[r for r in rs if any(str(v) in codes for k,v in r.items() if 'code' in k.lower() or 'insee' in k.lower() or k=='CODGEO_26')]
  (OUT/(city+'.json')).write_text(json.dumps(d,ensure_ascii=False,separators=(',',':')))
 catalog['sources'].append(dict(id='lovac',title='Vacance du parc privé LOVAC 2026',producer='Ministère du Logement / Zéro logement vacant',url='https://www.data.gouv.fr/datasets/logements-vacants-du-parc-prive-par-commune-departement-region-france-de-2020-a-2026',resource=res['url'],license=str(lovac.get('license')),retrieved=NOW,updated=res.get('last_modified'),period='2020–2026',scale='commune',method='Filtrage des codes des agglomérations ; valeurs originales et secret statistique conservés.',limits='Vacance résidentielle administrative ; ne mesure pas les semaines sans locataire d’un investissement. Données secrétisées non remplacées par zéro.',status='importé'))
 if (RAW/'osm-services.json').exists():
  j=json.loads((RAW/'osm-services.json').read_text());points=json.loads((OUT/'points.json').read_text())
  for element in j.get('elements',[]):
   pos=element.get('center',element);tags=element.get('tags',{});city='laval' if pos['lat']>48 else 'tours'
   points.append(dict(id='osm-'+element['type']+'-'+str(element['id']),name=tags.get('name','Gare' if tags.get('railway')=='station' else 'Supermarché'),city=city,kind='service',lon=pos['lon'],lat=pos['lat'],address=tags.get('addr:street',''),precision='point ou centre de géométrie OSM',source=f"https://www.openstreetmap.org/{element['type']}/{element['id']}",description='Gare' if tags.get('railway')=='station' else 'Commerce alimentaire ; renseignement OpenStreetMap à vérifier sur place.'))
  (OUT/'points.json').write_text(json.dumps(list({p['id']:p for p in points}.values()),ensure_ascii=False,indent=2))
  catalog['sources'].append(dict(id='osm-services',title='Gares et commerces alimentaires',producer='Contributeurs OpenStreetMap',url='https://www.openstreetmap.org/copyright',resource='https://overpass-api.de/',license='ODbL',retrieved=NOW,period=j.get('osm3s',{}).get('timestamp_osm_base'),scale='points et centres de bâtiments',method='Extraction Overpass des gares et supermarchés dans les emprises centrales des deux villes.',limits='Inventaire contributif non exhaustif ; périmètre de collecte limité autour des villes centres, pas aux EPCI entiers.',status='importé'))
 catalog['sources'].append(dict(id='laval-oll',title='Loyers observés Laval',producer='Réseau OLL / ANIL',url='https://www.data.gouv.fr/datasets/resultats-nationaux-des-observatoires-locaux-des-loyers',resource='https://www.observatoires-des-loyers.org/datagouv/2024/Base_OP_2024_Nationale.csv',license='Licence Ouverte',retrieved=NOW,period='fichiers 2024 et 2025 consultés',scale='agglomération',method='Recherche du territoire dans les fichiers nationaux et ressources locales.',limits='Aucun résultat lavallois trouvé dans ces fichiers. Utiliser uniquement la référence ANIL avec ses limites.',status='non trouvé'))
 catalog['sources']=list({x['id']:x for x in catalog['sources']}.values())
 (OUT/'sources.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
if __name__=='__main__':run()
