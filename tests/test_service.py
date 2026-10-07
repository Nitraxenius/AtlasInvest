import contextlib
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import zipfile
from zoneinfo import ZoneInfo
from service.store import Store, encode, config
from service.pipeline import run, dvf_years
from scripts.collect import parse_csv
from service.download import Downloader, safe_url, unzip
from service.transport import active_services, normalize, at_date
from service.scheduler import due
from service.documents import validate, extract
from service.api import Handler, ThreadingHTTPServer

def fixture(directory):
    directory.mkdir(exist_ok=True)
    for city,cfg in config()['cities'].items():
        value={'config':cfg,'communes':{'type':'FeatureCollection','features':[{'type':'Feature','properties':{'code':cfg['commune']},'geometry':{'type':'Polygon','coordinates':[[[-1,47],[1,47],[1,49],[-1,49],[-1,47]]]}}]},'transactions':[{'id':city+'-1','code':cfg['commune'],'lon':cfg['center'][0],'lat':cfg['center'][1],'area':40,'price':100000,'ppm':2500,'date':'2025-03-01','type':'Appartement','nature':'Vente','rooms':2,'address':'TEST'}],'audit':{'2025':{'rawRows':1,'mutations':1,'accepted':1,'excluded':{}}},'rents':[]}
        (directory/(city+'.json')).write_bytes(encode(value))
    (directory/'sources.json').write_bytes(encode({'retrieved':'2025-01-01','sources':[{'id':'fixture','url':'https://www.data.gouv.fr/','period':'2025','scale':'fixture'}]}))
    (directory/'points.json').write_bytes(encode([]))
    return directory

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.store=Store(self.root/'live');self.stage=fixture(self.root/'stage');self.v1,_=self.store.promote(self.stage)
    def tearDown(self):self.temp.cleanup()
    def test_hash_idempotent(self):
        version,changed=self.store.promote(self.stage);self.assertEqual(version,self.v1);self.assertFalse(changed)
    def test_atomic_invalid_release(self):
        data=json.loads((self.stage/'laval.json').read_bytes());data['transactions'][0]['area']=0;(self.stage/'laval.json').write_bytes(encode(data))
        with self.assertRaises(ValueError):self.store.promote(self.stage)
        self.assertEqual(self.store.current(),self.v1);self.assertTrue(self.store.file('laval.json').exists())
    def test_duplicates_rejected(self):
        data=json.loads((self.stage/'laval.json').read_bytes());data['transactions']*=2;(self.stage/'laval.json').write_bytes(encode(data))
        with self.assertRaises(ValueError):self.store.promote(self.stage)
    def test_invalid_geometry_preserves_release(self):
        data=json.loads((self.stage/'laval.json').read_bytes());data['communes']['features'][0]['geometry']['coordinates'][0][0]=[250,47];(self.stage/'laval.json').write_bytes(encode(data))
        with self.assertRaises(ValueError):self.store.promote(self.stage)
        self.assertEqual(self.store.current(),self.v1)
    def test_lock_and_recovery(self):
        with self.store.lock():
            with self.assertRaises(RuntimeError):
                with self.store.lock():pass
        with self.store.db() as db:db.execute('INSERT INTO locks VALUES(?,?,?)',('pipeline','crashed',time.time()-1))
        with self.store.lock():pass
    def test_backup_restore_rollback(self):
        backup=self.store.backup(self.root/'backup');restored_path=self.root/'restore';shutil.copytree(backup,restored_path)
        restored=Store(restored_path);self.assertEqual(restored.current(),self.v1);restored.rollback(self.v1)
        data=json.loads((self.stage/'sources.json').read_bytes());data['sources'][0]['period']='2026';(self.stage/'sources.json').write_bytes(encode(data));v2,_=self.store.promote(self.stage)
        self.store.rollback(self.v1);self.assertEqual(self.store.current(),self.v1);self.assertNotEqual(v2,self.v1)
    def test_failure_keeps_last_source(self):
        class Failure:
            records=[]
            def __init__(self,*a):pass
            def fetch(self,*a,**kw):raise TimeoutError('fixture timeout')
        with patch('service.pipeline.Downloader',Failure):out=run(self.store,['geo'])
        self.assertEqual(out['version'],self.v1);self.assertFalse(out['changed']);self.assertEqual(len(out['errors']),2)
    def test_two_syncs_idempotent_and_new_resource(self):
        class Fake:
            def __init__(self,*args):self.records=[]
            def fetch(self,url,**kwargs):
                city='laval' if '200083392' in url else 'tours';data=json.loads((self_outer.stage/(city+'.json')).read_bytes())['communes'];body=encode(data)
                self.records.append({'url':url,'sha256':hashlib.sha256(body).hexdigest()});return body
        self_outer=self
        with patch('service.pipeline.Downloader',Fake):
            first=run(self.store,['geo']);second=run(self.store,['geo']);self.assertTrue(first['changed']);self.assertFalse(second['changed']);self.assertEqual(first['version'],second['version'])
    def test_http_version_pin_pagination_and_admin(self):
        Handler.store=self.store;server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(json.load(urllib.request.urlopen(base+'/api/v1/manifest'))['version'],self.v1)
            value=json.load(urllib.request.urlopen(base+f'/api/v1/versions/{self.v1}/laval/transactions?limit=1'));self.assertEqual(len(value['items']),1)
            for route in ['/api/v1/admin/sync',f'/api/v1/versions/{self.v1}/laval/transactions?limit=1001','/api/v1/versions/../../atlas.sqlite']:
                with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+route)
        finally:server.shutdown();server.server_close();thread.join()

class TransportTests(unittest.TestCase):
    def gtfs(self):
        files={'stops.txt':'stop_id,stop_name,stop_lat,stop_lon\nstop:a,Test,48.076,-0.77\n','routes.txt':'route_id,route_short_name,route_type\nroute:a,A,3\n','trips.txt':'route_id,service_id,trip_id,direction_id\nroute:a,svc:a,trip:a,0\nroute:a,svc:b,trip:b,1\n','stop_times.txt':'trip_id,stop_id,departure_time\ntrip:a,stop:a,25:15:00\ntrip:b,stop:a,07:30:00\n','calendar_dates.txt':'service_id,date,exception_type\nsvc:a,20261007,1\nsvc:b,20261007,1\nsvc:a,20261008,2\n'}
        body=io.BytesIO()
        with zipfile.ZipFile(body,'w') as z:
            for name,text in files.items():z.writestr(name,text)
        return body.getvalue()
    def test_colon_ids_midnight_directions_exceptions_no_shapes(self):
        transport=normalize(self.gtfs());first=at_date(transport,'2026-10-07');self.assertEqual(first['activeServices'],2)
        self.assertEqual(first['stops']['features'][0]['properties']['departures'],[[450,'route:a','1'],[1515,'route:a','0']]);self.assertFalse(first['shapesAvailable']);self.assertEqual(first['lines']['features'],[])
        second=at_date(transport,'2026-10-08');self.assertEqual(second['stops']['features'][0]['properties']['departures'],[])
    def test_weekday_and_exception(self):
        calendar=[{'service_id':'a','start_date':'20260101','end_date':'20261231','wednesday':'1'}]
        self.assertEqual(active_services(calendar,[],'2026-10-07'),{'a'})
        self.assertEqual(active_services(calendar,[{'service_id':'a','date':'20261007','exception_type':'2'}],'2026-10-07'),set())
    def test_decompression_limit(self):
        with self.assertRaises(ValueError):unzip(self.gtfs(),10)

class DownloadTests(unittest.TestCase):
    def test_new_vintage_without_code_change(self):
        listing=''.join(f'<a href="/geo-dvf/latest/csv/{y}/">{y}</a>' for y in range(2021,2027))
        self.assertEqual(dvf_years(listing),[2022,2023,2024,2025,2026])
    def test_csv_encodings_and_secrets(self):
        self.assertEqual(parse_csv('code;valeur\n53130;Secret statistique\n'.encode('utf-8-sig'))[0]['valeur'],'Secret statistique')
        self.assertEqual(parse_csv('code;nom\n53130;Laval é\n'.encode('cp1252'))[0]['nom'],'Laval é')
        with self.assertRaises(ValueError):parse_csv(b'')
    def test_conditional_download_304(self):
        class Response(io.BytesIO):
            headers={'Content-Length':'3','ETag':'fixture-v1'};url='https://www.data.gouv.fr/test'
        with tempfile.TemporaryDirectory() as temp:
            client=Downloader(temp)
            with patch('service.download.safe_url',side_effect=lambda x:x),patch.object(client.opener,'open',return_value=Response(b'abc')):self.assertEqual(client.fetch(Response.url),b'abc')
            error=urllib.error.HTTPError(Response.url,304,'unchanged',{},None)
            with patch('service.download.safe_url',side_effect=lambda x:x),patch.object(client.opener,'open',side_effect=error) as request:
                self.assertEqual(client.fetch(Response.url,max_age=0),b'abc');self.assertEqual(request.call_args[0][0].get_header('If-none-match'),'fixture-v1')
    def test_private_or_unapproved_rejected(self):
        for url in ['http://www.data.gouv.fr/test','https://127.0.0.1/test','https://www.data.gouv.fr@127.0.0.1/','https://example.com/test']:
            with self.assertRaises(ValueError):safe_url(url)
        with patch('service.download.socket.getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]):
            with self.assertRaises(ValueError):safe_url('https://www.data.gouv.fr/test')
    def test_truncated_download_does_not_replace_cache(self):
        class Response(io.BytesIO):
            headers={'Content-Length':'100'};url='https://www.data.gouv.fr/test'
        with tempfile.TemporaryDirectory() as temp:
            client=Downloader(temp)
            with patch('service.download.safe_url',side_effect=lambda x:x),patch.object(client.opener,'open',return_value=Response(b'abc')):
                with self.assertRaises(ValueError):client.fetch(Response.url)
            self.assertFalse(list(Path(temp).glob('*.bin')))
    def test_http_retry_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            client=Downloader(temp);error=urllib.error.HTTPError('https://www.data.gouv.fr/',503,'fixture',{},None)
            with patch('service.download.safe_url',side_effect=lambda x:x),patch.object(client.opener,'open',side_effect=error) as request,patch('service.download.time.sleep'):
                with self.assertRaises(urllib.error.HTTPError):client.fetch('https://www.data.gouv.fr/')
                self.assertEqual(request.call_count,3)

class DocumentsSchedulerTests(unittest.TestCase):
    def test_quotes_and_capacity_validation(self):
        valid={'documentDate':None,'facts':[{'field':'capacity','value':600,'quote':'Capacité de 600 étudiants.'}]};self.assertTrue(validate(valid,'Capacité de 600 étudiants.')['reviewRequired'])
        normalized=validate({'documentDate':'12 septembre 2025','facts':[{'field':'capacity','value':'600 étudiants','quote':'600 étudiants'}]},'12 septembre 2025 : 600 étudiants')
        self.assertEqual(normalized['documentDate'],'2025-09-12');self.assertEqual(normalized['facts'][0]['value'],600)
        with self.assertRaises(ValueError):validate(valid,'Capacité non indiquée.')
        with self.assertRaises(ValueError):validate({**valid,'facts':[{'field':'capacity','value':700,'quote':'Capacité de 600 étudiants.'}]},'Capacité de 600 étudiants.')
    def test_ollama_offline_does_not_break_imports(self):
        with tempfile.TemporaryDirectory() as temp,patch.dict(os.environ,{'OLLAMA_MODEL':'fixture'}),patch('service.documents.urllib.request.urlopen',side_effect=TimeoutError('offline')):
            value=extract('Official test document','https://www.data.gouv.fr/',Store(temp));self.assertEqual(value['status'],'review-error');self.assertTrue(value['reviewRequired'])
    def test_paris_dst_daily_once(self):
        zone=ZoneInfo('Europe/Paris')
        for day in ['2026-03-29','2026-10-25']:
            local=dt.datetime.fromisoformat(day+'T04:00:00').replace(tzinfo=zone)
            self.assertTrue(due(local,None));self.assertFalse(due(local,day));self.assertFalse(due(local.replace(hour=3),None))

if __name__=='__main__':unittest.main()
