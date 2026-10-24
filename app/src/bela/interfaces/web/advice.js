"use strict";

let adviceJob=null, adviceKey=null, adviceSerial=0, adviceTimer=null, adviceError="", adviceStarting=false;
const adviceSource=()=>state.match?`${state.match.id}:${state.match.revision}:${state.match.deal_number}`:null;
const adviceOwnTurn=()=>state.match?.phase==="playing" && state.match.next_player===state.match.setup.player;
const mixedAdviceNote="The model treats consistent deals equally and announces bela at the first opportunity. In the mixed model, the other three players have unknown strategies drawn independently from five profiles. Each lineup stays fixed across candidate moves and throughout its hypothetical match. Your later moves use the tactical strategy. Values average the current deal across these possibilities.";

function syncAdvice(){
  const key=adviceSource();
  if(key!==adviceKey){
    adviceKey=key; adviceJob=null; adviceError=""; adviceStarting=false; adviceSerial++;
    clearTimeout(adviceTimer);
  }
  renderAdvice();
}

async function adviceRequest(path,payload){
  const response=await fetch(path,payload===undefined?{headers:{"Accept-Language":language}}:{
    method:"POST",headers:{"Content-Type":"application/json","Accept-Language":language},
    body:JSON.stringify({...context(),...payload})
  });
  const data=await response.json();
  if(!response.ok){const error=new Error(data.error||t("Analysis request failed."));error.status=response.status;throw error;}
  return data;
}

async function startAdvice(){
  if(!adviceOwnTurn()||adviceStarting||["running","cancelling"].includes(adviceJob?.state))return;
  const key=adviceSource(),serial=++adviceSerial;
  adviceKey=key; adviceStarting=true; adviceJob=null; adviceError=""; renderAdvice();
  const config={samples:Number($("advice-samples").value),seconds:8,seed:Number($("advice-seed").value),
    policy:$("advice-policy").value,objective:$("advice-objective").value};
  try{
    const job=await adviceRequest("/api/analysis/start",{config});
    if(serial!==adviceSerial||key!==adviceSource())return;
    adviceStarting=false;
    acceptAdviceJob(job,key,serial);
  }catch(error){
    if(serial!==adviceSerial||key!==adviceSource())return;
    adviceStarting=false; adviceError=error.message; renderAdvice();
    if(error.status===409){
      try{const fresh=await request("/api/state");if(serial===adviceSerial&&key===adviceSource()){state=fresh;selectedPlay=null;render();}}
      catch{}
    }
  }
}

function acceptAdviceJob(job,key,serial){
  if(serial!==adviceSerial||key!==adviceSource())return;
  if(job.state==="stale"||`${job.match_id}:${job.revision}:${job.deal_number}`!==key){
    adviceJob=null; adviceError=t("The game changed. Refresh the game before analysing again."); renderAdvice();
    request("/api/state").then(fresh=>{
      if(serial===adviceSerial&&key===adviceSource()){state=fresh;selectedPlay=null;render();}
    }).catch(()=>{});
    return;
  }
  adviceJob=job; adviceError=""; renderAdvice();
  if(["running","cancelling"].includes(job.state)){
    clearTimeout(adviceTimer);
    adviceTimer=setTimeout(()=>pollAdvice(job.id,key,serial),250);
  }
}

async function pollAdvice(id,key,serial){
  try{
    const job=await adviceRequest("/api/analysis?id="+encodeURIComponent(id));
    if(adviceJob?.id!==id)return;
    acceptAdviceJob(job,key,serial);
  }catch(error){
    if(serial!==adviceSerial||key!==adviceSource())return;
    adviceError=error.message; renderAdvice();
    if(error.status===404){adviceJob={...adviceJob,state:"failed",error:error.message};renderAdvice();}
    else adviceTimer=setTimeout(()=>pollAdvice(id,key,serial),1000);
  }
}

async function cancelAdvice(){
  if(!adviceJob||adviceJob.state!=="running")return;
  const id=adviceJob.id,key=adviceSource(),serial=++adviceSerial;
  clearTimeout(adviceTimer); adviceJob={...adviceJob,state:"cancelling"}; renderAdvice();
  try{acceptAdviceJob(await adviceRequest("/api/analysis/cancel",{job_id:id}),key,serial);}
  catch(error){if(serial===adviceSerial&&key===adviceSource()){adviceError=error.message;renderAdvice();}}
}

function renderAdvice(){
  const target=$("advice-content");
  if(!target)return;
  $("advice-model-note").textContent=t($("advice-policy").value==="mixed_match_v1"?mixedAdviceNote:
    "Single-strategy comparison: all simulated players use the selected strategy. Values estimate this deal under that policy. No real player's strategy is known.");
  const running=adviceStarting||["running","cancelling"].includes(adviceJob?.state);
  $("advice-start").disabled=!adviceOwnTurn()||running;
  $("advice-cancel").hidden=!running;
  $("advice-cancel").disabled=adviceStarting||adviceJob?.state!=="running";
  for(const id of ["advice-policy","advice-objective","advice-samples","advice-seed"])$(id).disabled=running;
  let notice="";
  if(!state.match)notice=t("Open a match to compare your legal moves.");
  else if(state.match.phase==="declarations")notice=t("Finish declarations before analysing moves.");
  else if(state.match.phase!=="playing")notice=t("This deal has finished. Start a new deal to analyse moves.");
  else if(!adviceOwnTurn())notice=t("Record the other players' cards until it is your turn.");
  else if(adviceError||adviceJob?.error)notice=t(adviceError||adviceJob.error);
  else if(running)notice=t(adviceJob?.state==="cancelling"?"Stopping analysis…":"Comparing moves across shared possible deals…");
  const result=adviceJob?.state==="finished"?adviceJob.result:null;
  if(!result){target.innerHTML=`<div class="panel advice-empty" role="status">${escapeHtml(notice||t("Choose a policy and start a comparison. No move will be played automatically."))}</div>`;return;}
  const pct=value=>`${(100*value).toFixed(1)}%`;
  const number=value=>value.toFixed(1);
  const status={complete:"Requested trials completed.",time_limit:"Time limit reached; showing completed trials.",
    cancelled:"Analysis cancelled; showing completed trials.",sampling_limit:"Sampling limit reached.",
    preparation_limit:"Preparation limit reached. No estimates are available.",forced_move:"Only one legal card. No simulation is needed."};
  const success=result.success_definition==="make_contract"?t("Make our contract"):t("Defeat their contract");
  const rows=result.moves.map(row=>{
    const estimated=row.samples>0;
    const label=result.status==="forced_move"?t("Forced move"):!estimated?t("No estimate"):
      row.rank===1?t("Leading estimate"):row.not_separated_from_leader?t("Unresolved vs leader"):t("Below leader in this model");
    return `<tr><td><span class="advice-rank">${row.rank??"—"}</span></td><td><button class="button secondary advice-card ${red(row.card)?"red":""}" data-advice-card="${escapeHtml(row.card)}">${escapeHtml(cardLabel(row.card))}</button>${row.bela?`<small>${t("Announce bela")}</small>`:""}</td><td data-label="${t("Our points")} ">${estimated?number(row.expected_recorded[result.our_team]):"—"}</td><td data-label="${t("Their points")} ">${estimated?number(row.expected_recorded[1-result.our_team]):"—"}</td><td data-label="${t("Difference")} ">${estimated?number(row.expected_point_difference):"—"}</td><td data-label="${t("Success / 95% range")}">${estimated?`<strong>${pct(row.success_probability)}</strong><small>${pct(row.success_interval[0])} – ${pct(row.success_interval[1])}</small>`:"—"}</td><td><span class="advice-label">${label}</span>${estimated&&result.config.objective==="point_difference"?`<small>${t("Point range")}: ${number(row.objective_interval[0])} – ${number(row.objective_interval[1])}</small>`:""}</td></tr>`;
  }).join("");
  target.innerHTML=`${notice?`<p role="status">${escapeHtml(notice)}</p>`:""}<div class="advice-summary"><div><strong>${result.completed_samples}</strong><span>${t("shared trials")}</span></div><div><strong>${(result.elapsed_seconds).toFixed(2)} s</strong><span>${t("analysis time")}</span></div><div><strong>${result.moves.length}</strong><span>${t("legal moves compared")}</span></div></div><section class="panel advice-results"><div class="panel-heading"><div><span class="section-kicker">${t("MODEL ESTIMATES")}</span><h2>${success}</h2><p>${t(status[result.status]||"Analysis stopped.")}</p></div></div><div class="advice-scroll"><table class="advice-table"><thead><tr><th>#</th><th>${t("Card")}</th><th>${t("Our points")}</th><th>${t("Their points")}</th><th>${t("Difference")}</th><th>${t("Success / 95% range")}</th><th>${t("Comparison")}</th></tr></thead><tbody>${rows}</tbody></table></div><p class="input-hint">${t("Points are settled scores after contract failure and bonuses. Click a card to select it at the table; record it only after it is played.")}</p></section>`;
  target.querySelectorAll("[data-advice-card]").forEach(button=>button.addEventListener("click",()=>{
    const row=result.moves.find(r=>r.card===button.dataset.adviceCard);
    if(adviceSource()!==adviceKey||!adviceOwnTurn()||!state.match.legal_cards.includes(row.card))return;
    selectedPlay=row.card;switchView("table");switchTab("play");renderHand();renderPlay();
    $("play-bela").checked=row.bela;
  }));
}

function initAdvice(){
  $("advice-start").addEventListener("click",startAdvice);
  $("advice-cancel").addEventListener("click",cancelAdvice);
  for(const id of ["advice-policy","advice-objective","advice-samples","advice-seed"]){
    $(id).addEventListener("change",()=>{
      if(adviceStarting||["running","cancelling"].includes(adviceJob?.state))return;
      adviceJob=null;adviceError="";adviceSerial++;clearTimeout(adviceTimer);renderAdvice();
    });
  }
}
