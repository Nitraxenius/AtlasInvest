"""Bounded official-source HTTP client, conditional cache, atomic writes and redirect checks."""
import hashlib
import ipaddress
import json
from pathlib import Path
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HOSTS = {'geo.api.gouv.fr', 'files.data.gouv.fr', 'www.data.gouv.fr', 'static.data.gouv.fr',
         'transport.data.gouv.fr', 'tabular-api.data.gouv.fr', 'www.observatoires-des-loyers.org',
         'data.geopf.fr', 'www.georisques.gouv.fr', 'georisques.gouv.fr', 'overpass-api.de',
         'data.laval.fr', 'data.tours-metropole.fr', 'www.filbleu.fr', 'portail-api-data.mobilites-touraine.fr',
         'geo-dvf.s3.sbg.io.cloud.ovh.net'}

def safe_url(url, hosts=HOSTS):
    p = urllib.parse.urlsplit(url)
    delegated = p.hostname == 's3.eu-west-1.amazonaws.com' and p.path.startswith('/files.orchestra.ratpdev.com/networks/rd-laval/exports/')
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443) or (p.hostname not in hosts and not delegated):
        raise ValueError('Download URL is not an allowed official HTTPS source')
    for info in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(info[4][0]).is_global: raise ValueError('Private source address rejected')
    return url

class Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

class Downloader:
    def __init__(self, directory, max_bytes=100 * 1024 * 1024, timeout=45):
        self.path = Path(directory); self.path.mkdir(parents=True, exist_ok=True)
        self.max_bytes = max_bytes; self.timeout = timeout
        self.opener = urllib.request.build_opener(Redirects())
        self.records = []
        self.force=False

    def fetch(self, url, name=None, force=False, max_age=86400):
        force=force or self.force
        safe_url(url)
        key = hashlib.sha256(url.encode()).hexdigest()
        datafile = self.path / (key + '.bin'); metafile = self.path / (key + '.json')
        meta = json.loads(metafile.read_text()) if metafile.exists() and datafile.exists() else {}
        if meta and hashlib.sha256(datafile.read_bytes()).hexdigest()!=meta.get('sha256'):meta={}
        if meta and not force and time.time() - meta.get('checked', 0) < max_age:
            self.records.append({**meta, 'cached': True}); return datafile.read_bytes()
        headers = {'User-Agent': 'AtlasInvest/2.0 (bounded open-data synchronisation)', 'Accept-Encoding': 'identity'}
        if meta and not force:
            for key, header in [('etag', 'If-None-Match'), ('lastModified', 'If-Modified-Since')]:
                if meta.get(key): headers[header] = meta[key]
        for attempt in range(3):
            try:
                with self.opener.open(urllib.request.Request(url, headers=headers), timeout=self.timeout) as response:
                    safe_url(response.url)
                    length = response.headers.get('Content-Length')
                    if length and int(length) > self.max_bytes: raise ValueError('Download too large')
                    chunks = []; size = 0
                    while True:
                        chunk = response.read(min(1024 * 1024, self.max_bytes + 1 - size))
                        if not chunk: break
                        chunks.append(chunk); size += len(chunk)
                        if size > self.max_bytes: raise ValueError('Download too large')
                    if length and size != int(length): raise ValueError('Incomplete download')
                    body = b''.join(chunks)
                    if not body: raise ValueError('Empty source response')
                    new = dict(url=url, finalUrl=response.url, name=name, checked=time.time(),
                               sha256=hashlib.sha256(body).hexdigest(), size=size,
                               etag=response.headers.get('ETag'), lastModified=response.headers.get('Last-Modified'))
                    temp = datafile.with_suffix('.' + uuid.uuid4().hex + '.tmp')
                    temp.write_bytes(body); temp.replace(datafile)
                    objects=self.path/'objects';objects.mkdir(exist_ok=True)
                    archived=objects/new['sha256']
                    if not archived.exists():
                        import shutil
                        shutil.copy2(datafile,archived)
                    metafile.write_text(json.dumps(new))
                    self.records.append(new); return body
            except urllib.error.HTTPError as error:
                if error.code == 304 and meta:
                    meta['checked'] = time.time(); metafile.write_text(json.dumps(meta))
                    self.records.append({**meta, 'notModified': True}); return datafile.read_bytes()
                if error.code not in (429, 500, 502, 503, 504): raise
                if attempt == 2: raise
            except (TimeoutError, urllib.error.URLError):
                if attempt == 2: raise
            time.sleep(2 ** attempt)
        raise RuntimeError('Download failed')

def unzip(body, max_total=250 * 1024 * 1024):
    import io, zipfile
    archive = zipfile.ZipFile(io.BytesIO(body))
    if len(archive.infolist()) > 200 or sum(i.file_size for i in archive.infolist()) > max_total:
        raise ValueError('Archive decompression limit')
    for info in archive.infolist():
        if info.file_size > max_total or '..' in Path(info.filename).parts: raise ValueError('Unsafe archive')
    return archive
