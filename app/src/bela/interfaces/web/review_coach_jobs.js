"use strict";

let reviewCoachRun=null,reviewCoachDepth="standard",reviewCoachRepeat=false;
const reviewCoachRunning=()=>!!reviewCoachRun?.running;
const coachDelay=()=>new Promise(resolve=>setTimeout(resolve,350));

function refreshCoachPanels(){
  renderReviewCoach();
  if(reviewPosition())renderReviewEngine();
}

function stopGameReview(){
  const run=reviewCoachRun;
  if(!run?.running)return;
  run.stopped=true;run.message="Stopping game review…";
  if(run.jobId)request("/api/review/analysis/cancel",{...run.context,job_id:run.jobId}).catch(()=>{});
  refreshCoachPanels();
}

async function startGameReview(){
  if(!reviewData||reviewCoachRunning()||reviewRunning())return;
  const data=reviewData,deep=reviewCoachDepth==="deep";
  const queue=coachSummary(data).decisions.filter(d=>d.assessment.kind!=="forced"&&
    (reviewCoachRepeat||!d.assessment.evaluated));
  const run={running:true,stopped:false,completed:0,total:queue.length,jobId:null,
    context:{expected_id:data.match_id,expected_revision:data.revision},
    message:queue.length?"Reviewing your decisions…":"All recorded choices already have an evaluation."};
  reviewCoachRun=run;refreshCoachPanels();
  try{
    for(const item of queue){
      if(run.stopped||reviewData!==data)break;
      let job=await request("/api/review/analysis/start",{...run.context,key:item.position.key,
        config:{samples:deep?512:128,seconds:deep?15:8,seed:42,policy:"mixed_match_v1",
          self_policy:"direct_competent_mix_v1",exact_endgame:true,objective:typeof recommendedLiveObjective==="function"?
            recommendedLiveObjective({setup:data.deals[item.deal].setup,awarded_melds:item.position.position.awarded_melds}):"point_difference"}});
      run.jobId=job.id;
      if(run.stopped||reviewData!==data)await request("/api/review/analysis/cancel",{...run.context,job_id:job.id});
      while(["running","cancelling"].includes(job.state)){
        await coachDelay();
        job=await request("/api/review/analysis?id="+encodeURIComponent(job.id));
      }
      if(job.match_id!==data.match_id||job.revision!==data.revision||job.position_key!==item.position.key)
        throw Error(t("The match changed. Reload the analysis board."));
      if(job.state!=="finished"||!job.result)throw Error(job.error||t("Game review stopped. Completed evaluations are saved."));
      if(!item.position.advice.some(r=>r.record_id===job.id))item.position.advice.push({record_id:job.id,
        created_at:new Date().toISOString(),source:"dashboard_review",advice:job.result});
      // Keep results on their exact frame, even when the user navigates elsewhere.
      item.position.selectedAnalysis=job.id;
      run.completed++;run.jobId=null;
      if(!run.stopped&&!coachAssessment(item.position,{advice:job.result}).evaluated)
        throw Error(t("A decision produced too few complete trials. Completed evaluations are saved; try this position separately."));
      if(reviewData===data)refreshCoachPanels();
    }
    run.message=run.stopped?"Review stopped. Completed evaluations are saved.":
      queue.length?"Game review complete. Evaluations are saved.":"All recorded choices already have an evaluation.";
  }catch(error){
    // A polling error must not leave an expensive worker running unnoticed.
    if(run.jobId)await request("/api/review/analysis/cancel",{...run.context,job_id:run.jobId}).catch(()=>{});
    run.message=error.message;
  }finally{
    run.running=false;run.jobId=null;
    if(reviewData)refreshCoachPanels();
  }
}

window.addEventListener("beforeunload",()=>{
  if(!reviewCoachRunning())return;
  reviewCoachRun.stopped=true;
  // No further positions are queued after the page closes. The active worker
  // remains bounded to 8/15 seconds and journals its result server-side.
});
