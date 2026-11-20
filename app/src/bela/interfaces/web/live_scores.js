"use strict";

function liveScoreData(match){
  const points=[0,0],counts=[0,0],tricks=[];
  for(const [index,trick] of (match.completed_tricks||[]).entries()){
    const team=trick.winner%2;counts[team]++;
    const bonus=index===7?10+(counts[team]===8?90:0):0;
    points[team]+=trick.points+bonus;
    tricks.push({number:index+1,winner:trick.winner,team,points:trick.points,bonus,total:[...points]});
  }
  const melds=[0,0];
  for(const player of match.bela_players||[])melds[player%2]+=20;
  const provisional=points.map((n,team)=>n+(counts[team]?((match.awarded_melds?.[team]||0)+melds[team]):0));
  return {tricks,provisional,earned:match.result?.type==="deal"?match.result.earned:provisional,
    recorded:match.result?.type==="deal"?match.result.recorded:null,total:match.score};
}

function renderLiveScores(){
  const target=$("live-scores"),m=state.match;
  if(!target)return;
  target.hidden=!m||botMode()&&state.bot?.calling;
  if(target.hidden)return;
  const data=liveScoreData(m),own=m.setup.player%2,other=1-own,last=data.tricks.at(-1),e=escapeHtml;
  const contract=$("table-contract");
  contract?.querySelectorAll(".contract-score").forEach(node=>node.remove());
  if(botMode()&&contract&&!contract.hidden){
    const deal=data.recorded||data.earned;
    contract.insertAdjacentHTML("beforeend",`<div class="contract-score"><span>${t("Declarations")}</span><strong>${m.awarded_melds[own]} – ${m.awarded_melds[other]}</strong></div><div class="contract-score"><span>${t(data.recorded?"Recorded this deal":"This deal · provisional")}</span><strong>${deal[own]} – ${deal[other]}</strong></div><div class="contract-score"><span>${t("Match total")} · ${t("Our team")} / ${t("Their team")}</span><strong>${data.total[own]} – ${data.total[other]}</strong></div>`);
  }
  const row=(label,values,css="")=>`<tr class="${css}"><th>${t(label)}</th><td>${values[own]}</td><td>${values[other]}</td></tr>`;
  let html=`<table class="live-score-table"><thead><tr><th>${t("Score")}</th><th>${t("Our team")}</th><th>${t("Their team")}</th></tr></thead><tbody>`;
  html+=row(data.recorded?"Earned this deal":"This deal · provisional",data.earned);
  if(last){const added=[0,0];added[last.team]=last.points+last.bonus;html+=row("Latest trick",added.map(n=>n?"+"+n:"0"));}
  if(data.recorded)html+=row("Recorded this deal",data.recorded,"live-score-settled");
  html+=row("Match total",data.total,"live-score-total")+`</tbody></table>`;
  if(!data.recorded)html+=`<p class="live-score-note">${t("Deal points include eligible declarations. Contract settlement is applied after all eight tricks.")}</p>`;
  if(data.recorded)html+=`<p class="live-score-note">${t(m.result.caller_passed?"The calling team made the contract.":"The calling team failed; all deal points go to the opponents.")}</p>`;
  html+=`<details class="live-score-history"><summary>${t("Trick and deal scores")}</summary><div class="live-score-scroll"><table><thead><tr><th>${t("Trick")}</th><th>${t("Winner")}</th><th>${t("Points won")}</th><th>${t("Our team")}</th><th>${t("Their team")}</th></tr></thead><tbody>${data.tricks.map(trick=>`<tr><td>${trick.number}</td><td>${t("Player")} ${trick.winner}</td><td>${trick.points+trick.bonus}${trick.bonus?`<small>${t("Bonus")}: ${trick.bonus}</small>`:""}</td><td>${trick.total[own]}</td><td>${trick.total[other]}</td></tr>`).join("")}</tbody></table></div><p class="input-hint">${t("Trick totals include card points and earned last-trick or sweep bonuses. Declarations are shown in the deal score above.")}</p>`;
  if(m.deal_scores?.length)html+=`<h4>${t("Completed deals")}</h4><div class="live-score-scroll"><table><thead><tr><th>${t("Deal")}</th><th>${t("Trump / caller")}</th><th>${t("Recorded points")}</th><th>${t("Match total")}</th></tr></thead><tbody>${m.deal_scores.map(deal=>`<tr><td>${deal.number}</td><td>${e(suitNames()[deal.trump])}<small>${t("Player")} ${deal.caller}</small></td><td>${deal.recorded?deal.recorded[own]+" – "+deal.recorded[other]:t("Belot")}</td><td>${deal.score[own]} – ${deal.score[other]}</td></tr>`).join("")}</tbody></table></div>`;
  target.innerHTML=html+"</details>";
  target.querySelector(".live-score-history>summary")?.addEventListener("click",event=>{
    if(!document.body.classList.contains("live-mode"))return;
    event.preventDefault();
    const copy=target.querySelector(".live-score-history").cloneNode(true);copy.querySelector("summary").remove();
    showLiveDetails(t("Trick and deal scores"),copy.innerHTML);
  });
}
