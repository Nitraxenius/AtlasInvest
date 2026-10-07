"""Package tracked and non-ignored project files, excluding local state and secrets."""
from pathlib import Path
import hashlib
import json
import subprocess
import zipfile

root=Path(__file__).resolve().parents[1]
files=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).decode().split('\0')
destination=root/'outputs'/'atlas-invest-docker.zip'
destination.parent.mkdir(exist_ok=True)
manifest={}
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(set(files)):
        file=root/name
        if not name or not file.is_file() or name.startswith(('.env','.openai/')) and name not in ('.env.example','.openai/hosting.json') or name.endswith('.tsbuildinfo'):continue
        body=file.read_bytes();manifest[name]=hashlib.sha256(body).hexdigest();archive.writestr('atlas-invest/'+name,body)
    archive.writestr('atlas-invest/RELEASE-MANIFEST.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(destination),'files':len(manifest),'sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}))
