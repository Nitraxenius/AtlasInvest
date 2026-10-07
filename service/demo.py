"""Isolated synthetic fixture release, never an import into production state."""
import argparse
import shutil
import uuid
from service.store import Store, config, encode

def publish(store, generation):
    if 'fixture' not in str(store.path):raise ValueError('Demo requires a separate state path containing fixture')
    with store.lock():
        stage=store.path/'staging'/uuid.uuid4().hex;stage.mkdir()
        try:
            points=[]
            for city,cfg in config()['cities'].items():
                lon,lat=cfg['center'];tx=[]
                for i in range(12):
                    tx.append(dict(id=f'fixture-{city}-{i}',date='2025-03-01',price=100000+generation*1000,area=40,rooms=2,type='Appartement',nature='Vente',code=cfg['commune'],commune='Fixture '+cfg['name'],address='RUE FIXTURE SYNTHÉTIQUE',lon=lon+.001+i*.00001,lat=lat+.001,ppm=(100000+generation*1000)/40,dependencies=False))
                points.append(dict(id='fixture-campus-'+city,city=city,name='Campus synthétique de test',kind='campus',lon=lon+.002,lat=lat+.002,address='Fixture',source='https://www.data.gouv.fr/',precision='fixture'))
                geometry={'type':'Polygon','coordinates':[[[lon-.02,lat-.02],[lon+.02,lat-.02],[lon+.02,lat+.02],[lon-.02,lat+.02],[lon-.02,lat-.02]]]}
                data=dict(config=cfg,communes={'type':'FeatureCollection','features':[{'type':'Feature','geometry':geometry,'properties':{'code':cfg['commune'],'nom':'Fixture synthétique'}}]},transactions=tx,rents=[],audit={'2025':{'rawRows':12,'mutations':12,'accepted':12,'excluded':{}}},dvfPeriods={'2025':{'partial':False}},transport={'stops':{'type':'FeatureCollection','features':[]},'lines':{'type':'FeatureCollection','features':[]},'routes':{}},fixtureGeneration=generation)
                (stage/(city+'.json')).write_bytes(encode(data))
            (stage/'points.json').write_bytes(encode(points))
            (stage/'sources.json').write_bytes(encode({'retrieved':'2026-10-07','sources':[dict(id='fixture',title=f'Fixture contrôlée génération {generation}',url='https://www.data.gouv.fr/',producer='Test Atlas',period='scénario synthétique',scale='fixture',license='Test',method='Aucune donnée réelle modifiée',limits='Contours et ventes synthétiques, aucune valeur de marché.',status='fixture',hash=str(generation))]}))
            return store.promote(stage,{'syntheticFixture':True,'generation':generation})
        finally:shutil.rmtree(stage)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['serve','publish']);parser.add_argument('--generation',type=int,default=1);args=parser.parse_args();store=Store()
    if args.action=='publish':print(publish(store,args.generation))
    else:
        if not store.current():publish(store,1)
        from service.api import serve
        serve(store)
