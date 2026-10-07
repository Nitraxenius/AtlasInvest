"""Read-only versioned API. Administrative writes are local CLI commands only."""
import datetime as dt
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import hmac
import re
from urllib.parse import urlsplit, parse_qs
from service.store import Store, config, encode
from service.transport import at_date

class Handler(BaseHTTPRequestHandler):
    store = None
    def log_message(self, format, *args):
        print(json.dumps({'http': format % args}), flush=True)
    def reply(self, value, status=200, cache='no-store'):
        body=encode(value);self.send_response(status)
        origin=self.headers.get('Origin');allowed=os.environ.get('ATLAS_CORS_ORIGINS','').split(',')
        if origin and origin in allowed:
            self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
        self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control',cache)
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        try:
            url=urlsplit(self.path);parts=url.path.strip('/').split('/');query=parse_qs(url.query)
            if len(self.path)>2048: return self.reply({'error':'Request too large'},414)
            if parts==['health']:
                return self.reply({'ok':bool(self.store.current()),'version':self.store.current()},200 if self.store.current() else 503)
            if parts[:2]!=['api','v1']:return self.reply({'error':'Not found'},404)
            route=parts[2:]
            token=os.environ.get('ATLAS_READ_TOKEN')
            if token and not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):return self.reply({'error':'Unauthorized'},401)
            if route==['manifest']:return self.reply(self.store.manifest())
            if route==['cities']:return self.reply(config()['cities'])
            if route in (['status'],['events']):
                with self.store.db() as db:
                    if route==['events']:
                        return self.reply([json.loads(r['payload']) for r in db.execute('SELECT payload FROM events ORDER BY created DESC LIMIT 50')])
                    rows=db.execute('SELECT id,started,finished,status,details FROM runs ORDER BY started DESC LIMIT 10').fetchall()
                    return self.reply({'current':self.store.current(),'runs':[{**dict(r),'details':json.loads(r['details'])} for r in rows]})
            if len(route)>=3 and route[0]=='versions' and re.fullmatch(r'[\w-]{1,64}',route[1]):
                version=route[1];name=route[2]
                if len(route)==3 and name in ('sources.json','points.json',*[c+'.json' for c in config()['cities']]):
                    value=json.loads(self.store.file(name,version).read_text(encoding='utf-8'))
                    return self.reply(value,cache='public, max-age=31536000, immutable')
                if len(route)==4 and name in config()['cities']:
                    city=json.loads(self.store.file(name+'.json',version).read_text(encoding='utf-8'));kind=route[3]
                    if kind=='transport':
                        date=query.get('date',[dt.date.today().isoformat()])[0];dt.date.fromisoformat(date)
                        return self.reply(at_date(city.get('transport'),date))
                    if kind=='transactions':
                        limit=int(query.get('limit',['200'])[0]);offset=int(query.get('offset',['0'])[0])
                        if not 1<=limit<=1000 or not 0<=offset<=1000000:raise ValueError('Pagination outside limits')
                        where='t.version=? AND t.city=?';args=[version,name]
                        if 'bbox' in query:
                            bbox=list(map(float,query['bbox'][0].split(',')))
                            if len(bbox)!=4 or not -6<=bbox[0]<bbox[2]<=10 or not 41<=bbox[1]<bbox[3]<=52:raise ValueError('Invalid bbox')
                            where+=' AND b.minLon>=? AND b.maxLon<=? AND b.minLat>=? AND b.maxLat<=?';args += [bbox[0],bbox[2],bbox[1],bbox[3]]
                        with self.store.db() as db:
                            total=db.execute('SELECT count(*) FROM transactions t JOIN transaction_bounds b ON b.id=t.rowid WHERE '+where,args).fetchone()[0]
                            values=[json.loads(r[0]) for r in db.execute('SELECT t.payload FROM transactions t JOIN transaction_bounds b ON b.id=t.rowid WHERE '+where+' ORDER BY t.rowid LIMIT ? OFFSET ?',args+[limit,offset])]
                        return self.reply({'version':version,'total':total,'offset':offset,'items':values})
            return self.reply({'error':'Not found'},404)
        except FileNotFoundError:return self.reply({'error':'Version unavailable'},404)
        except (ValueError,KeyError):return self.reply({'error':'Invalid request'},400)
        except Exception:return self.reply({'error':'Service unavailable'},503)

def serve(store=None, port=None):
    Handler.store=store or Store();Handler.store.bootstrap()
    server=ThreadingHTTPServer((os.environ.get('ATLAS_BIND','127.0.0.1'),port or int(os.environ.get('ATLAS_PORT','8787'))),Handler)
    print(json.dumps({'listening':server.server_address}),flush=True);server.serve_forever()

if __name__=='__main__':serve()
