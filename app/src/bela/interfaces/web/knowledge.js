"use strict";

let knowledgeData = null, knowledgeRequestKey = null, knowledgeSerial = 0;
let knowledgeLoading = false, knowledgeError = null;
const knowledgeKey = () => state.match ? `${state.match.id}:${state.match.revision}:${state.match.deal_number}` : null;
const responseKey = data => `${data.match_id}:${data.revision}:${data.deal_number}`;
const kt = (text, values={}) => t(text).replace(/\{(\w+)\}/g, (_,key)=>String(values[key] ?? ""));

function reasonText(reason) {
  const values={player:reason.player, suit:suitNames()[reason.suit],
    card:reason.threshold?cardLabel(reason.threshold):"",
    cards:(reason.cards ?? []).map(cardLabel).join(", ")};
  const text={
    void_suit:"Player {player} has no {suit} remaining.",
    no_higher:"Player {player} has no {suit} stronger than {card} remaining.",
    bela_pair:"Bela proves that player {player} started with {cards}.",
    announced_quad:"The announced value proves that player {player} started with {cards}.",
    starting_hand:"Your starting hand rules out this owner.",
    revealed:"Player {player} revealed this card.",
    belot:"Player {player} revealed belot.",
    played:"Player {player} played this card.",
    combined_evidence:"Your starting hand and the recorded events rule out this owner."
  }[reason.kind] ?? "Checked against your starting hand and the recorded events.";
  return kt(text,values);
}

function sourceLinks(reason) {
  const indices=(reason.events ?? []).filter(index=>Number.isInteger(index) && index>=0);
  const link=index=>`<button type="button" class="source-link" data-knowledge-event="${index}">${escapeHtml(kt("Event {number}",{number:index+1}))} ↗</button>`;
  const setup=`<button type="button" class="source-link" data-knowledge-setup>${escapeHtml(t("Starting hand"))} ↗</button>`;
  if(!indices.length) return setup;
  const extra=indices.length>3?`<details class="source-more"><summary>${escapeHtml(kt("{count} more events",{count:indices.length-3}))}</summary>${indices.slice(3).map(link).join("")}</details>`:"";
  return `<div class="knowledge-sources">${reason.includes_setup?setup:""}${indices.slice(0,3).map(link).join("")}${extra}</div>`;
}

function ownerExplanation(row) {
  const origin=row.origin && row.origin.kind!=="starting_hand" ? `<div class="knowledge-proof"><p>${escapeHtml(reasonText(row.origin))}</p>${sourceLinks(row.origin)}</div>` : "";
  const exclusions=row.excluded.map(item=>`<div class="knowledge-proof"><strong>${escapeHtml(kt("Player {player} cannot hold this card.",{player:item.player}))}</strong><p>${escapeHtml(reasonText(item.reason))}</p>${sourceLinks(item.reason)}</div>`).join("");
  return `<details class="owner-explanation"><summary>${escapeHtml(t("Why these owners?"))}</summary>${origin}${exclusions}<p class="knowledge-note">${escapeHtml(t("Possible means at least one legal deal supports this owner. It does not mean likely."))}</p></details>`;
}

function bindKnowledgeSources() {
  $("knowledge-content").querySelectorAll("[data-knowledge-event]").forEach(button=>button.addEventListener("click",()=>{
    const index=Number(button.dataset.knowledgeEvent);
    switchView("history");
    const row=$("history-content").querySelector(`[data-edit="${index}"]`)?.closest("tr");
    if(row) {
      row.tabIndex=-1; row.classList.add("source-highlight");
      row.scrollIntoView({block:"center"}); row.focus({preventScroll:true});
      setTimeout(()=>row.classList.remove("source-highlight"),2400);
    }
  }));
  $("knowledge-content").querySelectorAll("[data-knowledge-setup]").forEach(button=>button.addEventListener("click",()=>openSetup("setup")));
}

function renderKnowledge() {
  $("refresh-knowledge").disabled=!state.match || knowledgeLoading;
  $("view-knowledge").setAttribute("aria-busy",String(knowledgeLoading));
  if(!state.match) {
    $("knowledge-content").innerHTML=`<div class="panel empty-section">${escapeHtml(t("Open a match to explore known cards and deductions."))}</div>`;
    return;
  }
  const data=knowledgeData && responseKey(knowledgeData)===knowledgeKey()?knowledgeData:null;
  if(!data) {
    const message=knowledgeError || t("Checking what is known…");
    $("knowledge-content").innerHTML=`<div class="panel empty-section" role="status">${escapeHtml(message)}</div>`;
    return;
  }
  const certain=data.cards.filter(row=>row.owners.length===1).length;
  const metrics=[["Revealed cards",data.revealed_count],
    ["Proven owners",certain],["Uncertain cards",data.cards.length-certain],["Played cards",data.played_count]];
  const status=knowledgeError || (knowledgeLoading?t("Checking what is known…"):data.complete?t("All ownership checks finished."):t("Some owner checks are unfinished. Those players have not been ruled out."));
  const playerPanels=[0,1,2,3].map(player=>{
    const reasons=data.deductions.filter(reason=>reason.player===player);
    const role=player===data.player?t("You"):player%2===data.player%2?t("Partner"):t("Opponent");
    const body=reasons.length?reasons.map(reason=>`<li><p>${escapeHtml(reasonText(reason))}</p>${sourceLinks(reason)}</li>`).join(""):`<li class="knowledge-note">${escapeHtml(player===data.player?t("Your remaining cards are known from your hand."):t("No additional deduction yet."))}</li>`;
    return `<article class="knowledge-player"><div class="knowledge-player-heading"><span class="avatar small">${player}</span><div><h3>${escapeHtml(kt("Player {player}",{player}))}</h3><span>${escapeHtml(role)}</span></div></div><ul class="knowledge-list">${body}</ul></article>`;
  }).join("");
  const suit=$("knowledge-suit").value;
  const rows=data.cards.filter(row=>suit==="all" || row.card[0]===suit);
  const ownerRows=rows.map(row=>{
    const chips=row.owners.map(player=>{
      const checked=row.confirmed_possible.includes(player);
      const label=kt(checked?"Player {player} — possible":"Player {player} — not ruled out",{player});
      return `<span class="owner-chip ${row.owners.length===1?"certain-owner":""} ${checked?"":"unchecked-owner"}" aria-label="${escapeHtml(label)}">${player}${checked?"":" ?"}</span>`;
    }).join("");
    const label=row.revealed?t("Revealed"):row.owners.length===1?t("Deduced owner"):row.complete?t("Possible owners"):t("Checks unfinished");
    return `<article class="ownership-row"><div class="ownership-main"><span class="knowledge-card ${red(row.card)?"red":""}">${cardLabel(row.card)}</span><div class="owner-chips">${chips}</div><span class="knowledge-card-status">${escapeHtml(label)}</span></div>${ownerExplanation(row)}</article>`;
  }).join("");
  const facts=data.facts.length?data.facts.map(fact=>`<li><p>${escapeHtml(friendlyEvent(fact.event))}</p>${fact.revealed_cards?.length?`<p>${escapeHtml(t("Newly public cards"))}: ${fact.revealed_cards.map(item=>escapeHtml(kt("Player {player}",{player:item.player})+" · "+cardLabel(item.card))).join(", ")}</p>`:""}${sourceLinks({events:[fact.index]})}</li>`).join(""):`<li class="knowledge-note">${escapeHtml(t("No public declarations or reveals recorded yet."))}</li>`;
  $("knowledge-content").innerHTML=`
    <div class="knowledge-meta">${escapeHtml(kt("Deal {deal} · revision {revision}",{deal:data.deal_number,revision:data.revision}))}<span>${escapeHtml(t("Current deal only"))}</span></div>
    <div class="knowledge-metrics">${metrics.map(([label,value])=>`<div class="panel"><span>${escapeHtml(t(label))}</span><strong>${value}</strong></div>`).join("")}</div>
    <section class="panel knowledge-section"><div class="panel-heading"><div><span class="section-kicker">${escapeHtml(t("PROVEN FROM THE RULES"))}</span><h2>${escapeHtml(t("What each player can no longer hold"))}</h2><p>${escapeHtml(t("Every source opens the event behind the conclusion."))}</p></div></div><div class="knowledge-players">${playerPanels}</div></section>
    <div class="knowledge-columns"><section class="panel knowledge-section ownership-panel"><div class="panel-heading"><div><span class="section-kicker">${escapeHtml(t("CARD OWNERSHIP"))}</span><h2>${escapeHtml(t("Unplayed cards outside your hand"))}</h2><p>${escapeHtml(t("Possible does not mean likely. No probabilities are calculated here."))}</p></div></div><p class="knowledge-check-status" role="status">${escapeHtml(status)}</p><div class="ownership-rows">${ownerRows || `<div class="empty-section">${escapeHtml(t("No remaining cards in this suit."))}</div>`}</div></section>
    <section class="panel knowledge-section public-facts"><div class="panel-heading"><div><span class="section-kicker">${escapeHtml(t("PUBLIC FACTS"))}</span><h2>${escapeHtml(t("What was said and shown"))}</h2><p>${escapeHtml(t("Spoken details remain public even when that team loses the meld contest."))}</p></div></div><ul class="knowledge-list fact-list">${facts}</ul></section></div>`;
  bindKnowledgeSources();
}

async function loadKnowledge(force=false) {
  const key=knowledgeKey();
  if(!key || knowledgeRequestKey===key) {renderKnowledge();return;}
  if(!force && knowledgeData && responseKey(knowledgeData)===key) {renderKnowledge();return;}
  const serial=++knowledgeSerial;
  knowledgeRequestKey=key; knowledgeLoading=true; knowledgeError=null;
  renderKnowledge();
  try {
    const response=await fetch("/api/knowledge",{headers:{"Accept-Language":language}});
    const data=await response.json();
    if(serial!==knowledgeSerial || key!==knowledgeKey())return;
    if(!response.ok)throw new Error(data.error || t("Knowledge could not be loaded. Try refreshing."));
    if(responseKey(data)!==key) {
      state=await request("/api/state"); selectedPlay=null; render();
      return;
    }
    knowledgeData=data;
  }catch(error){
    if(serial===knowledgeSerial && key===knowledgeKey())knowledgeError=error.message;
  }finally{
    if(serial===knowledgeSerial){knowledgeLoading=false;knowledgeRequestKey=null;renderKnowledge();}
  }
}

function syncKnowledge() {
  if(knowledgeData && responseKey(knowledgeData)!==knowledgeKey())knowledgeData=null;
  if(currentView==="knowledge")loadKnowledge();
}

function initKnowledge() {
  $("refresh-knowledge").addEventListener("click",()=>loadKnowledge(true));
  $("knowledge-suit").addEventListener("change",renderKnowledge);
}
