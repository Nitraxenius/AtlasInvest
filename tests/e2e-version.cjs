const assert=require('node:assert/strict');const {execFileSync}=require('node:child_process');const fs=require('node:fs');
const {chromium}=require(process.env.ATLAS_PLAYWRIGHT||'C:/Users/sribeiro/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const docker=process.env.ATLAS_DOCKER||'C:/Users/sribeiro/AppData/Local/Programs/DockerDesktop/resources/bin/docker.exe';
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});const page=await browser.newPage();
 try{
  execFileSync(docker,['compose','-f','compose.demo.yaml','exec','-T','data','python','-m','service.demo','publish','--generation','1'],{stdio:'pipe'});
  await page.goto('http://127.0.0.1:3001');await page.locator('.zone-card').first().waitFor();
  const before=(await (await fetch('http://127.0.0.1:3001/api/atlas/manifest')).json()).version;
  const oldText=await page.locator('.zone-card').first().innerText();
  execFileSync(docker,['compose','-f','compose.demo.yaml','exec','-T','data','python','-m','service.demo','publish','--generation','2'],{stdio:'pipe'});
  const after=(await (await fetch('http://127.0.0.1:3001/api/atlas/manifest')).json()).version;assert.notEqual(before,after);
  // Wait for the normal client poll, without navigation, image build or reload.
  await page.waitForFunction(old=>document.querySelector('.zone-card')?.innerText!==old,oldText,{timeout:80000});
  const newText=await page.locator('.zone-card').first().innerText();assert.notEqual(oldText,newText);
  fs.mkdirSync('outputs/browser',{recursive:true});await page.screenshot({path:'outputs/browser/fixture-generation-2.png',fullPage:true});
  fs.writeFileSync('outputs/browser/e2e-version.json',JSON.stringify({before,after,oldText,newText,reload:false,rebuild:false},null,2));console.log('Fixture version promoted and visible in the map without reload/rebuild');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
