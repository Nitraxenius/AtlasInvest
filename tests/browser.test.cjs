// Uses a real installed Edge browser and the production Docker web server.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const runtime=process.env.ATLAS_PLAYWRIGHT||'C:/Users/sribeiro/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
const {chromium}=require(runtime);
const base=process.env.ATLAS_BROWSER_URL||'http://127.0.0.1:3000';
const out=path.resolve('outputs/browser');fs.mkdirSync(out,{recursive:true});
async function map(page){
  await page.waitForSelector('.map-canvas');
  await page.evaluate(()=>{
    const element=document.querySelector('.map-canvas');if(!element)return false;let fiber=element[Object.keys(element).find(k=>k.startsWith('__reactFiber'))];
    for(let depth=0;fiber&&depth<12;depth++,fiber=fiber.return){
      for(let hook=fiber.memoizedState;hook;hook=hook.next){if(hook.memoizedState?.current?.getLayer){window.__testMap=hook.memoizedState.current;return}}
    }
    throw Error('Real MapLibre instance unavailable');
  });
  await page.waitForFunction(()=>(window.__testMap?.getSource('zones')?._data?.geojson||window.__testMap?.getSource('zones')?._data)?.features?.length>0);
}
async function select(page,label,name){await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none');await page.getByRole('combobox',{name:label,exact:true}).click();if(label==='Ville')console.log(await page.getByRole('option').allTextContents());await page.getByRole('option',{name,exact:true}).click();await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none')}
async function clickLayer(page,layer,kind=null){
  await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none');
  await page.waitForFunction(()=>!window.__testMap.isMoving());
  const position=await page.evaluate(({layer,kind})=>{
    const m=window.__testMap;const canvas=m.getCanvas();const rect=canvas.getBoundingClientRect();
    for(let y=5;y<rect.height-5;y+=3)for(let x=5;x<rect.width-5;x+=3){
      const point=[x,y];const features=m.queryRenderedFeatures(point,{layers:[layer]});
      const top=m.queryRenderedFeatures(point,{layers:['points-layer','tx-layer','stops-layer','lines-layer','oll-fill','zone-fill']})[0];
      if(features.length&&top?.layer.id===layer&&(!kind||top.properties.kind===kind)){const e=document.elementFromPoint(rect.x+x,rect.y+y);if(e===canvas||e?.classList.contains('maplibregl-canvas-container'))return {x:rect.x+x,y:rect.y+y}}
    }
    const f=m.queryRenderedFeatures({layers:[layer]})[0];if(f?.geometry.type==='Point'){const p=m.project(f.geometry.coordinates);const e=document.elementFromPoint(rect.x+p.x,rect.y+p.y);console.log('hit',e?.tagName,e?.className,m.queryRenderedFeatures(p,{layers:['points-layer','tx-layer','stops-layer','lines-layer','oll-fill','zone-fill']}).map(f=>f.layer.id))}
    return null;
  },{layer,kind});
  if(!position){await page.screenshot({path:path.join(out,'failure-'+layer+'.png')});console.log(await page.evaluate(layer=>{const m=window.__testMap;return m.queryRenderedFeatures({layers:[layer]}).slice(0,3).map(f=>({geometry:f.geometry,point:m.project(f.geometry.coordinates),top:m.queryRenderedFeatures(m.project(f.geometry.coordinates)).map(x=>x.layer.id),rect:m.getCanvas().getBoundingClientRect().toJSON()}))},layer))}
  assert.ok(position,'Visible feature for '+layer);await page.mouse.click(position.x,position.y);
}
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});const report=[];
 try{
  for(const mobile of [false,true]){
   const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1600,height:1000},isMobile:mobile,deviceScaleFactor:1,acceptDownloads:true});
   const page=await context.newPage();const errors=[],failed=[],workers=[];
   page.on('console',m=>{if(m.text().startsWith('hit'))console.log(m.text())});page.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.message)});page.on('requestfailed',r=>failed.push({url:r.url(),error:r.failure()?.errorText}));page.on('worker',w=>workers.push(w.url()));
   await page.goto(base);await map(page);
   for(const city of ['Laval','Tours']){
    console.log('browser',mobile,city);await page.evaluate(()=>window.scrollTo(0,0));
    if(mobile)await page.getByRole('button',{name:'Afficher les filtres'}).click();
    await select(page,'Ville',city+(city==='Tours'?' · Métropole':' · Agglomération'));
    if(mobile)await page.getByRole('button',{name:'Afficher les filtres'}).click();
    await page.waitForFunction(city=>{const element=document.querySelector('.map-canvas');if(!element)return false;let fiber=element[Object.keys(element).find(k=>k.startsWith('__reactFiber'))];for(let d=0;fiber&&d<12;d++,fiber=fiber.return)for(let h=fiber.memoizedState;h;h=h.next)if(h.memoizedState?.current?.getLayer)window.__testMap=h.memoizedState.current;const source=window.__testMap?.getSource('communes')?._data;return (source?.geojson||source)?.features.length===(city==='Laval'?34:22)},city);
    await page.waitForFunction(()=>window.__testMap.queryRenderedFeatures({layers:['zone-fill']}).length>0);
    for(const label of ['Bus & tram','Arrêts','Campus','Services & emplois','Projets & logements']){
     const control=page.getByRole('switch',{name:label,exact:true});const initial=await control.getAttribute('aria-checked');await control.click();await control.click();assert.equal(await control.getAttribute('aria-checked'),initial);
    }
    const renders=await page.evaluate(()=>Object.fromEntries(['zone-fill','lines-layer','stops-layer','points-layer'].map(id=>[id,window.__testMap.queryRenderedFeatures({layers:[id]}).length])));
    assert.ok(renders['zone-fill']>0);assert.ok(renders['lines-layer']>0);assert.ok(renders['points-layer']>0);
    if(mobile){
     for(const [layer,heading] of [['lines-layer','LIGNE DE TRANSPORT'],['stops-layer','ARRÊT DE TRANSPORT'],['points-layer','CAMPUS'],['zone-fill','SECTEUR À PROSPECTER']]){
      await clickLayer(page,layer,layer==='points-layer'?'campus':null);await page.locator('.mobile-detail').getByText(heading,{exact:true}).first().waitFor();await page.keyboard.press('Escape');await page.locator('.mobile-detail').waitFor({state:'detached'});await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none');
     }
     await select(page,'Couche cartographique','Ventes individuelles');
     await page.waitForFunction(()=>{const s=window.__testMap.getSource('transactions')._data;return (s.geojson||s).features.length>0});
     await page.evaluate(()=>{const m=window.__testMap,s=m.getSource('transactions')._data;m.jumpTo({center:(s.geojson||s).features[0].geometry.coordinates,zoom:16})});
     await page.waitForFunction(()=>{const m=window.__testMap,c=m.getCanvas();return m.queryRenderedFeatures([c.clientWidth/2,c.clientHeight/2],{layers:['tx-layer']}).length>0});
     await clickLayer(page,'tx-layer');await page.locator('.mobile-detail').getByText('VENTE HISTORIQUE DVF',{exact:true}).waitFor();await page.keyboard.press('Escape');await page.locator('.mobile-detail').waitFor({state:'detached'});
     if(city==='Tours'){await select(page,'Couche cartographique','Loyer observé HC · OLL');await clickLayer(page,'oll-fill');await page.locator('.mobile-detail').getByText('ZONE DE LOYERS',{exact:true}).waitFor();await page.keyboard.press('Escape');await page.locator('.mobile-detail').waitFor({state:'detached'})}
     await select(page,'Couche cartographique','Prix de vente / m²');
     await page.locator('.zone-card').first().click();await page.getByRole('button',{name:'Favori',exact:true}).click();await page.keyboard.press('Escape');await page.locator('.mobile-detail').waitFor({state:'detached'});
     for(let i=0;i<4;i++){await page.locator('.zone-card').nth(i).click();await page.locator('.mobile-detail .detail-buttons').getByRole('button',{name:'Comparer',exact:true}).click();await page.keyboard.press('Escape');await page.locator('.mobile-detail').waitFor({state:'detached'})}
     await page.locator('.result-actions button').nth(1).click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none');
     const pending=page.waitForEvent('download');await page.getByTitle('Exporter en CSV').click();await(await pending).saveAs(path.join(out,'mobile-'+city+'.csv'));
     await page.evaluate(()=>window.scrollTo(0,0));await page.getByTitle('Choisir un rayon de recherche').click();const box=await page.locator('canvas.maplibregl-canvas').boundingBox();await page.mouse.click(box.x+box.width/2,box.y+box.height/2);await page.getByText('Rayon',{exact:true}).waitFor();await page.getByTitle('Effacer le périmètre').click();
     await page.getByTitle('Dessiner un périmètre').click();for(const [x,y] of [[.4,.4],[.6,.4],[.6,.6],[.4,.6]])await page.mouse.click(box.x+box.width*x,box.y+box.height*y);await page.getByTitle('Dessiner un périmètre').click();assert.ok(await page.evaluate(()=>(window.__testMap.getSource('selection')._data.geojson||window.__testMap.getSource('selection')._data).features.length>0));await page.getByTitle('Effacer le périmètre').click();
    }
    if(!mobile){
     for(const [layer,heading] of [['lines-layer','LIGNE DE TRANSPORT'],['stops-layer','ARRÊT DE TRANSPORT'],['points-layer','CAMPUS'],['zone-fill','SECTEUR À PROSPECTER']]){
      await clickLayer(page,layer,layer==='points-layer'?'campus':null);await page.getByText(heading,{exact:true}).first().waitFor();
     }
     await page.locator('.zone-card').first().click();await page.getByRole('button',{name:'Favori',exact:true}).click();assert.ok(await page.evaluate(()=>JSON.parse(localStorage.getItem('atlas-favorites')).length>0));
     for(let i=0;i<4;i++){await page.locator('.zone-card').nth(i).click();await page.locator('.detail-buttons').getByRole('button',{name:'Comparer',exact:true}).click()}
     await page.getByRole('button',{name:'Comparer (4/4)'}).click();await page.getByRole('dialog').waitFor();await page.keyboard.press('Escape');
     const download=page.waitForEvent('download');await page.getByTitle('Exporter en CSV').click();const file=await download;await file.saveAs(path.join(out,city+'.csv'));assert.ok(fs.readFileSync(path.join(out,city+'.csv'),'utf8').includes('mediane_eur_m2'));
     for(const option of ['Prix de vente / m²','Évolution historique','Volume de ventes','Loyer CC · commune','Rendement · hypothèse HC','Indice de prospection','Ventes individuelles'])await select(page,'Couche cartographique',option);
     await page.getByLabel('Surface min.',{exact:false}).fill('30');await page.getByLabel('Nombre minimum de ventes',{exact:false}).fill('3');await select(page,'Nombre de pièces','1 pièce');
     await page.waitForFunction(()=>{const s=window.__testMap.getSource('transactions')._data;const features=(s.geojson||s).features;return features.length>0&&features.every(f=>f.properties.rooms===1&&f.properties.area>=30)});
     await page.getByRole('button',{name:'Réinitialiser les filtres'}).click();
     await page.evaluate(()=>{const m=window.__testMap;const source=m.getSource('transactions')._data;const data=source.geojson||source;m.jumpTo({center:data.features[0].geometry.coordinates,zoom:16})});
     await page.waitForFunction(()=>window.__testMap.queryRenderedFeatures({layers:['tx-layer']}).length>0);await clickLayer(page,'tx-layer');await page.getByText('VENTE HISTORIQUE DVF',{exact:true}).waitFor();
     if(city==='Tours'){await select(page,'Couche cartographique','Loyer observé HC · OLL');await page.waitForFunction(()=>window.__testMap.queryRenderedFeatures({layers:['oll-fill']}).length>0);await clickLayer(page,'oll-fill');await page.getByText('ZONE DE LOYERS',{exact:true}).waitFor()}
     await select(page,'Couche cartographique','Prix de vente / m²');
     await page.getByTitle('Choisir un rayon de recherche').click();const box=await page.locator('canvas.maplibregl-canvas').boundingBox();await page.mouse.click(box.x+box.width/2,box.y+box.height/2);await page.getByText('Rayon',{exact:true}).waitFor();await page.getByTitle('Effacer le périmètre').click();
     await page.getByTitle('Dessiner un périmètre').click();for(const [x,y] of [[.4,.4],[.6,.4],[.6,.6],[.4,.6]])await page.mouse.click(box.x+box.width*x,box.y+box.height*y);await page.getByTitle('Dessiner un périmètre').click();assert.ok(await page.evaluate(()=>(window.__testMap.getSource('selection')._data.geojson||window.__testMap.getSource('selection')._data).features.length>0));await page.getByTitle('Effacer le périmètre').click();
    }
    await page.screenshot({path:path.join(out,(mobile?'mobile-':'desktop-')+city+'.png'),fullPage:true});
    report.push({mobile,city,renders,workers:[...new Set(workers)]});
   }
   await page.locator('.search-button').click();
   await page.getByPlaceholder('Saisir une adresse ou un campus…').fill('Tours');
   await page.getByRole('dialog').getByRole('option').first().click();
   await page.waitForFunction(()=>getComputedStyle(document.body).pointerEvents!=='none');
   if(mobile&&await page.getByRole('button',{name:'Fermer le détail'}).count())await page.getByRole('button',{name:'Fermer le détail'}).click();
   for(const name of ['Projets','Simulateur','Sources','Nouveautés','Explorer']){
    await page.getByRole('tab',{name,exact:true}).click();
    if(name==='Simulateur'){await page.getByLabel('Prix d’achat',{exact:false}).fill('100000');assert.equal(await page.getByLabel('Prix d’achat',{exact:false}).inputValue(),'100000')}
   }
   assert.equal(errors.length,0,JSON.stringify(errors));fs.writeFileSync(path.join(out,mobile?'mobile-network.json':'desktop-network.json'),JSON.stringify({errors,failed},null,2));await context.close();
  }
  fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});

