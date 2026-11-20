"use strict";

// Coaching describes the saved search, never the subsequently revealed deal.
// Thresholds are presentation rules in settled team point DIFFERENCE units.
const COACH_REVIEW_GAP=5, COACH_MAJOR_GAP=15;
const coachFinite=n=>typeof n==="number"&&Number.isFinite(n);
const coachDecisionPriority=(a,b)=>Number(b.assessment.metric==="match")-Number(a.assessment.metric==="match")||b.assessment.gap-a.assessment.gap;

function coachRecord(frame,deal=null){
  const needsMatch=deal&&typeof recommendedLiveObjective==="function"&&recommendedLiveObjective({setup:deal.setup,awarded_melds:frame.position?.awarded_melds})==="match_outcome";
  return [...(frame.advice||[])].reverse().find(record=>
    ["point_difference","match_outcome"].includes(record.advice?.config?.objective)&&(!needsMatch||record.advice.config.objective==="match_outcome")&&coachAssessment(frame,record).evaluated)||null;
}

function coachAssessment(frame,record){
  const base={evaluated:false,kind:"pending",gap:null,interval:null,clear:false};
  if(!frame.position?.can_analyse)return {...base,kind:"other"};
  if(frame.legal_cards?.length===1)return {...base,kind:"forced"};
  const result=record?.advice;
  if(!result)return base;
  if(!["point_difference","match_outcome"].includes(result.config?.objective))return {...base,kind:"different_objective"};
  const matchFocused=result.config.objective==="match_outcome",value=row=>matchFocused?row.objective_mean:row.expected_point_difference;
  const moves=result.moves||[],samples=result.completed_samples,exact=result.exact_layouts>0;
  // A partial or unmatched candidate set cannot fairly grade a played card.
  if((!exact&&(!Number.isInteger(samples)||samples<2))||moves.length!==frame.legal_cards?.length||
    new Set(moves.map(m=>m.card)).size!==moves.length||
    moves.some(m=>!frame.legal_cards.includes(m.card)||m.samples!==samples||!coachFinite(m.expected_point_difference)||!coachFinite(value(m))))return base;
  const leader=moves.find(m=>m.rank===1),played=moves.find(m=>m.card===frame.played.card);
  if(!leader||!played||(!exact&&moves.filter(m=>m.rank===1).length!==1)||moves.some(m=>value(m)>value(leader)+0.00001))return base;
  const gap=Math.max(0,value(leader)-value(played));
  const pair=(result.comparisons||[]).find(p=>
    (p.first===leader.card&&p.second===played.card)||(p.second===leader.card&&p.first===played.card));
  let interval=null;
  if(pair&&coachFinite(pair.mean_difference)&&Math.abs((pair.first===leader.card?pair.mean_difference:-pair.mean_difference)-gap)<0.001&&
    Array.isArray(pair.interval)&&pair.interval.length===2&&pair.interval.every(coachFinite)){
    const candidate=pair.first===leader.card?pair.interval:[-pair.interval[1],-pair.interval[0]];
    // Only a coherent, paired interval from this same run can establish separation.
    if(candidate[0]<=gap+0.001&&candidate[1]>=gap-0.001&&candidate[0]<=candidate[1])interval=candidate;
  }
  const clear=!!interval&&interval[0]>0;
  const scale=matchFocused?0.01:1;
  const kind=gap<0.05*scale?"leading":gap<COACH_REVIEW_GAP*scale?"close":clear?"opportunity":"uncertain";
  return {evaluated:true,kind,gap,interval,clear,metric:matchFocused?"match":"points",major:kind==="opportunity"&&gap>=COACH_MAJOR_GAP*scale,
    leader,played,samples,result,record,exact,
    exactTie:exact&&played.rank===1&&moves.some(m=>m.card!==played.card&&m.rank===1),
    provenTie:exact&&(played.proven_tie_with_leader||
      (played===leader&&moves.some(m=>m.proven_tie_with_leader)))};
}

function coachSummary(data){
  const decisions=[];
  (data?.deals||[]).forEach((deal,di)=>deal.frames.forEach((frame,fi)=>{
    if(frame.position?.can_analyse)decisions.push({deal:di,frame:fi,position:frame,
      assessment:coachAssessment(frame,coachRecord(frame,deal))});
  }));
  const evaluated=decisions.filter(d=>d.assessment.evaluated);
  return {decisions,evaluated,forced:decisions.filter(d=>d.assessment.kind==="forced"),
    pending:decisions.filter(d=>d.assessment.kind==="pending"),
    leading:evaluated.filter(d=>d.assessment.kind==="leading"),
    uncertain:evaluated.filter(d=>["close","uncertain"].includes(d.assessment.kind)),
    opportunities:evaluated.filter(d=>d.assessment.kind==="opportunity").sort(coachDecisionPriority)};
}

const coachLabel=a=>({pending:"Not evaluated",other:"Another player's move",forced:"Forced move",
  different_objective:"Different analysis objective",leading:"Leading choice",close:"Small estimated difference",
  uncertain:"Uncertain alternative",opportunity:a.major?"Major review opportunity":"Review opportunity"}[a.kind]);

function coachFacts(frame,deal,assessment){
  if(!assessment.evaluated)return [];
  const played=assessment.played.card,alternative=assessment.leader.card;
  if(played===alternative)return [{type:assessment.metric==="match"?"match_leading":"leading"}];
  const trump=deal.setup.trump,rank=c=>c.split("_")[1];
  const points=c=>(c[0]===trump?{"7":0,"8":0,Q:3,K:4,"10":10,A:11,"9":14,J:20}:
    {"7":0,"8":0,"9":0,J:2,Q:3,K:4,"10":10,A:11})[rank(c)];
  const order=c=>(c[0]===trump?["7","8","Q","K","10","A","9","J"]:
    ["7","8","9","J","Q","K","10","A"]).indexOf(rank(c));
  const facts=[];
  if(played[0]===trump&&alternative[0]!==trump)facts.push({type:"retain_trump",card:played});
  else if(played[0]===alternative[0]&&order(alternative)<order(played))facts.push({type:"retain_stronger",card:played});
  else if(played[0]!==trump&&alternative[0]===trump)facts.push({type:"commit_trump"});
  if(points(alternative)<points(played))facts.push({type:"fewer_points",points:points(played)-points(alternative)});
  const plays=frame.position.trick?.plays||[];
  if(!plays.length&&played[0]!==alternative[0])facts.push({type:"lead_other_suit",suit:alternative[0]});
  if(plays.length){
    const led=plays[0].card[0];
    const winner=plays.reduce((best,p)=>{
      const category=c=>c[0]===trump?2:c[0]===led?1:0;
      return category(p.card)>category(best.card)||category(p.card)===category(best.card)&&order(p.card)>order(best.card)?p:best;
    });
    if(winner.player%2===deal.setup.player%2)facts.push({type:"partner_ahead"});
  }
  return facts.length?facts:[{type:"different_card"}];
}

function coachFactText(fact){
  const card=fact.card?escapeHtml(cardLabel(fact.card)):"";
  return {leading:t("Your card has the highest estimated team point difference in this run."),
    match_leading:t("Your card leads the match-outcome comparison in this run."),
    retain_trump:t("The alternative keeps this trump in your hand:")+" "+card+".",
    retain_stronger:t("The alternative uses a lower card in the same suit and keeps:")+" "+card+".",
    commit_trump:t("The alternative commits a trump to the current trick."),
    fewer_points:t("The alternative puts fewer card points into this trick:")+" "+(fact.points||0)+".",
    partner_ahead:t("Your partner is currently winning the trick; later players may still overtake."),
    lead_other_suit:t("The alternative leads a different suit for the other players to follow:")+" "+escapeHtml(suitNames()[fact.suit])+".",
    different_card:t("Both cards were legal. Their estimated value depends on how the remaining deal develops.")}[fact.type];
}

function coachDecisionMarkup(frame,record){
  if(!frame.position.can_analyse)return "";
  const a=coachAssessment(frame,record),e=escapeHtml,number=n=>n.toFixed(1);
  let html=`<section class="coach-decision coach-${a.kind}"><span class="coach-badge">${t(coachLabel(a))}</span>`;
  if(a.kind==="forced")html+=`<p>${t("You had only one legal card. This decision is excluded from performance comparisons.")}</p>`;
  else if(a.kind==="different_objective")html+=`<p>${t("This run ranks contract success. Run a point-based analysis to compare the move with the game review.")}</p>`;
  else if(a.exactTie){
    html+=`<p>${t(a.provenTie?"Your move is tied for first. The tied cards have the same outcome in each consistent layout.":"Your move is tied for first in the exact endgame model.")}</p>`;
  }else if(a.evaluated){
    html+=`<div class="coach-versus"><div><small>${t("You played")}</small><strong>${e(cardLabel(a.played.card))}</strong></div><span>→</span><div><small>${t("Engine choice")}</small><strong>${e(cardLabel(a.leader.card))}</strong></div></div>`;
    html+=a.metric==="match"?`<p>${t("Win match now")}: ${(100*a.played.our_match_win_probability).toFixed(1)}% → ${(100*a.leader.our_match_win_probability).toFixed(1)}%</p><p>${t("Lose match now")}: ${(100*a.played.opponent_match_win_probability).toFixed(1)}% → ${(100*a.leader.opponent_match_win_probability).toFixed(1)}%</p>`:`<p class="coach-gap"><strong>${number(a.gap)}</strong> ${t("estimated point difference between moves")}</p>`;
    html+=`<p>${t(a.kind==="leading"?"Your move leads this search; this is not proof that it is optimal.":a.kind==="opportunity"?
      "The paired comparison supports reviewing this alternative.":a.clear?
      "The search separates these moves, but the estimated difference is small.":
      "The search does not confidently separate these moves. This is not graded as a mistake.")}</p>`;
    if(!a.exact&&a.interval&&a.metric!=="match")html+=`<p class="input-hint">${t("Paired 95% range for the gap")}: ${number(a.interval[0])} ${t("to")} ${number(a.interval[1])}.</p>`;
    const facts=coachFacts(frame,reviewData.deals[reviewDeal],a);
    if(facts.length)html+=`<details class="coach-context"><summary>${t("What changes with the alternative?")}</summary><ul>${facts.map(f=>`<li>${coachFactText(f)}</li>`).join("")}</ul><p class="input-hint">${t("These are visible card consequences, not a claim about why the simulation preferred the move.")}</p></details>`;
    html+=`<p class="input-hint">${t(a.metric==="match"?"Match odds refer to the end of this deal. A continuing match is kept alive; future deals are not simulated.":"Expected score shows our settled deal points versus theirs. Differences between moves are estimates, not guaranteed lost points, and must not be added across a game.")}</p>`;
  }else html+=`<p>${t("Analyse this decision to compare your card with the alternatives.")}</p>`;
  return html+"</section>";
}

function renderReviewCoach(){
  const target=$("review-coach");
  if(!target||!reviewData)return;
  const s=coachSummary(reviewData),e=escapeHtml,running=reviewCoachRunning();
  const candidates=[...s.opportunities,...s.uncertain.sort(coachDecisionPriority)].slice(0,5);
  const themes={};
  s.opportunities.forEach(d=>coachFacts(d.position,reviewData.deals[d.deal],d.assessment).forEach(f=>{
    if(["retain_trump","retain_stronger","partner_ahead"].includes(f.type))themes[f.type]=(themes[f.type]||0)+1;
  }));
  const themeLabels={retain_trump:"Keeping trumps for later",retain_stronger:"Keeping stronger cards",partner_ahead:"Decisions while partner leads"};
  const status=reviewCoachRun?.context.expected_id===reviewData.match_id?reviewCoachRun.message:
    running?"Stopping previous game review…":"";
  target.innerHTML=`<div class="coach-heading"><div><span class="section-kicker">${t("GAME COACH")}</span><h2>${t("Your game review")}</h2><p>${s.evaluated.length} / ${s.decisions.length-s.forced.length} ${t("choices evaluated")} · ${s.forced.length} ${t("forced moves excluded")}</p></div><div class="coach-run-actions"><button id="coach-start" class="button primary" ${running||reviewRunning()||!s.decisions.length?"disabled":""}>${t("Review game")}</button><button id="coach-stop" class="button secondary" ${running?"":"hidden"}>${t("Stop review")}</button></div></div>
    <div class="coach-stats"><div><strong>${s.leading.length}</strong><span>${t("Leading choices")}</span></div><div><strong>${s.opportunities.length}</strong><span>${t("Worth reviewing")}</span></div><div><strong>${s.uncertain.length}</strong><span>${t("Close or uncertain")}</span></div><div><strong>${s.pending.length}</strong><span>${t("Awaiting analysis")}</span></div></div>
    <p class="coach-status" role="status">${e(t(status))}${running?` ${reviewCoachRun.completed} / ${reviewCoachRun.total}`:""}</p>
    <details class="coach-moments" ${s.opportunities.length?"open":""}><summary>${t("Key decisions")}</summary>${candidates.length?`<div class="coach-moment-list">${candidates.map(d=>`<button class="coach-moment" data-coach-deal="${d.deal}" data-coach-frame="${d.frame}"><span>${t("Deal")} ${d.deal+1} · ${t("Trick")} ${d.position.trick_number}<small>${e(cardLabel(d.assessment.played.card))} → ${e(cardLabel(d.assessment.leader.card))}</small></span><span class="coach-badge coach-${d.assessment.kind}">${t(coachLabel(d.assessment))}<small>${d.assessment.metric==="match"?(100*d.assessment.leader.our_match_win_probability).toFixed(1)+"%":d.assessment.gap.toFixed(1)} ${t(d.assessment.metric==="match"?"Win match now":"estimated point difference")}</small></span></button>`).join("")}</div>`:`<p>${t(s.evaluated.length?"No clear review opportunities in the evaluated choices. Unanalysed moves may still contain important decisions.":"Review the game to find decisions worth a closer look.")}</p>`}</details>
    ${Object.keys(themes).length?`<details class="coach-themes"><summary>${t("Patterns to explore")}</summary><ul>${Object.entries(themes).map(([key,count])=>`<li>${t(themeLabels[key])}: ${count}</li>`).join("")}</ul><p class="input-hint">${t("Counts describe situations among clear review opportunities; they are not proven weaknesses.")}</p></details>`:""}
    <details class="coach-settings"><summary>${t("Review settings and scope")}</summary><div class="coach-options"><label>${t("Analysis depth")}<select id="coach-depth"><option value="standard" ${reviewCoachDepth==="standard"?"selected":""}>${t("Standard · up to 8 seconds per decision")}</option><option value="deep" ${reviewCoachDepth==="deep"?"selected":""}>${t("Deeper · up to 15 seconds per decision")}</option></select></label><label class="checkbox-line"><input type="checkbox" id="coach-repeat" ${reviewCoachRepeat?"checked":""}>${t("Reanalyse evaluated choices")}</label></div><p>${t("Reviews run one decision at a time and save each result. You can stop and resume; reloading the page stops new work after the current decision.")}</p><p>${t("The summary uses the latest usable evaluation. Ordinary choices compare point scores; near the finish, match outcomes take priority. Review opportunities require a positive paired confidence bound.")}</p><p>${t("Only information available before each move is used. Estimates depend on the simulated player strategies. Confidence ranges cover sampling uncertainty, not model errors.")}</p><p>${t("This review covers card play. Trump calling and cross-game performance tracking are not graded yet.")}</p></details>`;
  $("coach-start").onclick=startGameReview;$("coach-stop").onclick=stopGameReview;
  $("coach-depth").onchange=event=>{reviewCoachDepth=event.target.value;};
  $("coach-repeat").onchange=event=>{reviewCoachRepeat=event.target.checked;};
  target.querySelectorAll("[data-coach-frame]").forEach(button=>button.onclick=()=>{
    const di=Number(button.dataset.coachDeal),fi=Number(button.dataset.coachFrame);
    reviewNavigate(()=>{reviewDeal=di;reviewFrame=fi;setReviewTab("analysis");});
    if(reviewDeal===di&&reviewFrame===fi)document.querySelector(".analysis-layout")?.scrollIntoView({block:"start",behavior:"smooth"});
  });
}
