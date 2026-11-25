"use strict";

const $ = id => document.getElementById(id);
const SUITS = ["H", "S", "D", "C"];
const RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"];
const SYMBOLS = {H:"♥", S:"♠", D:"♦", C:"♣"};
const suitNames = () => deckSuitNames();
const DECK = SUITS.flatMap(s => RANKS.map(r => `${s}_${r}`));
const phases = () => ({declarations:t("Meld declarations"), playing:t("Play in progress"), deal_finished:t("Deal finished"), match_finished:t("Match finished")});
let state = {match:null, saved:[]};
let appInspectorTab="advice",appEndedKey=null,appPhase=null,appLoaded=false,appLastView=null;
let currentView = "table", currentTab = "play", selectedPlay = null, busy = false;
let setupMode = "new", setupCards = new Set(), meldCards = new Set(), editCards = new Set(), editAction = null;
let toastTimer;
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const red = code => code[0] === "H" || code[0] === "D";
const cardLabel = code => `${suitNames()[code[0]]} ${code.split("_")[1]}`;
const sortedCards = set => DECK.filter(code => set.has(code));
const context = () => ({expected_id:state.match?.id ?? null, expected_revision:state.match?.revision ?? 0});

function showError(message) {
  $("error-text").textContent = message;
  $("error-banner").hidden = false;
}
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $("toast").hidden = true, 3800);
}
function setBusy(value) {
  busy = value;
  document.body.classList.toggle("busy", value);
  document.querySelectorAll("dialog button[type=submit]").forEach(b => b.disabled = value);
  $("save-status").textContent = value ? t("Validating and saving…") : t("All accepted changes saved");
}
async function request(path, payload) {
  const response = await fetch(path, payload === undefined ? {headers:{"Accept-Language":language}} : {
    method:"POST", headers:{"Content-Type":"application/json", "Accept-Language":language}, body:JSON.stringify({...context(), ...payload})
  });
  const result = await response.json();
  if (!response.ok) {
    if (response.status === 409) {
      state = await (await fetch("/api/state")).json();
      selectedPlay = null;
      render();
    }
    throw new Error(result.error || t("Request failed."));
  }
  return result;
}
async function mutate(path, payload = {}, message = t("Change saved.")) {
  if (busy) return false;
  setBusy(true);
  try {
    const previousKey = state.match ? `${state.match.id}:${state.match.deal_number}` : null;
    state = await request(path, payload);
    if (previousKey !== `${state.match?.id}:${state.match?.deal_number}`) meldCards = new Set();
    selectedPlay = null;
    $("play-bela").checked = false;
    $("error-banner").hidden = true;
    render();
    toast(message);
    return true;
  } finally { setBusy(false); }
}
async function sendCommand(command, message) { return mutate("/api/command", {command}, message); }
function action(fn) { return async event => { try { await fn(event); } catch (error) { showError(error.message); } }; }

function cardMarkup(code, {selected=false, legal=false, disabled=false, table=false} = {}) {
  return l`<button class="playing-card ${red(code)?"red":""} ${selected?"selected":""} ${legal?"legal":""} ${table?"on-table":""}" data-card="${code}" aria-label="${suitNames()[code[0]]} ${deckRank(code.split("_")[1])}" ${disabled?"disabled":""}><img class="hungarian-face" src="/cards/hungarian/${code}.svg" alt="" aria-hidden="true" draggable="false"><span class="card-rank">${code.split("_")[1]}</span><span class="card-center">${SYMBOLS[code[0]]}</span><span class="card-bottom">${SYMBOLS[code[0]]}</span></button>`;
}
function picker(target, selected, onPick, disabled = () => false) {
  target.innerHTML = SUITS.map(suit => l`<div class="suit-row"><span class="suit-label ${red(suit)?"red":""}" aria-label="${suitNames()[suit]}">${suitMarkup(suit)}</span>${RANKS.map(rank => {
    const code = l`${suit}_${rank}`;
    return l`<button type="button" class="mini-card ${red(code)?"red":""} ${selected.has(code)?"selected":""}" data-card="${code}" aria-label="${suitNames()[suit]} ${rank}" aria-pressed="${selected.has(code)}" ${disabled(code)?"disabled":""}>${rank}</button>`;
  }).join("")}</div>`).join("");
  target.querySelectorAll("[data-card]").forEach(button => button.addEventListener("click", () => {
    if (!busy) onPick(button.dataset.card);
  }));
}
function toggleCard(set, card, max=8) {
  if (set.has(card)) set.delete(card);
  else if (set.size < max) set.add(card);
  else toast(l`You can select up to ${max} cards.`);
}
function switchView(view) {
  if(currentView==="review"&&reviewSaving)return;
  if(currentView==="review"&&view!=="review"&&reviewDirty){
    if(!confirm(t("Discard unsaved review note?")))return;
    reviewDirty=false;
  }
  if(currentView==="review"&&view!=="review"){stopGameReview();abandonReviewAnalysis();}
  currentView = view;
  document.body.classList.toggle("analysis-mode",view==="review");
  document.body.classList.toggle("live-mode",view==="table");
  const toolsNav=$("tools-nav");
  if(toolsNav){
    const toolView=["advice","trump","knowledge","history","help"].includes(view);
    toolsNav.open=document.documentElement.dataset.shell!=="desktop"&&toolView&&!window.matchMedia("(max-width:760px)").matches;
    toolsNav.classList.toggle("has-active",toolView);
  }
  document.querySelectorAll(".view").forEach(node => node.hidden = node.id !== `view-${view}`);
  document.querySelectorAll(".nav-item").forEach(node => {
    node.classList.toggle("active", node.dataset.view === view);
    if (node.dataset.view === view) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  const titles = {table:[t("Live game"),t("Your table, one move at a time.")],history:[t("Event history"),t("Every move and correction, in one place.")],saved:[t("My matches"),t("Save your progress and return when you like.")],help:[t("Rules and help"),t("Agreed rules and a clear way to play.")]};
  titles.knowledge=[t("What we know"),t("Every conclusion has a reason.")];
  titles.advice=[t("Move advice"),t("Compare the choices. Keep the uncertainty visible.")];
  titles.trump=[t("Trump advice"),t("Compare calling and passing before the talon.")];
  titles.review=[t("Analysis board"),t("Replay a game. Inspect every decision.")];
  $("page-title").textContent = titles[view][0];
  $("page-subtitle").textContent = titles[view][1];
  if(view==="knowledge")loadKnowledge();
  if(view==="advice")renderAdvice();
  if(view==="trump")renderTrump();
  if(view==="review")loadReview();
  scheduleBotTurn();
  if(view==="table")syncBotAdvice();
  renderAppWorkspace();
}
function switchTab(tab) {
  currentTab = tab;
  for (const name of ["play","meld"]) {
    $(`tab-${name}`).classList.toggle("active", name === tab);
    $(`tab-${name}`).setAttribute("aria-selected", String(name === tab));
    $(`input-${name}`).hidden = name !== tab;
  }
}
function render() {
  const m = state.match;
  $("version-label").textContent = state.version ? t("Version")+" "+state.version : "";
  $("saved-count").textContent = state.saved.length;
  const ownTeam = m ? m.setup.player % 2 : 0;
  $("score-strip").innerHTML = [0,1].map(team => l`<div class="score-card ${team===ownTeam?"our-team":""}"><div class="score-label">${m && team===ownTeam?t("OUR TEAM"):t("TEAM ")+team} <span>· ${team} + ${team+2}</span></div><div class="score-value">${m?.score[team] ?? 0}<small>points</small></div><span class="suit-icon">${team===ownTeam?"♣":"♤"}</span></div>`).join("") + l`<div class="score-card compact"><div class="score-label">TRUMP</div><div class="score-value">${m?suitPrefix(m.setup.trump)+" "+suitNames()[m.setup.trump]:"—"}</div><div class="score-detail">${m?t("Called by player ")+m.setup.caller:t("Awaiting selection")}</div></div><div class="score-card compact"><div class="score-label">DEAL ${m?.deal_number ?? "—"}</div><div class="score-value">${m?Math.min(m.completed_tricks.length+1,8):"—"}<small>/ 8 tricks</small></div><div class="score-detail">${m?t("Dealer: player ")+m.setup.dealer:t("New match")}</div></div>`;
  $("match-name").textContent = m?.name ?? t("Your next move starts here");
  $("phase-badge").textContent = m ? (m.winner!==null?t("Match finished"):phases()[m.phase]) : t("Ready to play");
  $("phase-badge").classList.toggle("live", m?.phase === "playing");
  $("edit-setup").hidden = !m;
  $("next-deal").hidden = !m?.result || m.winner !== null;
  $("export").disabled = !m;
  $("insert-first").disabled = !m;
  renderBoard(); renderHand(); renderPlay(); renderMeldFields(); renderHistory(); renderLibrary();
  syncKnowledge();
  syncAdvice();
  const recent = m?.events.slice(-3).reverse() ?? [];
  $("recent-events").innerHTML = recent.length ? recent.map(e => l`<div class="recent-row"><span class="event-number">${e.index+1}</span><span>${escapeHtml(friendlyEvent(e.event))}</span></div>`).join("") : t('<div class="recent-empty">Your game is waiting for its first event.</div>');
  $("undo").disabled = !m?.events.length;
  $("small-metrics").innerHTML = l`<div class="small-metric"><span>OUR TEAM'S TRICKS</span><strong>${m?.trick_counts[ownTeam] ?? 0}<small> / ${m?.completed_tricks.length ?? 0} completed</small></strong></div><div class="small-metric"><span>CARD POINTS</span><strong>${m?.trick_points[ownTeam] ?? 0}<small> our team</small></strong></div><div class="small-metric"><span>ORDINARY MELDS</span><strong>${m?.awarded_melds[ownTeam] ?? 0}<small> requires at least one trick</small></strong></div>`;
  if (m?.phase === "declarations") switchTab("meld");
  else switchTab(currentTab);
  renderBotMode();
  renderLiveScores();
  renderAppWorkspace();
}
function trickCardsMarkup(plays, own){
  const seatPositions=["bottom","right","top","left"];
  return plays.map(({player,card})=>{
    const offset=(player-own+4)%4;
    const name=t(offset===0?"You":offset===2?"Partner":"Opponent");
    const label=offset%2?`${name} ${player}`:name;
    return `<div class="trick-card ${seatPositions[offset]}" data-trick-seat="${player}">
      ${cardMarkup(card,{table:true,disabled:true})}
      <span class="trick-card-owner">${escapeHtml(label)}</span>
    </div>`;
  }).join("");
}

function renderBoard() {
  const m = state.match;
  const handPanel=document.querySelector("#view-table .hand-panel");
  if(handPanel?.parentElement===$("table-board"))document.querySelector("#view-table .board-panel").after(handPanel);
  const contract=$("table-contract");
  contract.hidden=!m||botMode()&&state.bot?.calling;
  if(m&&!contract.hidden){
    const caller=m.setup.caller,own=m.setup.player;
    const role=caller===own?t("You"):caller%2===own%2?t("Partner"):t("Opponent");
    contract.innerHTML=`<div class="table-contract-trump"><span>${t("Trump")}</span><strong>${suitMarkup(m.setup.trump)} ${escapeHtml(suitNames()[m.setup.trump])}</strong></div><div><span>${t("Called by")}</span><strong>${role} · ${t("Player")} ${caller}</strong></div><div><span>${t("Calling position")}</span><strong>${(caller-m.setup.dealer+4)%4||4} / 4</strong></div><span class="table-contract-team">${t(caller%2===own%2?"Our team called":"Opponents called")}</span>`;
  }
  if (!m) {
    $("table-board").innerHTML = t('<div class="table-placeholder"><div class="empty-suit">♣</div><h3>A place for a good game.</h3><p>Start with your hand or explore the workbench with a demo match.</p><button class="button" id="board-demo">Open demo match →</button></div>');
    $("board-demo").addEventListener("click", action(openDemo));
    $("turn-message").textContent = t("Open a demo or start a new match.");
    return;
  }
  const positions = ["bottom","right","top","left"];
  const seats = [0,1,2,3].map(offset => {
    const p = (m.setup.player+offset)%4;
    const role = offset===0?t("You"):offset===2?t("Partner"):t("Opponent");
    const flags = [m.setup.dealer===p?t("dealer"):null,m.setup.caller===p?t("caller"):null].filter(Boolean);
    return l`<div class="seat ${positions[offset]} ${m.next_player===p?"on-turn":""}"><span class="avatar">${p}</span><div><div class="seat-name">${role} <span>· ${p}</span></div><div class="seat-meta">${m.remaining_counts[p]} cards${flags.length?" · "+flags.join(" · "):""}</div></div></div>`;
  }).join("");
  const visibleTrick=botMode()&&state.bot?.awaiting_trick?m.completed_tricks.at(-1):m.trick;
  const played = trickCardsMarkup(visibleTrick.plays,m.setup.player);
  $("table-board").innerHTML = l`<div class="board-wordmark">bela<small>CROATIAN BELA</small></div>${seats}${played}`;
  let message = m.phase==="declarations" ? t("Record public melds, then confirm their outcome.") : m.next_player===m.setup.player ? t("Your turn. Choose one of the legal cards.") : m.next_player!==null ? l`Player to act: ${m.next_player}. Record their card.` : t("The deal is finished. Scoring is confirmed.");
  if (m.winner!==null) message = l`Match finished. Winning team: ${m.winner}.`;
  $("turn-message").textContent = message;
}
function renderHand() {
  const m = state.match;
  $("hand-count").textContent = l`${m?.hand.length ?? 0} / 8`;
  $("my-hand").innerHTML = m?.hand.length ? m.hand.map(c => {const options={legal:m.legal_cards.includes(c),selected:selectedPlay===c,disabled:m.next_player!==m.setup.player || !m.legal_cards.includes(c) || botMode()&&(state.bot?.awaiting_trick||state.bot?.declarations_pending)};return botMode()?botHandCard(c,options):cardMarkup(c,options);}).join("") : l`<div class="empty-hand">${m?t("You have played all your cards."):t("Your eight cards will appear here.")}</div>`;
  $("my-hand").querySelectorAll("[data-card]").forEach(button => button.addEventListener("click", () => {
    if(botMode()){botAction("/api/bot/play",{card:button.dataset.card}).catch(()=>{});return;}
    selectedPlay = button.dataset.card; switchTab("play"); renderHand(); renderPlay();
  }));
  $("hand-note").textContent = m && m.next_player===m.setup.player ? t("Highlighted cards are legal. Their order is not a recommendation.") : t("Other players' unrevealed cards stay hidden.");
}
function renderPlay() {
  const m = state.match, actor = m?.next_player;
  $("actor-badge").textContent = actor ?? "—";
  $("actor-name").textContent = m && m.winner!==null?t("Match finished"):actor===null || actor===undefined ? t("Waiting for the next move") : actor===m.setup.player?t("Your turn"):t("Player ")+actor+t(" is to act");
  $("actor-detail").textContent = m && m.winner!==null?t("Start a new match to continue."):m?.phase === "declarations" ? t("Finish ordinary declarations first.") : actor!==null && actor!==undefined ? t("Enter the card that was actually played.") : t("Open a match or a new deal.");
  const used = new Set(m?.events.filter(e=>e.event.type==="play").map(e=>e.event.card) ?? []);
  const disabled = code => !m || m.phase!=="playing" || used.has(code)
    || m.revealed.some((known,owner)=>owner!==actor && known.includes(code))
    || (actor===m.setup.player ? !m.legal_cards.includes(code) : m.hand.includes(code));
  if (selectedPlay && disabled(selectedPlay)) selectedPlay = null;
  picker($("play-picker"), new Set(selectedPlay?[selectedPlay]:[]), code=>{selectedPlay=code;renderPlay();renderHand();}, disabled);
  $("selection-line").textContent = selectedPlay ? l`Selected: ${cardLabel(selectedPlay)}` : t("No card selected.");
  $("selection-line").classList.toggle("has-selection", !!selectedPlay);
  $("submit-play").disabled = !selectedPlay || !m || m.phase!=="playing";
  const belaPossible = selectedPlay && selectedPlay[0]===m?.setup.trump
    && ["K","Q"].includes(selectedPlay.split("_")[1]) && !m.bela_players.length
    && !used.has(`${m.setup.trump}_K`) && !used.has(`${m.setup.trump}_Q`);
  $("play-bela").disabled = !belaPossible;
  if (!belaPossible) $("play-bela").checked = false;
}
function valueOptions(values, selected) { return values.map(v=>l`<option value="${v}" ${String(v)===String(selected)?"selected":""}>${v}</option>`).join(""); }
function eventFields(type, prefix, chosen, update, event={}) {
  if (["reveal","belot","play"].includes(type)) return l`<div class="field-caption">${type==="play"?t("PLAYED CARD"):t("REVEALED CARDS")}</div><div id="${prefix}-cards" class="${prefix==="edit"?"large-picker":"compact-picker"}"></div><p class="input-hint" id="${prefix}-count">${chosen.size} selected${type==="belot"?t(" · leave empty to claim belot from your own hand"):""}</p>${type==="play"?l`<label class="checkbox-line"><input type="checkbox" id="${prefix}-bela" ${event.bela?"checked":""}> Bela was announced with this card</label>`:""}`;
  if (type==="meld_value") return l`<label>Announced value<select id="${prefix}-points">${valueOptions([20,50,100,150,200],event.points ?? 20)}</select></label>`;
  if (type==="sequence_high") return l`<label>Sequence high card<select id="${prefix}-rank">${valueOptions(RANKS,event.rank ?? "A")}</select></label>`;
  if (type==="presence") return l`<label>Declaration<select id="${prefix}-presence"><option value="true" ${event.has_meld!==false?"selected":""}>Has melds</option><option value="false" ${event.has_meld===false?"selected":""}>No melds</option></select></label>`;
  return l`<label>Meld outcome<select id="${prefix}-winner"><option value="none">No ordinary melds</option><option value="0" ${event.winning_team===0?"selected":""}>Team 0</option><option value="1" ${event.winning_team===1?"selected":""}>Team 1</option></select></label>`;
}
function renderMeldFields() {
  const type = $("meld-type").value, m=state.match;
  // Preserve currently entered values when the main state is refreshed.
  const old = {points:$("meld-points")?.value, rank:$("meld-rank")?.value, has_meld:$("meld-presence")?.value!=="false"};
  $("meld-fields").innerHTML = eventFields(type,"meld",meldCards,null,old);
  if (["reveal","belot"].includes(type)) picker($("meld-cards"),meldCards,code=>{toggleCard(meldCards,code);renderMeldFields();}, code=>!m || (Number($("meld-player").value)!==m.setup.player && m.setup.hand.includes(code)));
  $("submit-meld").disabled = !m || m.phase!=="declarations";
  $("finish-melds").disabled = !m || m.phase!=="declarations";
}
function collectEvent(type,prefix,chosen,player) {
  if (type==="finish_declarations") return {type,winning_team:$(`${prefix}-winner`).value==="none"?null:Number($(`${prefix}-winner`).value)};
  if (type==="play") {
    if (chosen.size!==1) throw new Error(t("Select exactly one card."));
    return {type,player,card:sortedCards(chosen)[0],bela:$(`${prefix}-bela`).checked};
  }
  if (["reveal","belot"].includes(type)) {
    if (type==="reveal" && !chosen.size) throw new Error(t("Select at least one revealed card."));
    return {type,player,cards:sortedCards(chosen)};
  }
  if (type==="meld_value") return {type,player,points:Number($(`${prefix}-points`).value)};
  if (type==="sequence_high") return {type,player,rank:$(`${prefix}-rank`).value};
  return {type,player,has_meld:$(`${prefix}-presence`).value==="true"};
}
function friendlyEvent(e) {
  if(e.type==="play") return l`Player ${e.player} · ${cardLabel(e.card)}${e.bela?" · bela":""}`;
  if(e.type==="reveal") return l`Player ${e.player} revealed ${e.cards.map(cardLabel).join(", ")}`;
  if(e.type==="meld_value") return l`Player ${e.player} announced ${e.points}`;
  if(e.type==="sequence_high") return l`Player ${e.player} · sequence up to ${e.rank}`;
  if(e.type==="presence") return l`Player ${e.player} ${e.has_meld?t("has"):t("has no")} melds`;
  if(e.type==="belot") return l`Player ${e.player} · belot`;
  return e.winning_team===null?t("No ordinary melds"):t("Melds belong to team ")+e.winning_team;
}
function renderHistory() {
  const m = state.match;
  $("history-content").innerHTML = m?.events.length ? l`<table class="history-table"><thead><tr><th>NO.</th><th>EVENT</th><th></th></tr></thead><tbody>${m.events.map(e=>l`<tr><td>${String(e.index+1).padStart(2,"0")}</td><td>${escapeHtml(friendlyEvent(e.event))}</td><td><div class="history-actions"><button data-edit="${e.index}">Edit</button><button data-insert="${e.index}" aria-label="Insert before event ${e.index+1}">＋ Before</button><button class="delete" data-delete="${e.index}">Delete</button></div></td></tr>`).join("")}</tbody></table>` : t('<div class="empty-section">Declarations, reveals and played cards will appear here.</div>');
  $("history-content").querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>openEventDialog("replace",Number(b.dataset.edit))));
  $("history-content").querySelectorAll("[data-insert]").forEach(b=>b.addEventListener("click",()=>openEventDialog("insert",Number(b.dataset.insert))));
  $("history-content").querySelectorAll("[data-delete]").forEach(b=>b.addEventListener("click",action(()=>sendCommand({type:"delete",index:Number(b.dataset.delete)},t("Event deleted and subsequent events revalidated.")))));
  $("deal-history").innerHTML = m ? m.deals.map(d=>l`<div class="deal-row"><strong>Deal ${d.number}</strong><span>${phases()[d.phase]}</span><span>${d.tricks} tricks</span><strong>${d.score[0]} : ${d.score[1]}</strong></div>`).join("") : t('<div class="recent-empty">No open match.</div>');
}
function renderLibrary() {
  const e=escapeHtml;
  $("library-content").innerHTML=state.saved.length?`<div class="library-table-wrap"><table class="library-table"><thead><tr><th>${t("Match")}</th><th>${t("Mode")}</th><th>${t("Deals")}</th><th>${t("Last played")}</th><th><span class="sr-only">${t("Actions")}</span></th></tr></thead><tbody>${state.saved.map(match=>`<tr><td><strong>${e(match.name)}</strong></td><td>${t(match.mode==="bots"?"Bot game":"Manual input")}</td><td>${match.deals}</td><td>${e(new Date(match.modified*1000).toLocaleString(language==="hr"?"hr-HR":"en-GB",{dateStyle:"medium",timeStyle:"short"}))}</td><td><button class="button secondary" data-load="${e(match.id)}">${t("Continue")}</button><button class="text-button" data-review-match="${e(match.id)}">${t("Review")}</button></td></tr>`).join("")}</tbody></table></div>`:`<div class="empty-section"><h3>${t("No saved matches")}</h3><p>${t("Finished and ongoing matches will appear here. You can also import a player archive.")}</p></div>`;
  $("library-content").querySelectorAll("[data-load]").forEach(button=>button.onclick=action(async()=>{await mutate("/api/load",{id:button.dataset.load},t("Match loaded."));switchView("table");}));
  $("library-content").querySelectorAll("[data-review-match]").forEach(button=>button.onclick=()=>{reviewMatchId=button.dataset.reviewMatch;switchView("review");});
}

async function openDemo() {
  await mutate("/api/demo",{},t("Opened a separate copy of the demo match."));
  switchView("table"); switchTab("play");
}
function renderSetupPicker() {
  const limit=setupStage==="six"?6:8;
  picker($("setup-picker"),setupCards,card=>{
    if(setupStage==="eight"&&setupMode!=="setup"&&predealDraft?.six.includes(card))return;
    toggleCard(setupCards,card,limit);renderSetupPicker();
  });
  $("setup-selected").textContent = `${setupCards.size} / ${limit} ${t("selected")}`;
}
function openSetup(mode) {
  setupMode = mode;
  setupStage=mode==="setup"?"eight":"six";
  const m = state.match, s=m?.setup;
  setupCards = new Set(mode==="setup"?s.hand:[]);
  $("setup-title").textContent = mode==="new"?t("New match"):mode==="next"?t("Next deal"):t("Edit initial setup");
  $("setup-name").value = mode==="new"?t("My match"):m.name;
  $("setup-name").disabled = mode!=="new";
  $("setup-player").value = s?.player ?? 0;
  $("setup-player").disabled = mode!=="new";
  $("setup-dealer").value = mode==="next"?(s.dealer+1)%4:s?.dealer ?? 3;
  $("setup-dealer").disabled = mode==="next";
  $("setup-caller").value = mode==="setup"?s.caller:"";
  $("setup-trump").value = mode==="setup"?s.trump:"";
  for(const team of [0,1]) {
    $(`setup-score${team}`).value = mode==="next"?m.score[team]:mode==="setup"?s.match_score[team]:0;
    $(`setup-score${team}`).disabled = mode==="next";
  }
  $("setup-submit").textContent = mode==="new"?t("Open match →"):mode==="next"?t("Start deal →"):t("Validate and save →");
  $("setup-error").hidden = true;
  renderSetupStage();renderSetupPicker(); $("setup-dialog").showModal();
}
function openEventDialog(type,index) {
  if (!state.match) return;
  editAction = {type,index};
  const event = type==="replace"?state.match.events[index].event:{type:"reveal",player:state.match.setup.player};
  $("event-title").textContent = type==="replace"?l`Correct event ${index+1}`:l`Insert before event ${index+1}`;
  $("edit-type").value = event.type;
  $("edit-player").value = event.player ?? state.match.setup.player;
  editCards = new Set(event.cards ?? (event.card?[event.card]:[]));
  $("event-error").hidden = true;
  renderEditFields(event); $("event-dialog").showModal();
}
function renderEditFields(event={}) {
  const type = $("edit-type").value;
  $("edit-player-label").hidden = type==="finish_declarations";
  $("edit-fields").innerHTML = eventFields(type,"edit",editCards,null,event);
  if (["play","reveal","belot"].includes(type)) picker($("edit-cards"),editCards,code=>{
    const bela=$("edit-bela")?.checked;
    if(type==="play") editCards=new Set([code]); else toggleCard(editCards,code);
    renderEditFields({bela});
  });
}

document.querySelectorAll("[data-view]").forEach(button=>button.addEventListener("click",()=>switchView(button.dataset.view)));
document.querySelectorAll("[data-tab]").forEach(button=>button.addEventListener("click",()=>switchTab(button.dataset.tab)));
document.querySelectorAll("[data-close]").forEach(button=>button.addEventListener("click",()=>$(button.dataset.close).close()));
$("dismiss-error").addEventListener("click",()=>$("error-banner").hidden=true);
$("demo").addEventListener("click",action(openDemo));
$("new-match").addEventListener("click",()=>botMode()?openBotSetup():openSetup("new"));
$("edit-setup").addEventListener("click",()=>openSetup("setup"));
$("next-deal").addEventListener("click",()=>openSetup("next"));
$("insert-first").addEventListener("click",()=>openEventDialog("insert",0));
$("undo").addEventListener("click",action(()=>sendCommand({type:"delete",index:state.match.events.length-1},t("Last event undone."))));
$("submit-play").addEventListener("click",action(()=>sendCommand({type:"add",event:{type:"play",player:state.match.next_player,card:selectedPlay,bela:$("play-bela").checked}},t("Move validated and saved."))));
$("meld-type").addEventListener("change",()=>{meldCards=new Set();renderMeldFields();});
$("meld-player").addEventListener("change",()=>{meldCards=new Set();renderMeldFields();});
$("submit-meld").addEventListener("click",action(async()=>{
  const event=collectEvent($("meld-type").value,"meld",meldCards,Number($("meld-player").value));
  if(await sendCommand({type:"add",event},t("Public information saved."))){meldCards=new Set();renderMeldFields();}
}));
$("finish-melds").addEventListener("click",action(async()=>{
  const winning_team=$("declaration-winner").value==="none"?null:Number($("declaration-winner").value);
  if(await sendCommand({type:"add",event:{type:"finish_declarations",winning_team}},t("Declarations confirmed. You can now record moves.")))switchTab("play");
}));
$("setup-form").addEventListener("submit",async event=>{
  event.preventDefault();
  try {
    if(setupStage==="six"){beginCallingSetup();return;}
    if(setupCards.size!==8)throw new Error(t("Select exactly eight cards for your starting hand."));
    if(!$("setup-caller").value||!$("setup-trump").value)throw new Error(t("Choose the actual caller and trump."));
    if(setupMode!=="setup"&&predealDraft&&JSON.stringify(predealDraft.source)!==JSON.stringify(context()))
      throw new Error(t("The current match changed. Start deal setup again."));
    const setup={player:Number($("setup-player").value),hand:sortedCards(setupCards),dealer:Number($("setup-dealer").value),caller:Number($("setup-caller").value),trump:$("setup-trump").value,match_score:[Number($("setup-score0").value),Number($("setup-score1").value)]};
    const ok=setupMode==="new"?await mutate("/api/new",{name:$("setup-name").value,setup},t("New match opened.")):await sendCommand({type:setupMode==="next"?"next_deal":"setup",setup},t("Setup validated and saved."));
    if(ok){if(setupMode!=="setup")clearPredeal();$("setup-dialog").close();switchView("table");}
  }catch(error){$("setup-error").textContent=error.message;$("setup-error").hidden=false;}
});
$("edit-type").addEventListener("change",()=>{editCards=new Set();renderEditFields();});
$("event-form").addEventListener("submit",async event=>{
  event.preventDefault();
  try {
    const entry=collectEvent($("edit-type").value,"edit",editCards,Number($("edit-player").value));
    if(await sendCommand({...editAction,event:entry},t("History updated and revalidated.")))$("event-dialog").close();
  }catch(error){$("event-error").textContent=error.message;$("event-error").hidden=false;}
});
$("export").addEventListener("click",action(async()=>{
  const response=await fetch("/api/export");
  if(!response.ok)throw new Error(t("Export failed."));
  const url=URL.createObjectURL(await response.blob());
  const link=document.createElement("a");link.href=url;link.download=`${state.match.id}.player.json`;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);toast("Archive downloaded.");
}));
$("import").addEventListener("click",()=>$("import-file").click());
$("import-file").addEventListener("change",action(async()=>{
  const file=$("import-file").files[0];if(!file)return;
  try{if(file.size>8*1024*1024)throw new Error(t("The file must not exceed 8 MiB."));await mutate("/api/import",{archive:await file.text()},t("Imported a separate copy of the match."));switchView("table");}finally{$("import-file").value="";}
}));
$("open-rules").addEventListener("click",action(async()=>{
  const rules=await request("/api/rules?lang="+language);$("rules-content").textContent=rules.text;$("rules-dialog").showModal();
}));
$("open-project-status").addEventListener("click",action(async()=>{
  const result=await request("/api/project-status");
  $("status-content").textContent=result.text;$("status-dialog").showModal();
}));
function setLegalCopy(target, text){
  const docsBase="https://github.com/AleksejLeonG/Belote_engine/blob/main/";
  const fragment=document.createDocumentFragment();
  let list=null;
  for(const line of text.split(/\r?\n/)){
    if(!line||line.startsWith("# ")){list=null;continue;}
    let node,copy;
    if(line.startsWith("- ")){
      if(!list){list=document.createElement("ul");fragment.append(list);}
      node=document.createElement("li");list.append(node);copy=line.slice(2);
    }else{
      list=null;
      const heading=line.startsWith("## ");
      node=document.createElement(heading?"h3":"p");fragment.append(node);
      copy=heading?line.slice(3):line;
    }
    let end=0;
    for(const token of copy.matchAll(/\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*|`([^`]+)`/g)){
      node.append(copy.slice(end,token.index));
      const [,label,url,bold,code]=token;
      const href=url?.startsWith("https://")?url:/^[A-Z]+\.md$/.test(url||"")?docsBase+url:null;
      if(href){
        const link=document.createElement("a");link.textContent=label;link.href=href;
        link.target="_blank";link.rel="noopener noreferrer";node.append(link);
      }else if(bold||code){
        const inline=document.createElement(bold?"strong":"code");
        inline.textContent=bold||code;node.append(inline);
      }else node.append(label);
      end=token.index+token[0].length;
    }
    node.append(copy.slice(end));
  }
  target.replaceChildren(fragment);
}

document.querySelectorAll("[data-legal]").forEach(button=>button.addEventListener("click",action(async()=>{
  const result=await request("/api/legal/"+button.dataset.legal);
  const dialog=$("legal-dialog");
  $("legal-title").textContent=button.textContent;
  setLegalCopy(dialog.querySelector(".legal-copy"),result.text);
  dialog.showModal();
})));
initKnowledge();
initAdvice();
initTrump();
initPredeal();
initDeck();
initBotPlay();
renderAppWorkspace();
(async()=>{
  try{state=await request("/api/state");appLoaded=true;render();if(!botMode())restorePredeal();}
  catch(error){appLoaded=true;render();showError(t("The local engine is unavailable. Restart Bela Lab and try again. ")+error.message);}
})();

function refreshDialogLanguage() {
  if ($("setup-dialog").open) {
    renderSetupStage();
    renderSetupPicker();
  }
  if ($("event-dialog").open && editAction) {
    const old={points:$("edit-points")?.value,rank:$("edit-rank")?.value,
      has_meld:$("edit-presence")?.value!=="false",bela:$("edit-bela")?.checked,
      winning_team:$("edit-winner")?.value==="none"?null:Number($("edit-winner")?.value)};
    $("event-title").textContent = editAction.type==="replace"?l`Correct event ${editAction.index+1}`:l`Insert before event ${editAction.index+1}`;
    renderEditFields(old);
  }
}
$("language-select").addEventListener("change",action(async()=>{
  language=$("language-select").value==="hr"?"hr":"en";
  savePreference("bela.language",language);
  applyStaticLanguage();
  render(); switchView(currentView); refreshDialogLanguage(); updateThemeButton();
  updateDeckOptions();
  setBusy(busy);
  if($("rules-dialog").open) $("rules-content").textContent=(await request("/api/rules?lang="+language)).text;
}));
$("theme-toggle").addEventListener("click",()=>{
  const theme=document.documentElement.dataset.theme==="dark"?"light":"dark";
  document.documentElement.dataset.theme=theme;
  savePreference("bela.theme",theme);
  updateThemeButton();
});


// Shared shell: move existing controls without replacing their event bindings.
function setAppInspector(tab){
  appInspectorTab=tab;
  document.querySelectorAll("[data-inspector-tab]").forEach(button=>{
    const active=button.dataset.inspectorTab===tab;button.classList.toggle("active",active);button.setAttribute("aria-selected",String(active));button.tabIndex=active?0:-1;
  });
  document.querySelectorAll("[data-inspector-pane]").forEach(pane=>pane.hidden=pane.dataset.inspectorPane!==tab);
}
function bindTabKeyboard(container,attribute,activate){
  container.addEventListener("keydown",event=>{
    if(!["ArrowLeft","ArrowRight","Home","End"].includes(event.key)||!event.target.hasAttribute(attribute))return;
    const buttons=[...container.querySelectorAll(`[${attribute}]`)];let index=buttons.indexOf(event.target);
    index=event.key==="Home"?0:event.key==="End"?buttons.length-1:(index+(event.key==="ArrowRight"?1:-1)+buttons.length)%buttons.length;
    event.preventDefault();activate(buttons[index].getAttribute(attribute));buttons[index].focus();
  });
}
function initAppWorkspace(){
  if($("app-inspector"))return;
  document.body.classList.add("native-workspaces");
  const tools=$("tools-nav"),toolSection=document.createElement("section");toolSection.id="tools-nav";toolSection.className="nav-tools";
  toolSection.innerHTML='<h2 data-app-label="Tools"></h2>';
  const toolsList=tools.querySelector(".nav-tools-items");
  const advanced=document.createElement("details");
  advanced.className="app-advanced-tools";
  advanced.innerHTML='<summary data-app-label="Advanced tools"></summary>';
  for(const view of ["advice","trump","knowledge","history"]){advanced.append(toolsList.querySelector(`[data-view="${view}"]`));}
  advanced.append($("demo"));
  toolsList.append(advanced);
  toolSection.append(toolsList);tools.replaceWith(toolSection);
  const menuButton=document.createElement("button");menuButton.type="button";menuButton.className="app-tools-toggle";menuButton.setAttribute("aria-controls","tools-nav");menuButton.setAttribute("aria-expanded","false");
  menuButton.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 6h14M5 12h14M5 18h14"/></svg><span data-app-label="Tools"></span>';
  menuButton.onclick=()=>{const open=document.querySelector(".sidebar").classList.toggle("tools-open");menuButton.setAttribute("aria-expanded",String(open));};
  document.querySelector(".sidebar nav").append(menuButton);
  const preferences=document.querySelector(".preferences"),settings=document.createElement("dialog");settings.id="app-settings";
  settings.innerHTML=`<div class="dialog-heading"><h2>${t("Settings")}</h2><button type="button" class="close-button" aria-label="${t("Close")}">×</button></div><div class="app-settings-body"></div>`;
  settings.querySelector(".close-button").onclick=()=>settings.close();document.body.append(settings);
  const names=document.createElement("select");names.id="suit-names-select";
  names.innerHTML='<option value="standard">Hearts, Spades, Diamonds, Clubs</option><option value="hungarian">Hearts, Leaves, Bells, Acorns</option>';
  names.value=document.documentElement.dataset.suitNames||"standard";
  names.addEventListener("change",()=>{document.documentElement.dataset.suitNames=names.value;savePreference("bela.suitNames",names.value);refreshDeckPresentation();});
  preferences.append(names);
  for(const [id,label,description] of [["suit-names-select","Suit names","Independent of the card artwork."],["card-style-select","Card style","Choose the artwork used at the table."],["language-select","Language","Interface language."],["theme-toggle","Appearance","Switch between light and dark."]]){
    const row=document.createElement("div");row.className="preference-row";
    row.innerHTML=`<div><label for="${id}" data-app-label="${label}"></label><p data-app-label="${description}"></p></div>`;
    row.append($(id));settings.querySelector(".app-settings-body").append(row);
  }
  preferences.remove();
  const settingsButton=document.createElement("button");settingsButton.type="button";settingsButton.id="app-settings-open";settingsButton.className="app-settings-button";
  settingsButton.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 17h16M8 4v6m8 4v6"/></svg><span data-app-label="Settings"></span>';
  settingsButton.onclick=()=>{clearTimeout(botTimer);settings.showModal();};settings.addEventListener("close",()=>{scheduleBotTurn();if(window.matchMedia("(max-width:760px)").matches)document.querySelector(".app-tools-toggle").focus();});
  const footer=document.querySelector(".sidebar-bottom");footer.replaceChildren(settingsButton);placeAppSettings();
  window.addEventListener("resize",placeAppSettings);
  const pause=document.createElement("button");pause.id="app-pause";pause.type="button";pause.className="button secondary";
  pause.onclick=()=>{botPaused=!botPaused;renderBotMode();};document.querySelector(".header-actions").prepend(pause);
  const context=document.createElement("span");context.id="app-session-context";document.querySelector(".page-header>div").append(context);
  const inspector=document.createElement("section");inspector.id="app-inspector";inspector.setAttribute("aria-label",t("Game inspector"));
  inspector.innerHTML=`<div class="app-inspector-tabs" role="tablist" aria-label="${t("Game inspector")}">${[["advice","Advice"],["scores","Score"],["events","Events"]].map(([id,label])=>`<button type="button" id="inspector-tab-${id}" role="tab" data-inspector-tab="${id}" aria-controls="app-pane-${id}">${t(label)}</button>`).join("")}</div>${["advice","scores","events"].map(id=>`<section id="app-pane-${id}" role="tabpanel" aria-labelledby="inspector-tab-${id}" data-inspector-pane="${id}"></section>`).join("")}`;
  document.querySelector("#view-table .input-column").append(inspector);
  $("app-pane-advice").append($("bot-controls"),document.querySelector(".input-panel"),document.querySelector(".insight-panel"));
  $("app-pane-scores").append($("live-scores"));const recent=document.querySelector(".recent-panel");recent.open=true;$("app-pane-events").append(recent,$("export"));
  inspector.querySelectorAll("[data-inspector-tab]").forEach(button=>button.onclick=()=>setAppInspector(button.dataset.inspectorTab));
  bindTabKeyboard(inspector,"data-inspector-tab",setAppInspector);setAppInspector(appInspectorTab);
  const ledger=document.createElement("section");ledger.id="app-scoreline";ledger.setAttribute("aria-label",t("Deal and match scores"));document.querySelector(".board-panel").prepend(ledger);
  document.querySelector(".brand-mark").innerHTML='<img src="/favicon.svg" alt="" width="24" height="24">';
}
function placeAppSettings(){
  const button=$("app-settings-open");if(!button)return;
  const host=window.matchMedia("(max-width:760px)").matches?$("tools-nav"):document.querySelector(".sidebar-bottom");
  if(button.parentElement!==host)host.append(button);
}
function renderAppWorkspace(){
  initAppWorkspace();
  document.querySelector("main").setAttribute("aria-busy",String(!appLoaded));
  $("new-match").disabled=!appLoaded;
  document.querySelectorAll("[data-game-mode]").forEach(button=>button.disabled=!appLoaded);
  const icons={table:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M8 10h3v5H8zM13 9h3v5h-3z"/>',review:'<path d="M4 19V5m0 14h16M8 15l4-6 4 3 4-7"/>',saved:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M10 10v10"/>'};
  for(const [view,label] of [["table","Play"],["review","Review"],["saved","Library"]]){
    const button=document.querySelector(`.sidebar nav>[data-view="${view}"]`);
    button.innerHTML=`<span class="nav-icon"><svg viewBox="0 0 24 24" aria-hidden="true">${icons[view]}</svg></span><span>${t(label)}</span>${view==="saved"?`<span id="saved-count" class="nav-count">${state.saved.length}</span>`:""}`;
  }
  const nameOptions=$("suit-names-select").options;
  nameOptions[0].textContent=["Hearts","Spades","Diamonds","Clubs"].map(t).join(", ");
  nameOptions[1].textContent=["Hearts","Leaves","Bells","Acorns"].map(t).join(", ");
  $("app-settings-open").setAttribute("aria-label",t("Settings"));$("app-settings-open").title=t("Settings")+" · Ctrl+,";
  $("app-settings").querySelector("h2").textContent=t("Settings");
  document.querySelectorAll("[data-app-label]").forEach(node=>node.textContent=t(node.dataset.appLabel));
  if(appLastView!==currentView){document.querySelector(".sidebar").classList.remove("tools-open");document.querySelector(".app-tools-toggle").setAttribute("aria-expanded","false");appLastView=currentView;}
  const m=state.match,b=state.bot,phase=b?.calling?"calling":b?.declarations_pending?"declarations":m?.phase;
  if(phase!==appPhase){if(["calling","declarations","playing"].includes(phase))appInspectorTab="advice";appPhase=phase;}
  $("app-pause").hidden=!appLoaded||currentView!=="table"||!botMode()||!b||(!b.calling&&m?.phase!=="playing");
  $("app-pause").textContent=t(botPaused?"Resume":"Pause");$("app-pause").title=t(botPaused?"Resume bots":"Pause bots");$("app-pause").setAttribute("aria-pressed",String(botPaused));
  $("app-session-context").textContent=currentView==="table"?(botMode()?b?.name:m?.name)||"":"";
  const ledger=$("app-scoreline"),score=botMode()&&b?.calling?b.score:m?.score,own=m?.setup.player%2||0;
  ledger.hidden=!score||!botMode();
  ledger.setAttribute("aria-label",t("Deal and match scores"));
  if(score){
    const dealScores=m&&!b?.calling?liveScoreData(m):null;
    const deal=dealScores?(dealScores.recorded||dealScores.earned):null;
    const teamScore=(team,label)=>`<div class="scoreline-team">
      <span>${t(label)}</span>
      <div class="scoreline-primary"><span>${t(deal?"This deal":"Match total")}</span><strong>${deal?deal[team]:score[team]}</strong></div>
      ${deal?`<small>${t("Match total")}: ${score[team]}</small>`:""}
    </div>`;
    ledger.innerHTML=`${teamScore(own,"Our team")}${teamScore(1-own,"Their team")}<div class="scoreline-context"><span>${b?.calling?t("Dealer")+" · "+t("Player")+" "+b.dealer:t("Deal")+" "+m?.deal_number}</span><strong>${b?.calling?t("Trump calling"):t("Trick")+" "+Math.min((m?.completed_tricks.length||0)+1,8)+" / 8"}</strong><small>${b?.calling?t("Calling position")+" "+b.position+" / 4":t(b?.declarations_pending?"Declarations":m?.winner!==null&&m?.winner!==undefined?"Match finished":m?.phase==="deal_finished"?"Deal finished":botPaused?"Bots are paused.":"Play in progress")}</small></div>`;
  }
  const board=$("table-board"),ended=botMode()&&m&&!b?.calling&&["deal_finished","match_finished"].includes(m.phase);
  document.body.classList.toggle("app-session-ended",!!ended);
  if(!board.querySelector(".app-result")&&ended){
    const finished=m.winner!==null,won=finished&&m.winner===own,recorded=m.result?.recorded;
    const result=document.createElement("section");result.className="app-result";
    result.innerHTML=`<span class="result-caption">${t(finished?"Match result":"Deal result")}</span><h2>${t(finished?(won?"You won the match":"Opponents won the match"):"Deal complete")}</h2><div class="app-result-score"><div><small>${t("Our team")}</small><strong>${m.score[own]}</strong></div><div><small>${t("Their team")}</small><strong>${m.score[1-own]}</strong></div></div><p>${recorded?t("Recorded this deal")+": "+recorded[own]+" – "+recorded[1-own]:t("Belot")}</p><div class="app-result-actions"></div>`;
    const actions=result.querySelector(".app-result-actions");
    for(const id of ["bot-next","bot-review"]){const button=$(id);if(button)actions.append(button);}
    if(finished){const button=document.createElement("button");button.className="button primary";button.textContent=t("New match");button.onclick=()=>$("new-match").click();actions.prepend(button);}
    board.append(result);
  }
  if(appLoaded&&!m&&!b&&!board.querySelector(".app-empty")){
    board.innerHTML=`<div class="app-empty"><h2>${t("Start a match")}</h2><p>${t("Play with bots or track a game using the information you know.")}</p><div><button type="button" class="button primary" id="app-empty-new">${t("New match")}</button><button type="button" class="button secondary" id="app-empty-library">${t("Open library")}</button></div></div>`;
    $("app-empty-new").onclick=()=>$("new-match").click();$("app-empty-library").onclick=()=>switchView("saved");
  }
  const endedKey=ended?m.id+":"+m.deal_number:null;if(endedKey&&endedKey!==appEndedKey)appInspectorTab="scores";appEndedKey=endedKey;
  const scores=$("live-scores");scores.querySelector(".app-trick-list")?.remove();
  if(m&&!b?.calling){const data=liveScoreData(m);
    scores.insertAdjacentHTML("beforeend",`<section class="app-trick-list"><h3>${t("Tricks")}</h3>${data.tricks.length?data.tricks.map(trick=>`<div><span>${t("Trick")} ${trick.number}</span><strong>${t(trick.team===own?"Our team":"Their team")}</strong><span>+${trick.points+trick.bonus}</span></div>`).join(""):`<p class="input-hint">${t("No completed tricks yet.")}</p>`}</section>`);
  }
  const labels={advice:botMode()?"Advice":"Record a move",scores:"Score",events:"Events"};document.querySelectorAll("[data-inspector-tab]").forEach(button=>button.textContent=t(labels[button.dataset.inspectorTab]));setAppInspector(appInspectorTab);
}
window.addEventListener("keydown",event=>{
  if(event.key==="Escape"){document.querySelector(".sidebar").classList.remove("tools-open");document.querySelector(".app-tools-toggle")?.setAttribute("aria-expanded","false");}
  if(!event.ctrlKey||event.altKey||event.metaKey)return;
  if(event.key===","){event.preventDefault();$("app-settings-open")?.click();}
  else if(["1","2","3"].includes(event.key)&&!document.querySelector("dialog[open]")){event.preventDefault();switchView({"1":"table","2":"review","3":"saved"}[event.key]);}
});
document.addEventListener("click",event=>{if(!event.target.closest(".sidebar")){document.querySelector(".sidebar").classList.remove("tools-open");document.querySelector(".app-tools-toggle")?.setAttribute("aria-expanded","false");}});
