const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

async function main(){
  const elements=new Map(),pending=[],requests=[];
  for(const [id,value] of Object.entries({'trump-player':'0','trump-dealer':'3','trump-samples':'128',
    'trump-seconds':'5','trump-seed':'42','trump-condition':'','trump-selected':'','trump-position':'',
    'trump-start':'','trump-status':'','trump-results':'','trump-picker':'','trump-use-monte-carlo':''})){
    elements.set(id,{value,checked:false,handlers:{},textContent:'',innerHTML:'',
      addEventListener(type,fn){this.handlers[type]=fn;}});
  }
  elements.get('trump-use-monte-carlo').checked=true; // Existing asynchronous MC scenarios remain explicit.
  const context=vm.createContext({$:id=>elements.get(id),language:'en',t:s=>s,
    l:(strings,...values)=>strings.reduce((s,v,i)=>s+v+(values[i]??''),''),
    picker(){},toggleCard:(set,c,max)=>{if(set.has(c))set.delete(c);else if(set.size<max)set.add(c);},
    sortedCards:set=>[...set].sort(),SYMBOLS:{H:'♥',C:'♣',D:'♦',S:'♠'},
    suitPrefix:s=>({H:'♥',C:'♣',D:'♦',S:'♠'}[s]),
    suitNames:()=>({H:'Hearts',C:'Clubs',D:'Diamonds',S:'Spades'}),escapeHtml:s=>String(s),
    fetch:(url,options)=>new Promise(resolve=>{requests.push({url,options});pending.push(resolve);})});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/trump.js'),'utf8'),context);
  vm.runInContext('initTrump()',context);
  assert.equal(elements.get('trump-start').disabled,true);
  vm.runInContext('trumpCards=new Set("C_9 C_J C_K H_A S_Q D_A".split(" "));renderTrump()',context);
  assert.equal(elements.get('trump-start').disabled,false);
  const fixture={status:'complete',completed_samples:128,elapsed_seconds:1,recommendation:{action:'call',suit:'C'},
    recommendation_source:'monte_carlo',rankings:[{rank:1,action:'call',suit:'C',
      expected_point_difference:50,success_probability:.8,success_interval:[.4,1],objective_interval:[-50,150],not_separated_from_leader:true}]};
  const respond=(index,data,ok=true)=>pending[index]({ok,json:async()=>data});
  const first=vm.runInContext('startTrump()',context);
  await vm.runInContext('startTrump()',context);
  assert.equal(requests.length,1,'Only one request at a time');
  const body=JSON.parse(requests[0].options.body);
  assert.equal(body.hand.length,6);
  assert.deepEqual(body.passes,[]);
  assert.equal(body.config.condition_on_passes,false);
  assert.equal(body.expected_id,undefined,'Pre-deal tool is independent of the open match');
  elements.get('trump-dealer').value='0';elements.get('trump-dealer').handlers.change();
  respond(0,fixture);await first;
  assert.equal(vm.runInContext('trumpResult',context),null,'Changed input invalidates an old response');
  const second=vm.runInContext('startTrump()',context);
  assert.deepEqual(JSON.parse(requests[1].options.body).passes,[1,2,3]);
  respond(1,fixture);await second;
  assert.match(elements.get('trump-results').innerHTML,/80.0%/);
  assert.match(elements.get('trump-position').textContent,/Dealer must call/);
  elements.get('trump-condition').checked=true;elements.get('trump-condition').handlers.change();
  assert.equal(vm.runInContext('trumpResult',context),null);
  const failed=vm.runInContext('startTrump()',context);
  assert.equal(JSON.parse(requests[2].options.body).config.condition_on_passes,true);
  respond(2,{error:'Invalid input'},false);await failed;
  assert.equal(elements.get('trump-status').textContent,'Invalid input');
  assert.equal(elements.get('trump-start').disabled,false);
  const fallback=vm.runInContext('startTrump()',context);
  respond(3,{...fixture,status:'time_limit',completed_samples:0,recommendation_source:'heuristic_fallback',
    rankings:fixture.rankings.map(r=>({...r,rank:null,expected_point_difference:null,success_probability:null,
      success_interval:null,objective_interval:null,not_separated_from_leader:null}))});await fallback;
  assert.match(elements.get('trump-results').innerHTML,/heuristic fallback/);
  assert.ok(!elements.get('trump-results').innerHTML.includes('0.0%'),'No invented zero-sample probability');
  elements.get('trump-use-monte-carlo').checked=false;
  elements.get('trump-use-monte-carlo').handlers.change();
  const recommended=vm.runInContext('startTrump()',context);
  assert.equal(JSON.parse(requests[4].options.body).method,'position_control_v2');
  assert.deepEqual(JSON.parse(requests[4].options.body).config,{});
  respond(4,{method:'position_control_v2',recommendation:{action:'call',suit:'C'},
    rankings:[{rank:1,action:'call',suit:'C',score:75,trump_count:3}]});await recommended;
  assert.match(elements.get('trump-results').innerHTML,/Hand-strength score/);
  assert.ok(!elements.get('trump-results').innerHTML.includes('%'),'Recommended heuristic does not invent probabilities');
  const html=fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/index.html'),'utf8');
  assert.match(html,/<details[^>]*id="trump-experimental"[^>]*>/);
  assert.ok(!html.match(/id="trump-use-monte-carlo"[^>]*checked/),'MC is opt-in');
  console.log('Trump settings, stale responses, forced calls, estimates and fallback display checks passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
