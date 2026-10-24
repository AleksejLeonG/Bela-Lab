// Run with: node app/tests/test_web_knowledge.cjs
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const vm=require("node:vm");

async function main(){
  const pending=[];
  const context=vm.createContext({state:{match:{id:"match-a",revision:1,deal_number:1}},
    language:"en",t:text=>text,fetch:()=>new Promise(resolve=>pending.push(resolve)),
    selectedPlay:null});
  vm.runInContext(fs.readFileSync(path.join(__dirname,"../src/bela/interfaces/web/knowledge.js"),"utf8"),context);
  vm.runInContext("renderKnowledge=()=>{}",context);
  const first=vm.runInContext("loadKnowledge()",context);
  context.state.match={id:"match-a",revision:2,deal_number:1};
  const second=vm.runInContext("loadKnowledge()",context);
  assert.equal(pending.length,2);
  pending[0]({ok:true,json:async()=>({match_id:"match-a",revision:1,deal_number:1})});
  await first;
  assert.equal(vm.runInContext("knowledgeData",context),null);
  pending[1]({ok:true,json:async()=>({match_id:"match-a",revision:2,deal_number:1})});
  await second;
  assert.equal(vm.runInContext("knowledgeData.revision",context),2);
  await vm.runInContext("loadKnowledge()",context);
  assert.equal(pending.length,2,"Current cached knowledge should not fetch again");
  // Next deal and switched matches invalidate the previous result too.
  context.state.match={id:"match-a",revision:3,deal_number:2};
  const nextDeal=vm.runInContext("loadKnowledge()",context);
  context.state.match={id:"match-b",revision:1,deal_number:1};
  const switched=vm.runInContext("loadKnowledge()",context);
  pending[2]({ok:true,json:async()=>({match_id:"match-a",revision:3,deal_number:2})});
  await nextDeal;
  assert.equal(vm.runInContext("knowledgeData.match_id",context),"match-a");
  pending[3]({ok:true,json:async()=>({match_id:"match-b",revision:1,deal_number:1})});
  await switched;
  assert.equal(vm.runInContext("knowledgeData.match_id",context),"match-b");
  const failed=vm.runInContext("loadKnowledge(true)",context);
  pending[4]({ok:false,json:async()=>({error:"Temporary error"})});
  await failed;
  assert.equal(vm.runInContext("knowledgeError",context),"Temporary error");
  assert.equal(vm.runInContext("knowledgeLoading",context),false);
  console.log("Knowledge revision, request ordering and refresh checks passed.");
}
main().catch(error=>{console.error(error);process.exitCode=1;});
