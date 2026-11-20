const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const requests=[],pending=[];
const ctx=vm.createContext({
 reviewData:{match_id:'saved-match',revision:40,deals:[{frames:[
  {key:'first',position:{can_analyse:true},advice:[]},
  {key:'second',position:{can_analyse:true},advice:[]}
 ]}]},reviewDeal:0,reviewFrame:0,
 request:(url,body)=>{requests.push({url,body});if(url.endsWith('/start'))return new Promise(resolve=>pending.push(resolve));return Promise.resolve({});},
 setTimeout:()=>1,clearTimeout:()=>{},Date,encodeURIComponent
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/bela/interfaces/web/review_analysis.js'),'utf8'),ctx);
vm.runInContext('renderReviewEngine=()=>{}',ctx);
(async()=>{
 const first=vm.runInContext('startReviewAnalysis(false)',ctx);
 assert.equal(requests[0].body.expected_id,'saved-match');
 assert.equal(requests[0].body.config.samples,128);
 vm.runInContext('abandonReviewAnalysis();reviewFrame=1;',ctx);
 pending.shift()({id:'old-job',match_id:'saved-match',revision:40,position_key:'first',state:'running'});
 await first;
 assert.equal(requests.at(-1).url,'/api/review/analysis/cancel');
 assert.equal(requests.at(-1).body.expected_id,'saved-match');
 assert.equal(requests.at(-1).body.expected_revision,40);
 assert.equal(vm.runInContext('reviewJob',ctx),null);
 const second=vm.runInContext('startReviewAnalysis(true)',ctx);
 assert.equal(requests.at(-1).body.key,'second');
 assert.equal(requests.at(-1).body.config.samples,512);
 assert.equal(requests.at(-1).body.config.seconds,15);
 pending.shift()({id:'new-job',match_id:'saved-match',revision:40,position_key:'second',state:'finished',result:{moves:[],completed_samples:512}});
 await second;
 assert.equal(ctx.reviewData.deals[0].frames[0].advice.length,0);
 assert.equal(ctx.reviewData.deals[0].frames[1].advice.length,1);
 assert.equal(ctx.reviewData.deals[0].frames[1].advice[0].source,'dashboard_review');
 vm.runInContext('acceptReviewJob(reviewJob,reviewIdentity(),reviewJobSerial)',ctx);
 assert.equal(ctx.reviewData.deals[0].frames[1].advice.length,1);
 vm.runInContext('reviewData.deals[0].frames[1].position.can_analyse=false',ctx);
 const count=requests.length;await vm.runInContext('startReviewAnalysis(false)',ctx);
 assert.equal(requests.length,count);
 console.log('Historical analysis context, navigation races, result isolation and budget checks passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
