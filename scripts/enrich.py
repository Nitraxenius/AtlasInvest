"""Rechercher les compléments territoriaux et conserver leurs sources."""
from collect import *
from urllib.parse import quote
POINTS=[
 dict(id='esiea',name='ESIEA Laval',city='laval',kind='campus',address='38 rue des Docteurs Calmette et Guérin Laval',source='https://openlab.esiea.fr/',description='École d’ingénieurs du numérique. Effectif local non intégré.'),
 dict(id='estaca',name='ESTACA Laval',city='laval',kind='campus',address='Rue Georges Charpak Changé 53810',source='https://www.estaca.fr/contact/',description='École d’ingénieurs spécialisée dans les transports. Capacité et effectif non utilisés pour prédire la demande.'),
 dict(id='iut-laval',name='IUT Laval',city='laval',kind='campus',address='52 rue des Docteurs Calmette et Guérin Laval',source='https://www.laval.fr/annuaire-structures/institut-universitaire-de-technologie-iut-laval-7835',description='Institut universitaire de technologie ; adresse confirmée par l’annuaire de la Ville de Laval.'),
 dict(id='ferrie',name='Pôle santé-social Ferrié',city='laval',kind='campus',address='65 rue du Chef de Bataillon Henri Géret Laval',source='https://www.chlaval.fr/app/uploads/2025/12/LIVRET-JPO-26.pdf',description='Instituts de formation du pôle santé-social ; effectif non intégré.'),
 dict(id='tanneurs',name='Université · Tanneurs',city='tours',kind='campus',address='3 rue des Tanneurs Tours',source='https://www.univ-tours.fr/plans-dacces/site-des-tanneurs',description='Site universitaire des Tanneurs.'),
 dict(id='portalis',name='Université · Deux-Lions',city='tours',kind='campus',address='50 avenue Jean Portalis Tours',source='https://www.univ-tours.fr/plans-dacces/site-deux-lions',description='Site Deux-Lions / Portalis.'),
 dict(id='grandmont',name='Université · Grandmont',city='tours',kind='campus',address='Avenue Monge Tours',source='https://sciences.univ-tours.fr/version-francaise/presentation/plan-dacces',description='Sciences et techniques ; point indicatif sur l’avenue du campus.'),
 dict(id='uco-future',name='Nouveau bâtiment UCO',city='laval',kind='project',address='Rue Marie Curie Changé 53810',source='https://www.agglo-laval.fr/autres/actualites/un-nouveau-batiment-pour-lenseignement-superieur-12691',status='chantier annoncé par la collectivité',year=2027,capacity=600,description='Ouverture prévue rentrée 2027. Capacité annoncée : jusqu’à 600 étudiants. Il s’agit aussi d’un transfert du campus existant, pas de 600 étudiants supplémentaires.'),
 dict(id='saint-sauveur',name='Campus Saint-Sauveur',city='tours',kind='project',address='Rue Auguste Chevallier Tours',source='https://www.esrre.fr/campus/campus-saint-sauveur',status='commercialisation / permis modificatif en cours',year=2028,capacity=946,description='Campus de 3 900 m² annoncé pour l’été 2028. Capacité ERP déclarative de 946 personnes ; établissements occupants et effectifs futurs non confirmés.'),
 dict(id='ch-laval',name='Centre hospitalier de Laval',city='laval',kind='employment',address='33 rue du Haut Rocher Laval',source='https://www.chlaval.fr/venir-a-lhopital/',description='Site principal du centre hospitalier. Effectif de salariés non intégré.'),
 dict(id='trousseau',name='CHU Trousseau',city='tours',kind='employment',address='Avenue de la République Chambray-lès-Tours',source='https://www.chu-tours.fr/?page_id=44',description='Site hospitalier. Point indicatif au niveau de l’avenue ; effectif non intégré.'),
 dict(id='tram2',name='Tramway T2 · repère Grandmont',city='tours',kind='project',address='Avenue Monge Tours',source='https://lignes2tram.fr/les-nouvelles-lignes/la-ligne-2-de-tramway/',status='projet en travaux / échéance annoncée',year=2028,description='Ligne 2 annoncée à horizon 2028, desservant notamment Grandmont, Bretonneau et Trousseau. Repère au campus, pas une station ni un tracé géométrique certifié.'),
]
def geocode(p):
 try:
  j=json.loads(fetch('https://data.geopf.fr/geocodage/search?q='+quote(p.get('geocodeAddress',p['address']))+'&limit=1','geo-'+p['id']+'.json'))
  f=j['features'][0]
  config=CONFIG[p['city']];codes={x['properties']['code'] for x in json.loads((OUT/(p['city']+'.json')).read_text())['communes']['features']}
  if f['properties'].get('citycode') not in codes:raise ValueError('Géocodage hors agglomération, rejeté')
  p.update(lon=f['geometry']['coordinates'][0],lat=f['geometry']['coordinates'][1],precision=f['properties'].get('type','géocodage'),geocodeLabel=f['properties'].get('label'),geocodeScore=f['properties'].get('score'),verified=NOW[:10]);return p
 except Exception as e:print('GEOCODE FAILED',p['id'],str(e),flush=True);return None
def permits(city):
 code='53130' if city=='laval' else '37261';allrows=[];page=1
 while True:
  url=f'https://tabular-api.data.gouv.fr/api/resources/65a9e264-7a20-46a9-9d98-66becb817bc3/data/?COMM__exact={code}&page_size=100&page={page}'
  j=json.loads(fetch(url,f'sitadel-{city}-{page}.json'));rows=j.get('data',[]);allrows+=rows
  total=j.get('meta',{}).get('total',j.get('meta',{}).get('total_rows',0))
  if len(rows)<100 or (total and len(allrows)>=total):break
  page+=1
 (OUT/(city+'-permits.json')).write_text(json.dumps(allrows,ensure_ascii=False))
 ps=[]
 for r in allrows:
  if (r.get('DATE_REELLE_AUTORISATION') or '')<'2023-01-01' or (r.get('NB_LGT_TOT_CREES') or 0)<20 or r.get('ETAT_DAU') not in [2,5,6]:continue
  address=' '.join(str(r.get(k) or '') for k in ['ADR_NUM_TER','ADR_LIBVOIE_TER','ADR_LOCALITE_TER','ADR_CODPOST_TER']).strip()
  if not r.get('ADR_LIBVOIE_TER'):continue
  status='terminé dans Sitadel' if r.get('ETAT_DAU')==6 else 'commencé dans Sitadel' if r.get('ETAT_DAU')==5 else 'autorisé'
  student=r.get('RES_ETUDIANTS') in [True,'True','true','1']
  ps.append(dict(id=r['NUM_DAU'],name=('Résidence étudiante' if student else 'Programme de logements')+' · '+str(r['NB_LGT_TOT_CREES'])+' logements',city=city,kind='housing',address=address,source='https://www.data.gouv.fr/datasets/liste-des-permis-de-construire-et-autres-autorisations-durbanisme',status=status,year=None,capacity=r['NB_LGT_TOT_CREES'],description=f"Permis {r['NUM_DAU']} autorisé le {r.get('DATE_REELLE_AUTORISATION')}. {r['NB_LGT_TOT_CREES']} logements déclarés. Étudiant : {'oui' if student else 'non'}. DOC : {r.get('DATE_REELLE_DOC') or 'non renseignée'}. Livraison non confirmée. Offre nouvelle potentiellement concurrente.",permit=r))
 print('PERMITS',city,len(allrows),len(ps),flush=True);return ps
def run():
 sources=json.loads((OUT/'sources.json').read_text());jobs=list(POINTS)
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  for ps in pool.map(permits,CONFIG):jobs+=ps
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
  ps=[p for p in pool.map(geocode,jobs) if p is not None]
 (OUT/'points.json').write_text(json.dumps(ps,ensure_ascii=False,indent=2))
 for p in POINTS:
  sources['sources'].append(dict(id=p['id'],title=p['name'],producer='Établissement / porteur du projet',url=p['source'],resource='',license='Résumé factuel ; document source sous ses conditions propres',retrieved=NOW,period=str(p.get('year') or 'site existant'),scale='adresse ou rue',method='Adresse publiée, géocodage IGN ; résumé des caractéristiques publiques.',limits=p.get('description'),status='vérifié / géocodé'))
 for city in CONFIG:
  sources['sources'].append(dict(id=city+'-sitadel',title='Permis de logements — '+CONFIG[city]['name'],producer='SDES / Sitadel',url='https://www.data.gouv.fr/datasets/liste-des-permis-de-construire-et-autres-autorisations-durbanisme',resource='https://tabular-api.data.gouv.fr/api/resources/65a9e264-7a20-46a9-9d98-66becb817bc3/data/?COMM__exact='+('53130' if city=='laval' else '37261'),license='Licence Ouverte 2.0',retrieved=NOW,period='autorisations depuis 2023',scale='commune centre uniquement',method='Toutes lignes de la commune récupérées. Carte : au moins 20 logements, état autorisé/chantier/achevé, adresse disponible.',limits='Périmètre permis limité à la commune centre ; calendrier et effectifs non prédits. Coordonnées géocodées parfois au milieu de la rue. État chantier fondé sur DOC, livraison seulement avec DAACT.',status='importé'))
 sources['sources']=list({x['id']:x for x in sources['sources']}.values())
 (OUT/'sources.json').write_text(json.dumps(sources,ensure_ascii=False,indent=2))
 print('POINTS',len(ps),flush=True)
if __name__=='__main__':run()
