"use strict";

let reviewJob=null, reviewJobSerial=0, reviewJobTimer=null, reviewStarting=false, reviewEngineError="";
const reviewPosition=()=>reviewData?.deals[reviewDeal]?.frames[reviewFrame];
const reviewIdentity=()=>reviewData?`${reviewData.match_id}:${reviewData.revision}:${reviewPosition()?.key}`:null;
const reviewRunning=()=>reviewStarting||["running","cancelling"].includes(reviewJob?.state);

function abandonReviewAnalysis(){
  clearTimeout(reviewJobTimer);reviewJobSerial++;
  if(reviewJob&&["running","cancelling"].includes(reviewJob.state)&&reviewData){
    request("/api/review/analysis/cancel",{expected_id:reviewData.match_id,
      expected_revision:reviewData.revision,job_id:reviewJob.id}).catch(()=>{});
  }
  reviewJob=null;reviewStarting=false;reviewEngineError="";
}

async function startReviewAnalysis(longer=false){
  const frame=reviewPosition();
  if(!frame?.position.can_analyse||reviewRunning()||(typeof reviewCoachRunning==="function"&&reviewCoachRunning()))return;
  const identity=reviewIdentity(),serial=++reviewJobSerial;
  const inputContext={expected_id:reviewData.match_id,expected_revision:reviewData.revision};
  const objective=typeof recommendedLiveObjective==="function"?recommendedLiveObjective({setup:reviewData.deals[reviewDeal].setup,awarded_melds:frame.position.awarded_melds}):"point_difference";
  reviewStarting=true;reviewJob=null;reviewEngineError="";renderReviewEngine();
  try{
    const job=await request("/api/review/analysis/start",{...inputContext,key:frame.key,config:{samples:longer?512:128,
        seconds:longer?15:8,seed:42,policy:"mixed_match_v1",self_policy:"direct_competent_mix_v1",exact_endgame:true,objective}});
    if(serial!==reviewJobSerial||identity!==reviewIdentity()){
      request("/api/review/analysis/cancel",{...inputContext,job_id:job.id}).catch(()=>{});return;
    }
    reviewStarting=false;acceptReviewJob(job,identity,serial);
  }catch(error){
    if(serial!==reviewJobSerial||identity!==reviewIdentity())return;
    reviewStarting=false;reviewEngineError=error.message;renderReviewEngine();
    if(typeof renderReviewCoach==="function")renderReviewCoach();
  }
}

function acceptReviewJob(job,identity,serial){
  if(serial!==reviewJobSerial||identity!==reviewIdentity())return;
  if(job.position_key!==reviewPosition()?.key||job.match_id!==reviewData.match_id||job.revision!==reviewData.revision)return;
  reviewJob=job;
  if(job.state==="finished"&&job.result){
    const frame=reviewPosition();
    if(!frame.advice.some(r=>r.record_id===job.id))frame.advice.push({record_id:job.id,
      created_at:new Date().toISOString(),source:"dashboard_review",advice:job.result});
    frame.selectedAnalysis=job.id;
  }
  renderReviewEngine();
  if(typeof renderReviewCoach==="function")renderReviewCoach();
  if(["running","cancelling"].includes(job.state)){
    clearTimeout(reviewJobTimer);
    reviewJobTimer=setTimeout(async()=>{
      try{const next=await request("/api/review/analysis?id="+encodeURIComponent(job.id));acceptReviewJob(next,identity,serial);}
      catch(error){if(serial===reviewJobSerial&&identity===reviewIdentity()){reviewJob=null;reviewEngineError=error.message;renderReviewEngine();}}
    },300);
  }
}

async function cancelReviewAnalysis(){
  if(!reviewJob||reviewJob.state!=="running")return;
  try{
    const identity=reviewIdentity(),serial=reviewJobSerial;
    const job=await request("/api/review/analysis/cancel",{expected_id:reviewData.match_id,
      expected_revision:reviewData.revision,job_id:reviewJob.id});
    acceptReviewJob(job,identity,serial);
  }catch(error){reviewEngineError=error.message;renderReviewEngine();}
}

function renderReviewEngine(){
  const target=$("review-engine"),frame=reviewPosition();
  if(!target||!frame)return;
  const e=escapeHtml,running=reviewRunning(),batchRunning=typeof reviewCoachRunning==="function"&&reviewCoachRunning();
  const record=frame.advice.find(r=>r.record_id===frame.selectedAnalysis)||frame.advice.at(-1);
  const result=record?.advice,exact=result?.exact_layouts>0,played=frame.played.card;
  let notice=reviewEngineError||reviewJob?.error||"";
  if(reviewJob?.state==="stale")notice=t("The match changed. Reload the analysis board.");
  else if(running)notice=t(reviewJob?.state==="cancelling"?"Stopping analysis…":"Comparing moves across shared possible deals…");
  const pct=n=>Number.isFinite(n)?(100*n).toFixed(1)+"%":"—";
  const num=n=>Number.isFinite(n)?(n>0?"+":"")+n.toFixed(1):"—";
  let html=`<div class="analysis-heading"><div><span class="section-kicker">${t("PLAYER INFORMATION ONLY")}</span><h2>${t("Move evaluation")}</h2></div></div>`;
  if(frame.position.can_analyse)html+=`<button id="review-try-move" class="button secondary">${t("Try an alternate move")}</button>`;
  html+=`<div class="analysis-actions"><button id="review-analyse" class="button primary" ${!frame.position.can_analyse||running||batchRunning?"disabled":""}>${t("Analyse position")}</button><button id="review-longer" class="button secondary" ${exact?"hidden":""} ${!frame.position.can_analyse||running||batchRunning?"disabled":""}>${t("Think longer")}</button><button id="review-stop" class="text-button" ${!running?"hidden":""} ${reviewStarting||reviewJob?.state!=="running"?"disabled":""}>${t("Stop analysis")}</button></div>`;
  if(!frame.position.can_analyse)html+=`<p class="analysis-notice">${t("Other players' hands are unknown. Move to one of your decisions to compare legal cards.")}</p>`;
  if(notice)html+=`<p class="analysis-notice" role="status">${e(notice)}</p>`;
  html+=openingLeadMarkup(result);
  html+=coachDecisionMarkup(frame,record);
  let savedSettings="";
  if(frame.advice.length)savedSettings+=`<label class="analysis-run-label">${t("Saved evaluation")}<select id="review-analysis-record">${frame.advice.map(r=>`<option value="${e(r.record_id)}" ${r===record?"selected":""}>${e(t(r.source==="dashboard_review"?"Board analysis":"Advice during game"))} · ${e(r.created_at?new Date(r.created_at).toLocaleString(language==="hr"?"hr-HR":"en-GB"):r.record_id)} · ${r.advice.exact_layouts?`${r.advice.exact_layouts} ${t("consistent layouts")}`:r.advice.completed_samples??0}</option>`).join("")}</select></label>`;
  if(result){
    const status={exact_endgame:"All consistent layouts were evaluated under the fixed player model.",complete:"Requested trials completed.",time_limit:"Time limit reached; showing completed trials.",cancelled:"Analysis cancelled; showing completed trials.",forced_move:"Only one legal card. No simulation is needed.",preparation_limit:"Preparation limit reached. No estimates are available.",sampling_limit:"Sampling limit reached."};
    savedSettings+=`<div class="analysis-run-meta"><span>${exact?`${result.exact_layouts} ${t("consistent layouts")}`:`${result.completed_samples??0} ${t("shared trials")}`}</span><span>${Number(result.elapsed_seconds||0).toFixed(2)} s</span></div><p class="input-hint">${t(status[result.status]||"Analysis stopped.")}</p>`;
    html+=`<div class="analysis-comparison-scroll"><table class="analysis-comparison"><thead><tr><th>${t("Move")}</th><th>${t("Expected score")}</th><th>${t("Contract")}</th></tr></thead><tbody>${(result.moves||[]).map(row=>`<tr class="${row.card===played?"analysis-played-row":""}"><td><button class="text-button ${red(row.card)?"red":""}" data-review-candidate="${e(row.card)}">${e(cardLabel(row.card))}</button><small>${t(row.card===played?"Played":row.rank===1?(exact?(result.moves.filter(m=>m.rank===1).length>1?"Tied for first":"Leads the exact model"):"Leading estimate"):"")}</small>${firstTrickDetail(row)}${result.config?.objective==="match_outcome"?`<small>${t("Win match now")}: ${pct(row.our_match_win_probability)}</small><small>${t("Lose match now")}: ${pct(row.opponent_match_win_probability)}</small>`:""}</td><td>${Array.isArray(row.expected_recorded)?row.expected_recorded[result.our_team].toFixed(0)+" – "+row.expected_recorded[1-result.our_team].toFixed(0):"—"}</td><td>${pct(row.success_probability)}<small>${row.samples>0&&row.success_interval?row.success_interval.map(pct).join(" – "):t("No estimate")}</small></td></tr>`).join("")}</tbody></table></div>`;
    const unresolved=result.moves?.some(row=>row.rank!==1&&row.not_separated_from_leader);
    html+=`<p class="analysis-notice">${t(result.status==="forced_move"?"Only one legal card. No simulation is needed.":exact?"Exact endgame":!result.completed_samples?"No completed trials; no probabilities are available.":unresolved?"The search has not clearly separated the top choices.":result.config?.objective==="match_outcome"?"Ranked by match-win chance minus match-loss chance.":result.config?.objective==="contract_success"?"Ranked by the chance of making or breaking the contract.":"Ranked by estimated team point difference.")}</p><p class="input-hint">${t(result.success_definition==="make_contract"?"Success means making our contract.":"Success means defeating their contract.")}</p>`;
  }else html+=`<div class="analysis-empty"><span>✧</span><h3>${t("A closer look at this decision")}</h3><p>${t("No original advice was saved for this position.")}</p></div>`;
  html+=`<details class="analysis-settings"><summary>${t("Analysis details")}</summary><p class="input-hint">${t("Quick analysis uses 128 trials. Think longer uses up to 512 with the same player model and trial sequence.")}</p>${savedSettings}${result?`<details class="analysis-details"><summary>${t("Full saved analysis")}</summary><pre>${e(JSON.stringify(result,null,2))}</pre></details>`:""}<p class="analysis-footnote">${t("Estimates describe simulated play, not proven optimal moves. Ranges cover sampling uncertainty, not errors in the player model.")}</p></details>`;
  target.innerHTML=html;
  $("review-try-move")?.addEventListener("click",()=>openReviewVariation(frame));
  $("review-analyse").onclick=()=>startReviewAnalysis(false);
  $("review-longer").onclick=()=>startReviewAnalysis(true);
  $("review-stop").onclick=cancelReviewAnalysis;
  $("review-analysis-record")?.addEventListener("change",event=>{frame.selectedAnalysis=event.target.value;renderReviewEngine();});
  target.querySelectorAll("[data-review-candidate]").forEach(button=>button.onclick=()=>{
    $("review-hand-hint").textContent=t("Inspecting candidate")+": "+cardLabel(button.dataset.reviewCandidate)+" · "+t("Recorded move")+": "+cardLabel(played);
    document.querySelectorAll("#review-hand [data-card]").forEach(card=>card.classList.toggle("selected",card.dataset.card===button.dataset.reviewCandidate));
  });
}


async function openReviewVariation(frame){
  const identity=reviewIdentity(), e=escapeHtml;
  const title=t("Try an alternate move");
  showLiveDetails(title, `<p>${t("Each line uses the same sampled deal. Opponent cards and future moves are simulated.")}</p>
    <div class="variation-controls"><label>${t("Starting card")}<select id="variation-card">${frame.legal_cards.map(card=>`<option value="${e(card)}">${e(cardLabel(card))}${card===frame.played.card?" · "+t("Played"):""}</option>`).join("")}</select></label>
    <button id="variation-resample" class="button secondary">${t("Sample another deal")}</button></div>
    <p id="variation-status" role="status"></p><div id="variation-board"></div>
    <div class="variation-controls"><button id="variation-prev" class="button secondary">← ${t("Previous move")}</button><button id="variation-next" class="button secondary">${t("Next move")} →</button></div>`);
  const dialog=$("live-details-dialog"), picker=$("variation-card"), next=$("variation-next"), prev=$("variation-prev"), resample=$("variation-resample");
  picker.value=frame.legal_cards.find(card=>card!==frame.played.card)||frame.played.card;
  let data=null,step=-1,seed=42;
  const draw=()=>{
    const branch=data?.branches.find(row=>row.card===picker.value);
    prev.disabled=!branch||step<0;
    next.disabled=!branch||step>=branch.steps.length-1;
    if(!branch){$("variation-board").replaceChildren();return;}
    const move=branch.steps[step],trick=move?.trick||frame.position.trick;
    const hand=move?.hand||frame.hand_before;
    const score=branch.recorded;
    $("variation-board").innerHTML=`<h3>${move?`${t("Trick")} ${move.trick_number} · ${t("Player")} ${move.player} · ${e(cardLabel(move.card))}`:t("Before the move")}</h3>
      <div class="variation-trick">${trick.plays.map(play=>`<div>${cardMarkup(play.card,{table:true,disabled:true})}<small>${t("Player")} ${play.player}</small></div>`).join("")}</div>
      ${trick.winner!==undefined?`<p>${t("Trick winner")}: ${t("Player")} ${trick.winner} · ${trick.points} ${t("card points")}</p>`:""}
      <h3>${t("Your hand")}</h3><div class="variation-hand">${hand.map(card=>cardMarkup(card,{disabled:true})).join("")}</div>
      <p>${t("Simulated deal score")}: <strong>${score[data.our_team]} – ${score[1-data.our_team]}</strong></p>`;
  };
  async function load(){
    data=null;step=-1;draw();resample.disabled=true;
    $("variation-status").textContent=t("Sampling a possible deal…");
    try{
      const result=await request("/api/review/variations",{expected_id:reviewData.match_id,
        expected_revision:reviewData.revision,key:frame.key,seed});
      if(!dialog.open||!picker.isConnected||reviewIdentity()!==identity)return;
      data=result;step=0;$("variation-status").textContent="";draw();
    }catch(error){if(dialog.open&&picker.isConnected)$("variation-status").textContent=error.message;}
    finally{if(picker.isConnected)resample.disabled=false;}
  }
  picker.onchange=()=>{step=0;draw();};
  prev.onclick=()=>{step--;draw();};
  next.onclick=()=>{step++;draw();};
  resample.onclick=()=>{seed++;load();};
  dialog.onkeydown=event=>{
    if(!picker.isConnected||event.target===picker)return;
    const button=event.key==="ArrowLeft"?prev:event.key==="ArrowRight"?next:null;
    if(button&&!button.disabled){event.preventDefault();button.click();}
  };
  await load();
}
