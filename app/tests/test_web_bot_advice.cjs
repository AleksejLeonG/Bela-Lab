const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const calls=[];
const ctx=vm.createContext({state:{bot:{calling:false,awaiting_trick:false}},currentView:'table',
 botMode:()=>true,adviceOwnTurn:()=>true,adviceSource:()=>ctx.key,adviceKey:'one',adviceJob:null,adviceStarting:false,
 $:()=>null,startAdvice:config=>calls.push(config)});ctx.key='one';
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/bot_advice.js'),'utf8'),ctx);
vm.runInContext('syncBotAdvice();syncBotAdvice()',ctx);assert.equal(calls.length,1);
assert.equal(calls[0].samples,128);assert.equal(calls[0].objective,'point_difference');
assert.equal(calls[0].self_policy,'direct_competent_mix_v1');
assert.equal(calls[0].exact_endgame,true);
vm.runInContext('runLiveComparison("point_difference",true)',ctx);
assert.deepEqual({...calls.pop(),samples:128,seconds:8},{...calls[0]});
ctx.state.bot.awaiting_trick=true;ctx.key='two';vm.runInContext('syncBotAdvice()',ctx);assert.equal(calls.length,1);
ctx.state.bot.awaiting_trick=false;ctx.currentView='review';vm.runInContext('syncBotAdvice()',ctx);assert.equal(calls.length,1);
ctx.currentView='table';vm.runInContext('syncBotAdvice()',ctx);assert.equal(calls.length,2);
ctx.state.bot.calling=true;ctx.key='three';vm.runInContext('syncBotAdvice()',ctx);assert.equal(calls.length,2);
console.log('Automatic bot advice runs once per position, uses recommended settings and respects trick/calling/navigation boundaries.');
ctx.match={setup:{caller:1},trick_counts:[0,2],trick_points:[0,42],awarded_melds:[0,200],bela_players:[]};
assert.equal(vm.runInContext('publicContractSecured(match)',ctx),true);
ctx.match.trick_counts=[0,0];assert.equal(vm.runInContext('publicContractSecured(match)',ctx),false);
ctx.match.trick_counts=[0,2];ctx.match.awarded_melds=[0,0];assert.equal(vm.runInContext('publicContractSecured(match)',ctx),false);
