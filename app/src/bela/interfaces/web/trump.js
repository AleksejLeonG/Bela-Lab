"use strict";
let trumpCards=new Set(), trumpResult=null, trumpRunning=false, trumpSerial=0, trumpError="";

function trumpPayload(){
  const player=Number($("trump-player").value),dealer=Number($("trump-dealer").value),passes=[];
  for(let i=1;i<=3;i++){const s=(dealer+i)%4;if(s===player)break;passes.push(s);}
  const experimental=$("trump-use-monte-carlo")?.checked===true;
  return {player,dealer,passes,hand:sortedCards(trumpCards),method:experimental?"monte_carlo_call_v1":"position_control_v2",config:experimental?{
    samples:Number($("trump-samples").value),seconds:Number($("trump-seconds").value),
    seed:Number($("trump-seed").value),condition_on_passes:$("trump-condition").checked}:{}};
}
function trumpChanged(){
  if(typeof predealDraft!=="undefined"&&predealDraft){
    predealDraft.six=sortedCards(trumpCards);predealDraft.player=Number($("trump-player").value);
    predealDraft.dealer=Number($("trump-dealer").value);savePredeal();
  }
  trumpSerial++;trumpResult=null;trumpError="";renderTrump();
}
function renderTrump(){
  const payload=trumpPayload();
  if(typeof renderPredeal==="function")renderPredeal();
  if(typeof predealDraft!=="undefined"&&!predealDraft){$("trump-player").disabled=false;$("trump-dealer").disabled=false;}
  const experimental=payload.method==="monte_carlo_call_v1";
  if($("trump-setup-status"))$("trump-setup-status").textContent=t(experimental?"Experimental settings active":"Recommended setup");
  $("trump-start").textContent=t(experimental?"Compare calls and pass":"Get trump advice");
  $("trump-position").textContent=l`Calling position: ${payload.passes.length+1}. `+
    t("Earlier seats assumed to have passed: ")+(payload.passes.join(", ")||t("none"))+
    (payload.passes.length===3?" · "+t("Dealer must call."):"");
  $("trump-selected").textContent=`${trumpCards.size} / 6`;
  $("trump-start").disabled=trumpRunning||trumpCards.size!==6;
  $("trump-status").textContent=trumpError||(trumpRunning?t("Comparing calls and pass…"):"");
  picker($("trump-picker"),trumpCards,card=>{toggleCard(trumpCards,card,6);trumpChanged();});
  const target=$("trump-results");
  if(!trumpResult){target.innerHTML="";return;}
  const r=trumpResult,percent=v=>v===null?"—":`${(100*v).toFixed(1)}%`;
  const range=(v,p=false)=>v===null?"—":v.map(n=>p?percent(n):n.toFixed(1)).join(" – ");
  const label=row=>row.action==="pass"?t("Pass"):`${t("Call")} ${suitPrefix(row.suit)} ${suitNames()[row.suit]}`;
  if(r.method==="position_control_v2"){
    target.innerHTML=`<section class="panel advice-controls"><h2>${escapeHtml(label(r.recommendation))}</h2>`+
      `<p>${t("Position-aware assessment. Scores describe hand strength, not success probabilities.")}</p>`+
      `<div class="advice-scroll"><table class="advice-table"><thead><tr><th>#</th><th>${t("Suit")}</th><th>${t("Hand-strength score")}</th><th>${t("Visible trumps")}</th></tr></thead><tbody>`+
      r.rankings.map(row=>`<tr><td>${row.rank}</td><td>${escapeHtml(label(row))}</td><td>${row.score}</td><td>${row.trump_count}</td></tr>`).join("")+
      `</tbody></table></div></section>`;
    return;
  }
  const rows=r.rankings.map(row=>`<tr><td>${row.rank??"—"}</td><td>${escapeHtml(label(row))}</td>`+
    `<td data-label="${t("Difference")}">${row.expected_point_difference===null?"—":row.expected_point_difference.toFixed(1)}<small>${range(row.objective_interval)}</small></td>`+
    `<td data-label="${t("Team success / 95% range")}">${percent(row.success_probability)}<small>${range(row.success_interval,true)}</small></td>`+
    `<td>${row.not_separated_from_leader===null?"—":row.not_separated_from_leader?t("Uncertain"):t("Lower estimate")}</td></tr>`).join("");
  const status={complete:"Completed",time_limit:"Time limit reached.",cancelled:"Cancelled",sampling_limit:"Sampling limit reached."};
  target.innerHTML=`<section class="panel advice-controls"><h2>${escapeHtml(label(r.recommendation))}</h2>`+
    `<p>${r.completed_samples} ${t("paired trials")} · ${r.elapsed_seconds.toFixed(2)} s · ${escapeHtml(t(status[r.status]||r.status))}</p>`+
    (r.recommendation_source==="heuristic_fallback"?`<p role="status">${t("No complete estimate. Showing the existing heuristic fallback.")}</p>`:"")+
    `<div class="advice-scroll"><table class="advice-table"><thead><tr><th>#</th><th>${t("Action")}</th><th>${t("Expected net points / 95% range")}</th><th>${t("Team success / 95% range")}</th><th>${t("Comparison")}</th></tr></thead><tbody>${rows}</tbody></table></div>`+
    `<p class="input-hint">${t("Team success means making our side's contract or defeating theirs. Belot wins are included in success, with no invented point award. These are model estimates, not optimal-play guarantees.")}</p></section>`;
}
async function startTrump(){
  if(trumpRunning||trumpCards.size!==6)return;
  const payload=trumpPayload(), serial=++trumpSerial;
  trumpRunning=true;trumpResult=null;trumpError="";renderTrump();
  try{
    const response=await fetch("/api/trump",{method:"POST",headers:{"Content-Type":"application/json","Accept-Language":language},body:JSON.stringify(payload)});
    const result=await response.json();
    if(serial!==trumpSerial)return;
    if(!response.ok)throw new Error(result.error||t("Request failed."));
    trumpResult=result;
  }catch(error){if(serial===trumpSerial)trumpError=error.message;}
  finally{trumpRunning=false;renderTrump();}
}
function initTrump(){
  for(const id of ["trump-player","trump-dealer","trump-samples","trump-seconds","trump-seed","trump-condition","trump-use-monte-carlo"]){
    $(id).addEventListener("change",trumpChanged);
    $(id).addEventListener("input",trumpChanged);
  }
  $("trump-start").addEventListener("click",startTrump);
  renderTrump();
}
