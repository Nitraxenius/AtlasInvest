"""GTFS keeps calendars and departures per service; query dates remain deterministic."""
import datetime as dt
import io
from pathlib import PurePosixPath
from scripts.collect import parse_csv, num
from service.download import unzip

def active_services(calendars, exceptions, date):
    date = dt.date.fromisoformat(date) if isinstance(date, str) else date
    day = date.strftime('%Y%m%d'); weekday = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][date.weekday()]
    active = {r['service_id'] for r in calendars if r['start_date'] <= day <= r['end_date'] and r.get(weekday) == '1'}
    for row in exceptions:
        if row['date'] == day:
            if row['exception_type'] == '1': active.add(row['service_id'])
            elif row['exception_type'] == '2': active.discard(row['service_id'])
    return active

def at_date(transport, date):
    if not transport or 'calendars' not in transport: return transport
    active = active_services(transport['calendars'], transport['exceptions'], date)
    stops = []
    for feature in transport['stops']['features']:
        prop = dict(feature['properties'])
        prop['departures'] = sorted([d[:3] for d in prop.pop('serviceDepartures', []) if d[3] in active])
        stops.append({**feature, 'properties': prop})
    return {**transport, 'stops': {'type':'FeatureCollection','features':stops}, 'serviceDate':str(date), 'activeServices':len(active)}

def normalize(body):
    archive = unzip(body); names = {PurePosixPath(n).name:n for n in archive.namelist()}
    required = {'stops.txt','routes.txt','trips.txt','stop_times.txt'}
    if not required.issubset(names) or not {'calendar.txt','calendar_dates.txt'} & names.keys(): raise ValueError('Incomplete GTFS schema')
    def rows(name): return parse_csv(archive.read(names[name])) if name in names else []
    routes = {r['route_id']:r for r in rows('routes.txt')}; trips = {r['trip_id']:r for r in rows('trips.txt')}
    departures = {}; stop_routes = {}
    for row in rows('stop_times.txt'):
        trip = trips.get(row['trip_id'])
        if not trip or trip['route_id'] not in routes: raise ValueError('GTFS orphan trip/route')
        time = row.get('departure_time') or row.get('arrival_time')
        stop_routes.setdefault(row['stop_id'],set()).add(trip['route_id'])
        if time:
            h,m,s = map(int,time.split(':'))
            if not 0<=m<60 or not 0<=s<60 or not 0<=h<=72: raise ValueError('Invalid GTFS time')
            departures.setdefault(row['stop_id'],[]).append([h*60+m,trip['route_id'],trip.get('direction_id',''),trip['service_id']])
    stops=[]
    for row in rows('stops.txt'):
        lon,lat = num(row.get('stop_lon')),num(row.get('stop_lat'))
        if lon is None or lat is None or not -6<lon<10 or not 41<lat<52: raise ValueError('Invalid GTFS coordinates')
        stops.append({'type':'Feature','geometry':{'type':'Point','coordinates':[lon,lat]},'properties':{'id':row['stop_id'],'name':row['stop_name'],'routes':sorted(stop_routes.get(row['stop_id'],set())),'departures':[],'serviceDepartures':departures.get(row['stop_id'],[])}})
    shapes={}
    for row in rows('shapes.txt'):
        lon,lat=float(row['shape_pt_lon']),float(row['shape_pt_lat'])
        if not -6<lon<10 or not 41<lat<52: raise ValueError('Invalid GTFS shape')
        shapes.setdefault(row['shape_id'],[]).append((int(row['shape_pt_sequence']),[lon,lat]))
    lines=[]; seen=set()
    for trip in trips.values():
        key=trip['route_id'],trip.get('shape_id'),trip.get('direction_id','')
        if key in seen or key[1] not in shapes: continue
        seen.add(key); route=routes[key[0]]
        lines.append({'type':'Feature','geometry':{'type':'LineString','coordinates':[p for _,p in sorted(shapes[key[1]])]},'properties':{'id':key[0],'name':route.get('route_short_name') or route.get('route_long_name'),'direction':key[2],'color':'#'+(route.get('route_color') or '748294'),'mode':route.get('route_type')}})
    return {'stops':{'type':'FeatureCollection','features':stops},'lines':{'type':'FeatureCollection','features':lines},'routes':{k:{'name':r.get('route_short_name') or r.get('route_long_name'),'longName':r.get('route_long_name'),'color':'#'+(r.get('route_color') or '748294'),'mode':r.get('route_type')} for k,r in routes.items()},'calendars':rows('calendar.txt'),'exceptions':rows('calendar_dates.txt'),'shapesAvailable':bool(shapes),'limits':'Horaires théoriques ; aucune donnée temps réel. Aucun tracé inventé.'}
