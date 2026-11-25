"use strict";

let botAdviceAttempt=null;
let liveComparison=null;

function runLiveComparison(objective, deeper=false){
  if(!botAdviceTurn())return;
  const prior=adviceKey===adviceSource()&&adviceJob?.state==="finished"?adviceJob.result:null;
  liveComparison={key:adviceSource(),prior,deeper,objective};
  startAdvice({samples:deeper?512:128,seconds:deeper?15:8,seed:42,
    policy:"mixed_match_v1",objective,self_policy:"direct_competent_mix_v1",exact_endgame:true});
}
function recommendedLiveObjective(match){
  const scores=match?.setup?.match_score||[0,0],bound=272+(match?.awarded_melds||[0,0]).reduce((a,b)=>a+b,0);
  return Math.max(...scores)+bound>1000?"match_outcome":"point_difference";
}
function publicContractSecured(match){
  const caller=match.setup.caller%2,other=1-caller;
  if(!match.trick_counts?.[caller])return false;
  const minimum=(match.trick_points?.[caller]||0)+(match.awarded_melds?.[caller]||0)+
    ((match.bela_players||[]).some(p=>p%2===caller)?20:0);
  // Once callers have a trick, the defenders cannot earn a sweep. Give them
  // every remaining card point, last trick, their melds and even a possible Bela.
  const maximumOther=152-(match.trick_points?.[caller]||0)+10+(match.awarded_melds?.[other]||0)+20;
  return minimum>maximumOther;
}
const botAdviceTurn=()=>botMode()&&state.bot&&!state.bot.calling&&!state.bot.declarations_pending&&!state.bot.awaiting_trick&&adviceOwnTurn();

function syncBotAdvice(){
  renderBotAdvice();
  if(!botAdviceTurn()||currentView!=="table")return;
  const key=adviceSource();
  if(botAdviceAttempt===key||adviceStarting||adviceJob&&adviceKey===key)return;
  botAdviceAttempt=key;
  runLiveComparison(recommendedLiveObjective(state.match));
}

function renderBotAdvice(){
  const panel=$("bot-live-advice");
  if(!panel)return;
  const active=botAdviceTurn(),same=adviceKey===adviceSource();
  const running=same&&(adviceStarting||["running","cancelling"].includes(adviceJob?.state));
  const comparison=liveComparison?.key===adviceSource()?liveComparison:null;
  const fresh=active&&same&&adviceJob?.state==="finished"?adviceJob.result:null;
  const prior=comparison?.prior;
  const keepPrior=comparison?.deeper&&prior?.config?.objective===comparison.objective&&
    (prior.exact_layouts||(!fresh?.exact_layouts&&prior.completed_samples>(fresh?.completed_samples??0)));
  const result=active&&(keepPrior?prior:fresh)||null;
  const e=escapeHtml,pct=n=>Number.isFinite(n)?(100*n).toFixed(1)+"%":"—";
  const shortPct=n=>Number.isFinite(n)?Math.round(100*n)+"%":"—";
  const leader=result?.moves?.find(r=>r.rank===1);
  const exact=result?.exact_layouts>0,tied=exact?result.moves.filter(r=>r.rank===1):[];
  const evidence=exact?`${result.exact_layouts} ${t("consistent layouts")}`:`${result?.completed_samples} ${t("shared trials")}`;
  const objective=result?.config?.objective||comparison?.objective||recommendedLiveObjective(state.match);
  const matchFocused=objective==="match_outcome";
  const contractFocused=objective==="contract_success";
  const delta=value=>Number.isFinite(value)?`${value>0?"+":""}${value.toFixed(1)}`:"—";
  const metricName=matchFocused?"Win − loss":contractFocused?"Contract":"Net pts";
  const metric=row=>matchFocused?pct(row.objective_mean):contractFocused?pct(row.success_probability):delta(row.expected_point_difference);
  const unresolved=result?.moves?.some(r=>r.rank!==1&&r.not_separated_from_leader);
  document.querySelectorAll("[data-bot-hand-card]").forEach(wrapper=>{
    const card=wrapper.dataset.botHandCard,row=result?.moves?.find(r=>r.card===card),target=wrapper.querySelector(".bot-card-estimate");
    if(!target)return;
    target.innerHTML=active&&row&&(exact||row.samples>0)?`<span>${t(metricName)}: <strong>${metric(row)}</strong></span>${contractFocused?`<span>${t("Net pts")}: <strong>${delta(row.expected_point_difference)}</strong></span>`:`<span>${t("Contract")}: <strong>${pct(row.success_probability)}</strong></span>`}${matchFocused?`<span>${t("Match")}: <strong>${pct(row.our_match_win_probability)}</strong></span>`:""}<span>${t("Štilja")}: ${shortPct(row.our_sweep_probability)} / ${shortPct(row.opponent_sweep_probability)}</span>`:
      active&&result?.status==="forced_move"&&row?t("Only legal card"):active&&running&&state.match.legal_cards.includes(card)?t("Calculating…"):"";
  });
  document.querySelectorAll("#my-hand .playing-card").forEach(card=>{
    card.classList.toggle("bot-recommended",active&&!unresolved&&(exact?tied.some(row=>row.card===card.dataset.card):card.dataset.card===leader?.card));
  });
  if(!active){panel.innerHTML="";panel.hidden=true;return;}
  panel.hidden=false;
  let html=`<div class="bot-advice-heading"><h3>${t("Move suggestions")}</h3><span>${t(exact?"Exact endgame":"Monte Carlo")}</span></div>`;
  if(running)html+=`<p role="status">${t("Comparing your legal cards… You can still play while analysis runs.")}</p><button id="bot-advice-stop" class="text-button" ${adviceStarting||adviceJob?.state!=="running"?"disabled":""}>${t("Stop analysis")}</button>`;
  else if(same&&(adviceError||adviceJob?.error))html+=`<p role="status">${e(adviceError||adviceJob.error)}</p>`;
  if(result){
    if(result.status==="forced_move")html+=`<p><strong>${leader?e(cardLabel(leader.card)):""}</strong> · ${t("Only one legal card. No simulation is needed.")}</p>`;
    else if((exact||result.completed_samples>0)&&leader){
      const success=result.success_definition==="make_contract"?"Make our contract":"Defeat their contract";
      const previousLeader=prior?.moves?.find(row=>row.rank===1);
      const label=exact?(tied.length>1?"Tied for first":"Leads the exact model"):unresolved?"Close estimates · no clear recommendation":"Leading estimate";
      const names=(tied.length>1?tied:[leader]).map(row=>cardLabel(row.card)).join(" / ");
      const opening=openingLeadMarkup(result);
      html+=opening||`<div class="bot-advice-leader"><small>${t(label)}</small><strong>${e(names)}</strong><span>${t(metricName)}: ${metric(leader)} · ${evidence}</span><span>${pct(leader.success_probability)} · ${t(success)}</span></div>`;
      if(fresh&&keepPrior&&!exact)html+=`<p>${t("Deeper run completed fewer trials. Showing the earlier result.")}</p>`;
      else if(!exact&&comparison?.deeper&&previousLeader&&previousLeader.card!==leader.card)html+=`<p>${t("Earlier leader")}: ${e(cardLabel(previousLeader.card))} · ${prior.completed_samples} ${t("shared trials")}</p>`;
      html+=`<p>${t(matchFocused?"Ranked by match-win chance minus match-loss chance.":contractFocused?"Ranked by the chance of making or breaking the contract.":"Ranked by average points gained minus points conceded.")}</p>`;
      if(matchFocused)html+=`<section class="bot-match-outcomes"><h4>${t("Match finish · this deal")}</h4><div><span>${t("Win match now")}</span><strong>${pct(leader.our_match_win_probability)}</strong></div><div><span>${t("Lose match now")}</span><strong>${pct(leader.opponent_match_win_probability)}</strong></div><div><span>${t("Continue match")}</span><strong>${pct(leader.match_continue_probability)}</strong></div><p class="input-hint">${t("Passing can still lose the match. Rankings now favour winning the match or keeping it alive; future deals are not simulated.")}</p></section>`;
      if(Number.isFinite(leader.our_sweep_probability))html+=`<div class="bot-sweep-summary"><div><span>${t("Our štilja")}</span><strong>${pct(leader.our_sweep_probability)}</strong></div><div><span>${t("Their štilja")}</span><strong>${pct(leader.opponent_sweep_probability)}</strong></div></div>`;
      if(unresolved)html+=`<p class="input-hint">${t("No clear best move has been established. The ranking is an estimate, not an instruction to risk points.")}</p>`;
      if(publicContractSecured(state.match))html+=`<p class="bot-advice-warning">${t("The calling team has already secured its contract from the public points. Compare how many points you can still collect.")}</p>`;
      else if(!exact&&result.moves.every(row=>row.success_probability===0))html+=`<p class="bot-advice-warning">${t("No contract successes in the sampled trials.")} ${t("Opponents' declarations")}: ${state.match.awarded_melds[1-result.our_team]||0} ${t("points")}.</p>`;
      html+=`<div class="bot-advice-scroll"><table><thead><tr><th>${t("Card")}</th><th>${t("Trial share")}</th><th>${t(metricName)}</th><th>${t("Contract")}</th></tr></thead><tbody>${result.moves.map(row=>`<tr class="${row.rank===1?"bot-advice-best":""}"><td>${row.rank}. ${e(cardLabel(row.card))}<small>${t("Expected score")}: ${Array.isArray(row.expected_recorded)?row.expected_recorded[result.our_team].toFixed(0)+" – "+row.expected_recorded[1-result.our_team].toFixed(0):"—"}</small><small>${t("Štilja · ours / theirs")}: ${pct(row.our_sweep_probability)} / ${pct(row.opponent_sweep_probability)}</small>${firstTrickDetail(row)}${row.rank!==1&&row.not_separated_from_leader?`<small>${t("Unresolved vs leader")}</small>`:""}</td><td>${pct(row.sample_best_share)}</td><td>${metric(row)}</td><td><strong>${pct(row.success_probability)}</strong><small>${Array.isArray(row.success_interval)?row.success_interval.map(pct).join(" – "):"—"}</small></td></tr>`).join("")}</tbody></table></div>`;
      html+=`<p class="input-hint">${evidence} · ${Number(result.elapsed_seconds||0).toFixed(1)} s.</p><p class="input-hint">${t("Success refers to this deal's contract, not winning the trick or the match. Estimates use your hand and public information only.")}</p><p class="input-hint">${t(exact?"All consistent layouts were evaluated under the fixed player model.":"Ranges show sampling uncertainty. Close choices may be unresolved; these are model estimates, not guaranteed odds.")}</p>`;
      if(!exact)html+=`<p class="input-hint">${t("Trial share counts how often the card led in individual simulations. Ties share credit. The ranking uses the average result across simulations.")}</p>`;
      html+=`<details class="bot-sweep-details"><summary>${t("Štilja: all eight tricks (+90 points)")}</summary><p class="input-hint">${t("Štilja chances are shown as ours / theirs. Winning even one trick prevents the opponents' štilja. The 90-point bonus is already included in expected scores and the point-based ranking, whether we called or they did.")}</p><table><thead><tr><th>${t("Card")}</th><th>${t("Our štilja · 95% range")}</th><th>${t("Their štilja · 95% range")}</th></tr></thead><tbody>${result.moves.map(row=>`<tr><td>${e(cardLabel(row.card))}</td><td>${row.our_sweep_interval?.map(pct).join(" – ")||"—"}</td><td>${row.opponent_sweep_interval?.map(pct).join(" – ")||"—"}</td></tr>`).join("")}</tbody></table></details>`;
      if(matchFocused)html+=`<details class="bot-sweep-details" open><summary>${t("Match odds for every move")}</summary><table><thead><tr><th>${t("Card")}</th><th>${t("Win match now")}</th><th>${t("Lose match now")}</th><th>${t("Continue match")}</th></tr></thead><tbody>${result.moves.map(row=>`<tr><td>${e(cardLabel(row.card))}</td><td>${pct(row.our_match_win_probability)}<small>${row.our_match_win_interval?.map(pct).join(" – ")||"—"}</small></td><td>${pct(row.opponent_match_win_probability)}<small>${row.opponent_match_win_interval?.map(pct).join(" – ")||"—"}</small></td><td>${pct(row.match_continue_probability)}</td></tr>`).join("")}</tbody></table></details>`;
    }else html+=`<p>${t("No completed trials; no probabilities are available.")}</p>`;
  }
  if(!running){
    if(!exact)html+=`<button id="bot-advice-deeper" class="button secondary">${t("Think longer")}</button>`;
    if(!matchFocused)html+=` <button id="bot-advice-focus" class="text-button">${t(contractFocused?"Rank by points":"Rank by contract")}</button>`;
  }
  panel.innerHTML=html;
  if(exact||result?.completed_samples>0){
    const details=document.createElement("div");
    panel.querySelectorAll(":scope>.bot-advice-scroll,:scope>.bot-sweep-details,:scope>.input-hint,:scope>.bot-advice-warning,.bot-match-outcomes>.input-hint").forEach(node=>details.append(node));
    const button=document.createElement("button");button.type="button";button.className="button secondary full";
    button.textContent=t("Analysis details");button.onclick=()=>showLiveDetails(t("Analysis details"),details.innerHTML);
    panel.append(button);
  }
  $("bot-advice-stop")?.addEventListener("click",cancelAdvice);
  $("bot-advice-deeper")?.addEventListener("click",()=>runLiveComparison(objective,true));
  $("bot-advice-focus")?.addEventListener("click",()=>runLiveComparison(contractFocused?"point_difference":"contract_success"));
}
