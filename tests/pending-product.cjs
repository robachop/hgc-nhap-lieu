const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const repo=path.resolve(__dirname,'..');
const ctx=vm.createContext({console,fetch:()=>{throw Error('Live network prohibited')},setTimeout:()=>{},Date});
vm.runInContext(fs.readFileSync(path.join(repo,'js/lsx_data.js'),'utf8'),ctx);
vm.runInContext(fs.readFileSync(path.join(repo,'js/entry.js'),'utf8'),ctx);
const run=s=>vm.runInContext(s,ctx);
for(const chain of '123456789X')for(const [tank,digit] of Object.entries({L113:1,L114:2,L133:3,L134:4,L138:5,L213:6})){
 for(const alias of [`Px${chain}0`,`PX${chain}0`,`Pz${chain}0`,`PZ${chain}0`])assert.equal(run(`resolveProductCode('${alias}','${tank}')`),`P${digit}${chain}0`);
}
assert.equal(run("normalizeProductCode('PX00')"),'PX00');assert.equal(run("isPendingProductCode('PX00')"),false);
run(`var saves=0, sent=0, warnings=[]; var state={workerName:'Phong',date:'2026-10-28',plan:{tasks:[]}};
function saveResult(){saves++} function savePlan(){} function toast(s){warnings.push(s)}
var inputs={'ai-lsx':'PX70','ai-cap':'T150','ai-nhan':'L213','ai-lo':'','ai-luong':'1500','ai-ghichu':'','ai-ngay':'2026-10-28'};
var document={getElementById:(id)=>({value:inputs[id]||''})}; renderWorkerTasks=()=>{};
inlineSt='done';currentResult={results:[]};submitWorkerTask();`);
assert.equal(run('state.plan.tasks[0].lsx'),'Pz70');assert.equal(run('currentResult.results[0].lsx'),'P670');
run(`state.plan={tasks:[{id:'t1',lsx:'Pz50',be_nhan:'Bể TP'}]};currentResult={results:[{task_id:'t1',lsx:'PX50',be_nhan:'L213',status:'done'}]};doSubmit=()=>{sent++};submitResult();`);
assert.equal(run('currentResult.results[0].lsx'),'P650');assert.equal(run('sent'),1);
run(`currentResult={results:[{task_id:'t1',lsx:'PZ50',be_nhan:'L999',status:'done'}]};submitResult();`);assert.equal(run('sent'),1);
run(`currentResult={results:[{task_id:'t1',lsx:'Pz50',be_nhan:'T099',status:'done'}]};submitResult();`);assert.equal(run('sent'),2);
run(`currentResult={results:[{task_id:'t1',lsx:'PX00',be_nhan:'L072',status:'done'}]};submitResult();`);assert.equal(run('currentResult.results[0].lsx'),'PX00');
console.log('PASS: 240 mapping cases, worker-added uppercase alias, submit resolution, invalid destination block, temporary tank and PX00 preserved; network mocked');
