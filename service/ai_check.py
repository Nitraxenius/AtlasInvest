"""Reproducible optional local extraction check using an official fetched document."""
import json
from service.documents import sources, parse, extract
from service.download import Downloader
from service.store import Store

if __name__=='__main__':
    store=Store();point=next(p for p in sources() if p['id']=='uco-future')
    body=Downloader(store.path/'raw').fetch(point['source'],max_age=604800)
    text=parse(body);position=text.find('600')
    excerpt=text[max(0,position-500):position+900] if position>=0 else text[:1400]
    result=extract(excerpt,point['source'],store)
    print(json.dumps(result,ensure_ascii=False))
