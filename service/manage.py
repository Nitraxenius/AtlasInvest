"""Local administrative commands; no HTTP administrative surface."""
import argparse
import json
from pathlib import Path
import shutil
from service.store import Store

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['bootstrap','status','backup','restore','rollback']);parser.add_argument('target',nargs='?');args=parser.parse_args();store=Store()
    if args.command=='bootstrap':print(store.bootstrap())
    elif args.command=='status':
        with store.db() as db: print(json.dumps({'version':store.current(),'runs':[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY started DESC LIMIT 10')]},ensure_ascii=False))
    elif args.command=='backup':print(store.backup(args.target))
    elif args.command=='rollback':store.rollback(args.target);print(store.current())
    elif args.command=='restore':
        source=Path(args.target).resolve()
        if store.current():raise ValueError('Restore requires a new isolated ATLAS_STATE directory')
        for name in ('releases','raw','review'):
            shutil.copytree(source/name,store.path/name,dirs_exist_ok=True)
        shutil.copy2(source/'atlas.sqlite',store.path/'atlas.sqlite')
        restored=Store(store.path);restored.rollback(restored.current());print(restored.current())
