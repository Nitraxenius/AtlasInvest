"""SQLite metadata and immutable snapshots. The database pointer is the commit boundary."""
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import uuid

ROOT = Path(__file__).resolve().parents[1]
FILES = (*[c+'.json' for c in json.loads((ROOT/'config/cities.json').read_text(encoding='utf-8'))['cities']], 'sources.json', 'points.json')

def validate_geojson(value):
    if not isinstance(value,dict) or value.get('type')!='FeatureCollection' or not isinstance(value.get('features'),list):raise ValueError('Invalid GeoJSON collection')
    def position(p):
        if not isinstance(p,list) or len(p)<2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in p):raise ValueError('Invalid coordinates')
        if not -180<=p[0]<=180 or not -90<=p[1]<=90:raise ValueError('Coordinates outside Earth')
    def line(points,ring=False):
        if not isinstance(points,list) or len(points)<(4 if ring else 2):raise ValueError('Invalid geometry length')
        for p in points:position(p)
        if ring and points[0]!=points[-1]:raise ValueError('Unclosed polygon ring')
    for feature in value['features']:
        if feature.get('type')!='Feature' or not isinstance(feature.get('properties'),dict):raise ValueError('Invalid feature')
        geometry=feature.get('geometry') or {};kind=geometry.get('type');coordinates=geometry.get('coordinates')
        if kind=='Point':position(coordinates)
        elif kind=='LineString':line(coordinates)
        elif kind in ('Polygon','MultiPolygon'):
            polygons=[coordinates] if kind=='Polygon' else coordinates
            if not isinstance(polygons,list) or not polygons:raise ValueError('Empty polygon')
            for polygon in polygons:
                if not isinstance(polygon,list) or not polygon:raise ValueError('Empty rings')
                for ring in polygon:line(ring,True)
        elif kind=='MultiLineString':
            if not isinstance(coordinates,list) or not coordinates:raise ValueError('Empty lines')
            for points in coordinates:line(points)
        else:raise ValueError('Unsupported geometry')

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:return super().__exit__(*args)
        finally:self.close()

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

def config():
    value = json.loads((ROOT / 'config/cities.json').read_text(encoding='utf-8'))
    assert value['schemaVersion'] == 1
    for key, city in value['cities'].items():
        if not re.fullmatch(r'[a-z][a-z0-9-]{1,30}', key): raise ValueError('Invalid city ID')
        if not re.fullmatch(r'\d{5}', city['commune']): raise ValueError('Invalid INSEE code')
        if not re.fullmatch(r'\d{9}', city['epci']): raise ValueError('Invalid EPCI')
        lon, lat = city['center']
        if not -6 < lon < 10 or not 41 < lat < 52: raise ValueError('Invalid centre')
    return value

class Store:
    def __init__(self, directory=None):
        self.path = Path(directory or os.environ.get('ATLAS_STATE', ROOT / '.atlas-state')).resolve()
        self.path.mkdir(parents=True, exist_ok=True)
        for name in ('releases', 'staging', 'raw', 'review'):
            (self.path / name).mkdir(exist_ok=True)
        with self.db() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS releases(id TEXT PRIMARY KEY, created TEXT NOT NULL, hash TEXT NOT NULL, manifest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, started TEXT, finished TEXT, status TEXT, details TEXT);
                CREATE TABLE IF NOT EXISTS locks(name TEXT PRIMARY KEY, owner TEXT, expires REAL);
                CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY, created TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS transactions(rowid INTEGER PRIMARY KEY, version TEXT, city TEXT, mutation TEXT, payload TEXT, UNIQUE(version,city,mutation));
                CREATE INDEX IF NOT EXISTS transaction_version_city ON transactions(version,city);
                CREATE VIRTUAL TABLE IF NOT EXISTS transaction_bounds USING rtree(id,minLon,maxLon,minLat,maxLat);
                CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied TEXT);
                INSERT OR IGNORE INTO migrations VALUES(1, CURRENT_TIMESTAMP);
            ''')
            if not db.execute('SELECT 1 FROM migrations WHERE version=2').fetchone():
                for release in db.execute('SELECT id FROM releases').fetchall():
                    self.index(db,release['id'],self.path/'releases'/release['id'])
                db.execute('INSERT INTO migrations VALUES(2,?)',(now(),))

    def index(self, db, version, stage):
        for city in config()['cities']:
            for tx in json.loads((stage/(city+'.json')).read_bytes())['transactions']:
                cursor=db.execute('INSERT INTO transactions(version,city,mutation,payload) VALUES(?,?,?,?)',(version,city,tx['id'],encode(tx).decode()))
                db.execute('INSERT INTO transaction_bounds VALUES(?,?,?,?,?)',(cursor.lastrowid,tx['lon'],tx['lon'],tx['lat'],tx['lat']))

    def db(self):
        db = sqlite3.connect(self.path / 'atlas.sqlite', timeout=30, factory=Connection)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA busy_timeout=30000')
        return db

    @contextlib.contextmanager
    def lock(self, name='pipeline', seconds=180):
        import time
        import threading
        owner = uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('DELETE FROM locks WHERE expires < ?', (time.time(),))
            try: db.execute('INSERT INTO locks VALUES(?,?,?)', (name, owner, time.time() + seconds))
            except sqlite3.IntegrityError: raise RuntimeError('An import already holds the lock')
        stop=threading.Event()
        def heartbeat():
            while not stop.wait(30):
                with self.db() as db:db.execute('UPDATE locks SET expires=? WHERE name=? AND owner=?',(time.time()+seconds,name,owner))
        worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
        try: yield owner
        finally:
            stop.set();worker.join(timeout=5)
            with self.db() as db: db.execute('DELETE FROM locks WHERE name=? AND owner=?', (name, owner))

    def current(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM settings WHERE key='current'").fetchone()
            return row['value'] if row else None

    def manifest(self, version=None):
        with self.db() as db:
            row = db.execute('SELECT manifest FROM releases WHERE id=?', (version or self.current(),)).fetchone()
            if not row: raise FileNotFoundError('No validated release')
            return json.loads(row['manifest'])

    def file(self, name, version=None):
        if name not in FILES: raise FileNotFoundError(name)
        manifest = self.manifest(version)
        return self.path / 'releases' / manifest['version'] / name

    def validate(self, stage):
        for name in FILES:
            if (stage / name).stat().st_size > 80 * 1024 * 1024: raise ValueError('Snapshot too large')
            obj = json.loads((stage / name).read_text(encoding='utf-8'))
            if name[:-5] in config()['cities']:
                if not obj.get('transactions') or not obj.get('communes', {}).get('features'): raise ValueError('Empty core dataset')
                validate_geojson(obj['communes'])
                for layer in ('lines','stops'):
                    if obj.get('transport',{}).get(layer):validate_geojson(obj['transport'][layer])
                codes = {f['properties']['code'] for f in obj['communes']['features']}
                ids = set()
                for tx in obj['transactions']:
                    if tx['id'] in ids: raise ValueError('Duplicate mutation')
                    ids.add(tx['id'])
                    if tx['code'] not in codes or not -6 < tx['lon'] < 10 or not 41 < tx['lat'] < 52: raise ValueError('Transaction outside scope')
                    if tx['area'] <= 0 or tx['price'] <= 0: raise ValueError('Invalid price/area')
                if obj.get('oll'):
                    validate_geojson(obj['oll']['features'])
                    zones = {f['properties']['id'] for f in obj['oll']['features']['features']}
                    if not zones or not zones.issubset({r['Zone_calcul'] for r in obj['oll']['rows']}): raise ValueError('Inconsistent OLL contours')
            elif name == 'sources.json':
                if not obj.get('sources'): raise ValueError('Empty sources')
            elif name == 'points.json':
                if not isinstance(obj, list): raise ValueError('Invalid points')
                for p in obj:
                    if p['city'] not in config()['cities'] or not -6 < p['lon'] < 10 or not 41 < p['lat'] < 52: raise ValueError('Invalid point')

    def promote(self, stage, details=None):
        stage = Path(stage)
        self.validate(stage)
        hashes = {n: hashlib.sha256((stage / n).read_bytes()).hexdigest() for n in FILES}
        digest = hashlib.sha256(encode(hashes)).hexdigest()
        previous = self.current()
        if previous and self.manifest(previous)['contentHash'] == digest: return previous, False
        version = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:12]
        manifest = dict(version=version, created=now(), contentHash=digest, files=hashes,
                        cities=list(config()['cities']), details=details or {})
        destination = self.path / 'releases' / version
        shutil.copytree(stage, destination)
        (destination / 'manifest.json').write_bytes(encode(manifest))
        for name in (*FILES,'manifest.json'):
            with (destination/name).open('r+b') as handle:os.fsync(handle.fileno())
        # All files have been closed and validated before committing the pointer.
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute('INSERT INTO releases VALUES(?,?,?,?)', (version, manifest['created'], digest, encode(manifest).decode()))
            db.execute("INSERT OR REPLACE INTO settings VALUES('current',?)", (version,))
            changes={}
            for city in config()['cities']:
                value=json.loads((stage/(city+'.json')).read_bytes())
                old=json.loads(self.file(city+'.json',previous).read_bytes()) if previous else {'transactions':[]}
                old_tx={t['id']:t for t in old['transactions']}
                changes[city]=[t['id'] for t in value['transactions'] if t!=old_tx.get(t['id'])][:1000]
            self.index(db,version,stage)
            old_sources={s['id']:s for s in json.loads(self.file('sources.json',previous).read_bytes())['sources']} if previous else {}
            for source in json.loads((stage/'sources.json').read_bytes())['sources']:
                old=old_sources.get(source['id'])
                if old and source==old:continue
                event_id=hashlib.sha256(encode([source['id'],source.get('hash') or source])).hexdigest()
                city=next((c for c in config()['cities'] if source['id'].startswith(c+'-')),None)
                event=dict(id=event_id,kind='data-publication',version=version,city=city,source=source.get('title',source['id']),url=source.get('url'),period=source.get('period') or 'Non précisée',scale=source.get('scale') or 'Non précisée',changedTransactions=changes.get(city,[]) if 'dvf' in source['id'] else [],description='Publication ou révision de données historiques ; aucune annonce immobilière disponible.' if 'dvf' in source['id'] else 'Nouvelle publication ou révision de la source. Consulter la période et les limites du catalogue.')
                db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(event_id,now(),encode(event).decode()))
        return version, True

    def bootstrap(self):
        with self.lock():
            if self.current(): return self.current()
            stage=self.path/'staging'/('bootstrap-'+uuid.uuid4().hex);stage.mkdir()
            excluded={}
            try:
                for name in FILES: shutil.copy2(ROOT/'public/data'/name,stage/name)
                for city in config()['cities']:
                    filename=stage/(city+'.json');data=json.loads(filename.read_text(encoding='utf-8'))
                    codes={f['properties']['code'] for f in data['communes']['features']}
                    excluded[city]=[t['id'] for t in data['transactions'] if t['code'] not in codes]
                    data['transactions']=[t for t in data['transactions'] if t['code'] in codes]
                    filename.write_bytes(encode(data))
                return self.promote(stage, {'bootstrap': True, 'freshness': 'Original snapshot, not a new collection', 'excludedOutsideScope':excluded})[0]
            finally:shutil.rmtree(stage)

    def rollback(self, version):
        with self.lock():
            manifest = self.manifest(version)
            directory = self.path / 'releases' / version
            self.validate(directory)
            for name, digest in manifest['files'].items():
                if hashlib.sha256((directory / name).read_bytes()).hexdigest() != digest: raise ValueError('Release hash mismatch')
            with self.db() as db: db.execute("INSERT OR REPLACE INTO settings VALUES('current',?)", (version,))

    def backup(self, destination):
        destination = Path(destination).resolve()
        if destination == self.path or self.path in destination.parents: raise ValueError('Backup must be outside live state')
        destination.mkdir(parents=True, exist_ok=False)
        with self.lock():
            with self.db() as source, sqlite3.connect(destination / 'atlas.sqlite',factory=Connection) as target:
                source.backup(target)
                target.execute('DELETE FROM locks')
                target.execute("UPDATE runs SET status='interrupted' WHERE status='running'")
            for name in ('releases', 'raw', 'review'): shutil.copytree(self.path / name, destination / name)
        return destination

    def prune(self, keep=8):
        # Keep recent releases and always keep the current release. Raw cache is retained.
        with self.db() as db:
            rows = db.execute('SELECT id FROM releases ORDER BY created DESC').fetchall()
            preserve = {r['id'] for r in rows[:max(2, keep)]} | {self.current()}
            for row in rows:
                if row['id'] not in preserve:
                    db.execute('DELETE FROM transaction_bounds WHERE id IN (SELECT rowid FROM transactions WHERE version=?)',(row['id'],))
                    db.execute('DELETE FROM transactions WHERE version=?',(row['id'],))
                    db.execute('DELETE FROM releases WHERE id=?', (row['id'],))
                    # Deletion happens only after a seven-day browser grace period.
        import time
        releases=(self.path/'releases').resolve()
        for directory in releases.iterdir():
            if directory.is_dir() and directory.name not in preserve and time.time()-directory.stat().st_mtime>7*86400:
                if directory.resolve().parent!=releases:raise ValueError('Unsafe retention target')
                shutil.rmtree(directory)
        return preserve
