import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
const config=JSON.parse(fs.readFileSync('dist/server/wrangler.json'));
const assets=path.resolve('dist/server',config.assets.directory);
for(const file of ['maplibre-gl-worker.mjs','maplibre-gl-shared.mjs'])assert.deepEqual(fs.readFileSync(path.join(assets,'maplibre',file)),fs.readFileSync('public/maplibre/'+file));
function walk(dir){return fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(path.join(dir,e.name)):[path.join(dir,e.name)])}
assert.ok(walk(assets).filter(f=>f.endsWith('.js')).some(f=>fs.readFileSync(f,'utf8').includes('/maplibre/maplibre-gl-worker.mjs')),'Compiled map must configure the worker URL');
console.log('Build : worker, dépendance et URL explicite présents dans les assets livrés');
