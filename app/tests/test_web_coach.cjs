const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const ctx=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/review_coach.js'),'utf8'),ctx);
const frame=()=>({position:{can_analyse:true,trick:{plays:[]}},legal_cards:['H_J','H_7'],played:{card:'H_J'},advice:[]});
function record(gap=10,interval=[2,18]){return {record_id:'test',advice:{config:{objective:'point_difference'},completed_samples:100,
 moves:[{card:'H_7',rank:1,samples:100,expected_point_difference:20},{card:'H_J',rank:2,samples:100,expected_point_difference:20-gap}],
 comparisons:[{first:'H_7',second:'H_J',mean_difference:gap,interval}]}};}
ctx.frame=frame();ctx.record=record();
const assess=()=>vm.runInContext('coachAssessment(frame,record)',ctx);
assert.equal(assess().kind,'opportunity');assert.equal(assess().gap,10);assert.equal(assess().major,false);
ctx.record=record(20,[1,39]);assert.equal(assess().major,true);
ctx.record=record(20,[-1,41]);assert.equal(assess().kind,'uncertain');
ctx.record=record(3,[1,5]);assert.equal(assess().kind,'close');assert.equal(assess().clear,true);
ctx.record=record(0,[-2,2]);assert.equal(assess().kind,'leading');
ctx.record=record();ctx.record.advice.comparisons=[{first:'H_J',second:'H_7',mean_difference:-10,interval:[-18,-2]}];assert.equal(assess().clear,true);
ctx.record.advice.comparisons=[];assert.equal(assess().kind,'uncertain');
ctx.record=record();ctx.record.advice.comparisons[0].interval=[12,18];assert.equal(assess().clear,false);
ctx.record=record();ctx.record.advice.completed_samples=0;assert.equal(assess().kind,'pending');
Object.assign(ctx.record.advice,{exact_layouts:12,comparisons:[{first:'H_7',second:'H_J',mean_difference:0,interval:[0,0]}]});
ctx.record.advice.moves.forEach(row=>Object.assign(row,{samples:0,rank:1,expected_point_difference:20}));
ctx.record.advice.moves[1].proven_tie_with_leader=true;
assert.equal(assess().exactTie,true);assert.equal(assess().provenTie,true);assert.equal(assess().gap,0);
ctx.record=record();ctx.record.advice.moves[0].samples=99;assert.equal(assess().kind,'pending');
ctx.record=record();ctx.record.advice.moves.pop();assert.equal(assess().kind,'pending');
ctx.record=record();ctx.record.advice.config.objective='contract_success';assert.equal(assess().kind,'different_objective');
ctx.frame=frame();ctx.frame.legal_cards=['H_J'];assert.equal(assess().kind,'forced');
ctx.frame.position.can_analyse=false;assert.equal(assess().kind,'other');
ctx.frame=frame();ctx.record=record();ctx.frame.advice=[ctx.record];
ctx.frame.advice.push(record(9,[-2,20]));ctx.frame.advice.push({advice:{config:{objective:'contract_success'}}});
assert.equal(vm.runInContext('coachAssessment(frame,coachRecord(frame)).kind',ctx),'uncertain');
// Results, opponents' subsequent plays and final scores cannot enter a grade.
ctx.deal={setup:{trump:'H',player:0},frames:[ctx.frame,{...frame(),position:{can_analyse:false}}]};
ctx.data={deals:[ctx.deal]};const before=vm.runInContext('JSON.stringify(coachSummary(data))',ctx);
ctx.deal.score=[999,0];ctx.deal.frames[1].played.card='S_A';
assert.equal(vm.runInContext('JSON.stringify(coachSummary(data))',ctx),before);
ctx.a=vm.runInContext('coachAssessment(frame,record)',ctx);
assert.deepEqual(Array.from(vm.runInContext('coachFacts(frame,deal,a).map(f=>f.type)',ctx)),['retain_stronger','fewer_points']);
assert.equal(vm.runInContext('coachSummary(data).decisions.length',ctx),1);
console.log('Coach paired-interval direction, uncertainty, missing/partial data, objective isolation, latest evidence, forced moves and no hindsight checks passed.');
ctx.frame=frame();ctx.record=record();ctx.record.advice.config.objective='match_outcome';
Object.assign(ctx.record.advice.moves[0],{expected_point_difference:-100,objective_mean:1,our_match_win_probability:1,opponent_match_win_probability:0});
Object.assign(ctx.record.advice.moves[1],{expected_point_difference:100,objective_mean:-1,our_match_win_probability:0,opponent_match_win_probability:1});
ctx.record.advice.comparisons=[{first:'H_7',second:'H_J',mean_difference:2,interval:[1,2]}];
assert.equal(assess().metric,'match');assert.equal(assess().kind,'opportunity');
