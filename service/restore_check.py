"""Restore a real backup into a separate test instance and check every release hash."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from service.store import Store

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('backup');parser.add_argument('destination');args=parser.parse_args()
    source=Path(args.backup).resolve();destination=Path(args.destination).resolve()
    if destination.exists():raise ValueError('Isolated destination must not exist')
    shutil.copytree(source,destination);store=Store(destination);store.rollback(store.current())
    manifest=store.manifest()
    for name,digest in manifest['files'].items():assert hashlib.sha256(store.file(name).read_bytes()).hexdigest()==digest
    with store.db() as db:assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    print(json.dumps({'restoreVerified':True,'version':store.current(),'files':len(manifest['files'])}))
