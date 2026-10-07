"""Wall-clock Europe/Paris 04:00. Persisted day claim prevents duplicate DST runs."""
import datetime as dt
import json
import time
from zoneinfo import ZoneInfo
from service.store import Store, config, now
from service.pipeline import run

def due(local, last_day, hour=4, minute=0):
    return local.date().isoformat()!=last_day and (local.hour,local.minute)>=(hour,minute)

def tick(store, instant=None):
    schedule=config()['schedule'];local=(instant or dt.datetime.now(dt.timezone.utc)).astimezone(ZoneInfo(schedule['timezone']))
    with store.db() as db:
        row=db.execute("SELECT value FROM settings WHERE key='schedulerDay'").fetchone()
        last=row['value'] if row else None
    if not due(local,last,schedule['hour'],schedule['minute']):return None
    result=run(store)
    with store.db() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedulerDay',?)",(local.date().isoformat(),))
    return result

if __name__=='__main__':
    store=Store();store.bootstrap()
    while True:
        try:
            result=tick(store)
            if result: print(json.dumps(result,ensure_ascii=False),flush=True)
            with store.db() as db:db.execute("INSERT OR REPLACE INTO settings VALUES('schedulerHeartbeat',?)",(now(),))
        except Exception as error:print(json.dumps({'schedulerError':str(error)[:300]}),flush=True)
        time.sleep(30)
