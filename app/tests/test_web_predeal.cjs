const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const elements=new Map(),storage=new Map(),source={expected_id:null,expected_revision:0};
const el=id=>{if(!elements.has(id))elements.set(id,{value:'',hidden:false,disabled:false,textContent:'',handlers:{},
  addEventListener(t,f){this.handlers[t]=f;},showModal(){this.open=true;},close(){this.open=false;}});return elements.get(id);};
const six='C_9 C_J C_K H_A S_Q D_A'.split(' ');
const ctx=vm.createContext({$:el,t:s=>s,setupMode:'new',setupCards:new Set(six),trumpCards:new Set(),trumpRunning:false,
 DECK:six.concat(['H_7','S_7']),sortedCards:set=>[...set].sort(),context:()=>({...source}),
 localStorage:{setItem(k,v){storage.set(k,v);},getItem:k=>storage.get(k)??null,removeItem:k=>storage.delete(k)},
 switchView:v=>ctx.view=v,trumpChanged:()=>{},startTrump:()=>ctx.started=(ctx.started??0)+1,
 renderSetupPicker:()=>{},showError:s=>ctx.error=s});
el('setup-name').value='Six-card match';el('setup-player').value='0';el('setup-dealer').value='3';
el('setup-score0').value='100';el('setup-score1').value='200';
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/predeal.js'),'utf8'),ctx);
vm.runInContext('renderSetupStage()',ctx);
assert.equal(el('setup-caller-label').hidden,true);assert.equal(el('setup-caller').disabled,true);
assert.equal(el('setup-trump').disabled,true);
vm.runInContext('beginCallingSetup()',ctx);
assert.equal(ctx.started,1);assert.equal(ctx.view,'trump');assert.equal(ctx.trumpCards.size,6);
assert.equal(el('predeal-name').textContent,'Six-card match');
const draft=storage.get('bela.predeal.v1');assert.equal(JSON.parse(draft).six.length,6);
vm.runInContext('continueCallingSetup()',ctx);
assert.equal(vm.runInContext('setupStage',ctx),'eight');assert.equal(ctx.setupCards.size,6);
assert.equal(el('setup-caller').value,'');assert.equal(el('setup-trump').value,'');
assert.equal(el('setup-caller').disabled,false);assert.equal(el('setup-trump').disabled,false);
assert.equal(el('setup-score0').value,100);assert.equal(el('setup-score1').value,200);
vm.runInContext('clearPredeal()',ctx);assert.equal(storage.has('bela.predeal.v1'),false);
storage.set('bela.predeal.v1',draft);ctx.trumpCards=new Set();vm.runInContext('restorePredeal()',ctx);
assert.equal(ctx.trumpCards.size,6);assert.equal(ctx.started,1,'Restore does not silently start new simulations');
source.expected_revision=1;vm.runInContext('continueCallingSetup()',ctx);
assert.match(ctx.error,/current match changed/);
vm.runInContext('clearPredeal()',ctx);
console.log('Six-card setup, actual-call confirmation, draft restore and stale-context checks passed.');
