const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=name=>fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/'+name),'utf8');
function setup(request){
 const frames=['one','two'].map(key=>({key,position:{can_analyse:true},legal_cards:['H_J','H_7'],played:{card:'H_J'},advice:[]}));
 const ctx=vm.createContext({request,reviewData:{match_id:'saved',revision:30,deals:[{frames}]},
  reviewRunning:()=>false,renderReviewCoach:()=>{},reviewPosition:()=>null,renderReviewEngine:()=>{},
  window:{addEventListener:()=>{}},$:()=>null,setTimeout:fn=>{fn();return 1;},t:s=>s,Date,encodeURIComponent});
 vm.runInContext(source('review_coach.js'),ctx);vm.runInContext(source('review_coach_jobs.js'),ctx);
 return ctx;
}
const result={config:{objective:'point_difference'},completed_samples:10,moves:[
 {card:'H_J',rank:1,samples:10,expected_point_difference:3},{card:'H_7',rank:2,samples:10,expected_point_difference:2}],comparisons:[]};
(async()=>{
 const requests=[];let active=0;
 const ctx=setup(async(url,body)=>{requests.push({url,body});
  if(url.endsWith('/start')){assert.equal(active,0);active++;return{id:body.key,state:'running'};}
  if(url.includes('?id=')){active--;return{id:url.split('=')[1],state:'finished',match_id:'saved',revision:30,position_key:url.split('=')[1],result};}
  return{};
 });
 await vm.runInContext('startGameReview()',ctx);
 assert.equal(requests.filter(r=>r.url.endsWith('/start')).length,2);
 assert.equal(ctx.reviewData.deals[0].frames[1].advice.length,1);
 for(const r of requests.filter(r=>r.body?.config)){assert.equal(r.body.config.seconds,8);assert.equal(r.body.expected_revision,30);}
 await vm.runInContext('startGameReview()',ctx);assert.equal(requests.filter(r=>r.url.endsWith('/start')).length,2);
 vm.runInContext('reviewCoachDepth="deep";reviewCoachRepeat=true;',ctx);
 await vm.runInContext('startGameReview()',ctx);assert.equal(requests.filter(r=>r.body?.config).at(-1).body.config.samples,512);
 // Stop while start request is in flight: cancel that worker and never queue two.
 let resolveStart,starts=0,cancels=0;
 const stopped=setup((url,body)=>{
  if(url.endsWith('/start')){starts++;return new Promise(resolve=>resolveStart=resolve);}
  if(url.endsWith('/cancel')){cancels++;return Promise.resolve({});}
  return Promise.resolve({id:'one',state:'finished',match_id:'saved',revision:30,position_key:'one',result});
 });
 const pending=vm.runInContext('startGameReview()',stopped);vm.runInContext('stopGameReview()',stopped);
 resolveStart({id:'one',state:'running'});await pending;assert.equal(starts,1);assert.equal(cancels,1);
 // Stale result cannot be attached to a different historical position.
 const stale=setup(async()=>({id:'stale',state:'finished',match_id:'saved',revision:31,position_key:'one',result}));
 await vm.runInContext('startGameReview()',stale);assert.equal(stale.reviewData.deals[0].frames[0].advice.length,0);
 assert.equal(vm.runInContext('reviewCoachRunning()',stale),false);
 console.log('Sequential game review, resume, depth, cancellation race and stale-result isolation checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
