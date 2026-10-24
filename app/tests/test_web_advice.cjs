// Run with: node app/tests/test_web_advice.cjs
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

async function main(){
  const pending=[],timers=new Map(),elements=new Map();let timerId=0;
  for(const [id,value] of Object.entries({"advice-samples":"64","advice-seed":"42",
    "advice-policy":"mixed_match_v1","advice-objective":"point_difference",
    "advice-start":"","advice-cancel":""})){
    elements.set(id,{value,handlers:{},addEventListener(type,fn){this.handlers[type]=fn;}});
  }
  const context=vm.createContext({state:{match:{id:"a",revision:1,deal_number:1,phase:"playing",next_player:0,setup:{player:0}}},
    language:"en",t:value=>value,$:id=>elements.get(id),context:()=>({expected_id:context.state.match.id,expected_revision:context.state.match.revision}),
    fetch:()=>new Promise(resolve=>pending.push(resolve)),setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},
    clearTimeout:id=>timers.delete(id),request:async()=>context.state,render:()=>{},selectedPlay:null});
  vm.runInContext(fs.readFileSync(path.join(__dirname,"../src/bela/interfaces/web/advice.js"),"utf8"),context);
  vm.runInContext("renderAdvice=()=>{};initAdvice();syncAdvice()",context);
  const job=(id,revision,state="finished")=>({id,match_id:"a",revision,deal_number:1,state,result:null,error:null});
  const respond=(index,data,status=200)=>pending[index]({ok:status===200,status,json:async()=>data});

  const old=vm.runInContext("startAdvice()",context);
  context.state.match.revision=2;vm.runInContext("syncAdvice()",context);
  respond(0,job("old",1));await old;
  assert.equal(vm.runInContext("adviceJob",context),null,"Old start response must be ignored");

  const fresh=vm.runInContext("startAdvice()",context);
  respond(1,job("current",2,"running"));await fresh;
  assert.equal(vm.runInContext("adviceJob.id",context),"current");
  const poll=vm.runInContext("pollAdvice(adviceJob.id,adviceKey,adviceSerial)",context);
  const cancel=vm.runInContext("cancelAdvice()",context);
  respond(2,job("current",2));await poll;
  assert.equal(vm.runInContext("adviceJob.state",context),"cancelling","Old poll must not override cancellation");
  respond(3,job("current",2));await cancel;
  assert.equal(vm.runInContext("adviceJob.state",context),"finished");

  elements.get("advice-policy").handlers.change();
  assert.equal(vm.runInContext("adviceJob",context),null,"Changed settings invalidate old estimates");
  const switched=vm.runInContext("startAdvice()",context);
  context.state.match={...context.state.match,id:"b",revision:1};vm.runInContext("syncAdvice()",context);
  respond(4,job("previous-match",2));await switched;
  assert.equal(vm.runInContext("adviceJob",context),null,"Switched matches invalidate pending work");

  context.state.match={...context.state.match,id:"a",revision:3};vm.runInContext("syncAdvice()",context);
  const failed=vm.runInContext("startAdvice()",context);
  respond(5,{error:"Bad configuration"},422);await failed;
  assert.equal(vm.runInContext("adviceStarting",context),false);
  assert.equal(vm.runInContext("adviceError",context),"Bad configuration");
  assert.equal(vm.runInContext("adviceJob",context),null);
  console.log("Advice revision, match switching, cancellation ordering and settings checks passed.");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
