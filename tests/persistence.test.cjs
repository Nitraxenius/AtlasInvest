const assert=require('node:assert/strict');
const fs=require('node:fs');
const {execFileSync}=require('node:child_process');
const root='http://127.0.0.1:3000/api/atlas/';
(async()=>{
 const before=await(await fetch(root+'manifest')).json();
 execFileSync('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',['-NoProfile','-File','scripts/atlas.ps1','restart','data','scheduler','web'],{stdio:'inherit'});
 let after;for(let i=0;i<60;i++){try{const response=await fetch(root+'manifest');if(response.ok){after=await response.json();break}}catch{}await new Promise(r=>setTimeout(r,1000))}
 assert.equal(after.version,before.version);const cities={};
 for(const city of ['laval','tours']){const response=await fetch(root+'versions/'+after.version+'/'+city+'.json');assert.equal(response.status,200);const data=await response.json();cities[city]={communes:data.communes.features.length,transactions:data.transactions.length,years:Object.keys(data.audit)}}
 fs.mkdirSync('outputs/browser',{recursive:true});fs.writeFileSync('outputs/browser/persistence.json',JSON.stringify({version:after.version,cities},null,2));console.log({version:after.version,cities});
})().catch(e=>{console.error(e);process.exit(1)});
