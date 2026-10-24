"use strict";

const $ = id => document.getElementById(id);
const SUITS = ["H", "S", "D", "C"];
const RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"];
const SYMBOLS = {H:"♥", S:"♠", D:"♦", C:"♣"};
const suitNames = () => ({H:t("Hearts"), S:t("Spades"), D:t("Diamonds"), C:t("Clubs")});
const DECK = SUITS.flatMap(s => RANKS.map(r => `${s}_${r}`));
const phases = () => ({declarations:t("Meld declarations"), playing:t("Play in progress"), deal_finished:t("Deal finished"), match_finished:t("Match finished")});
let state = {match:null, saved:[]};
let currentView = "table", currentTab = "play", selectedPlay = null, busy = false;
let setupMode = "new", setupCards = new Set(), meldCards = new Set(), editCards = new Set(), editAction = null;
let toastTimer;
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const red = code => code[0] === "H" || code[0] === "D";
const cardLabel = code => `${SYMBOLS[code[0]]} ${code.split("_")[1]}`;
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
    if (previousKey !== `${state.match.id}:${state.match.deal_number}`) meldCards = new Set();
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
  return l`<button class="playing-card ${red(code)?"red":""} ${selected?"selected":""} ${legal?"legal":""} ${table?"on-table":""}" data-card="${code}" aria-label="${suitNames()[code[0]]} ${code.split("_")[1]}" ${disabled?"disabled":""}><span class="card-rank">${code.split("_")[1]}</span><span class="card-center">${SYMBOLS[code[0]]}</span><span class="card-bottom">${SYMBOLS[code[0]]}</span></button>`;
}
function picker(target, selected, onPick, disabled = () => false) {
  target.innerHTML = SUITS.map(suit => l`<div class="suit-row"><span class="suit-label ${red(suit)?"red":""}">${SYMBOLS[suit]}</span>${RANKS.map(rank => {
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
  currentView = view;
  document.querySelectorAll(".view").forEach(node => node.hidden = node.id !== `view-${view}`);
  document.querySelectorAll(".nav-item").forEach(node => {
    node.classList.toggle("active", node.dataset.view === view);
    if (node.dataset.view === view) node.setAttribute("aria-current", "page");
    else node.removeAttribute("aria-current");
  });
  const titles = {table:[t("Game table"),t("Track the game. Check moves. Develop strategy.")],history:[t("Event history"),t("Every move and correction, in one place.")],saved:[t("My matches"),t("Save your progress and return when you like.")],help:[t("Rules and help"),t("Agreed rules and a clear way to play.")]};
  titles.knowledge=[t("What we know"),t("Every conclusion has a reason.")];
  $("page-title").textContent = titles[view][0];
  $("page-subtitle").textContent = titles[view][1];
  if(view==="knowledge")loadKnowledge();
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
  $("saved-count").textContent = state.saved.length;
  const ownTeam = m ? m.setup.player % 2 : 0;
  $("score-strip").innerHTML = [0,1].map(team => l`<div class="score-card ${team===ownTeam?"our-team":""}"><div class="score-label">${m && team===ownTeam?t("OUR TEAM"):t("TEAM ")+team} <span>· ${team} + ${team+2}</span></div><div class="score-value">${m?.score[team] ?? 0}<small>points</small></div><span class="suit-icon">${team===ownTeam?"♣":"♤"}</span></div>`).join("") + l`<div class="score-card compact"><div class="score-label">TRUMP</div><div class="score-value">${m?SYMBOLS[m.setup.trump]+" "+suitNames()[m.setup.trump]:"—"}</div><div class="score-detail">${m?t("Called by player ")+m.setup.caller:t("Awaiting selection")}</div></div><div class="score-card compact"><div class="score-label">DEAL ${m?.deal_number ?? "—"}</div><div class="score-value">${m?Math.min(m.completed_tricks.length+1,8):"—"}<small>/ 8 tricks</small></div><div class="score-detail">${m?t("Dealer: player ")+m.setup.dealer:t("New match")}</div></div>`;
  $("match-name").textContent = m?.name ?? t("Your next move starts here");
  $("phase-badge").textContent = m ? phases()[m.phase] : t("Ready to play");
  $("phase-badge").classList.toggle("live", m?.phase === "playing");
  $("edit-setup").hidden = !m;
  $("next-deal").hidden = !m?.result || m.winner !== null;
  $("export").disabled = !m;
  $("insert-first").disabled = !m;
  renderBoard(); renderHand(); renderPlay(); renderMeldFields(); renderHistory(); renderLibrary();
  syncKnowledge();
  const recent = m?.events.slice(-3).reverse() ?? [];
  $("recent-events").innerHTML = recent.length ? recent.map(e => l`<div class="recent-row"><span class="event-number">${e.index+1}</span><span>${escapeHtml(friendlyEvent(e.event))}</span></div>`).join("") : t('<div class="recent-empty">Your game is waiting for its first event.</div>');
  $("undo").disabled = !m?.events.length;
  $("small-metrics").innerHTML = l`<div class="small-metric"><span>OUR TEAM'S TRICKS</span><strong>${m?.trick_counts[ownTeam] ?? 0}<small> / ${m?.completed_tricks.length ?? 0} completed</small></strong></div><div class="small-metric"><span>CARD POINTS</span><strong>${m?.trick_points[ownTeam] ?? 0}<small> our team</small></strong></div><div class="small-metric"><span>ORDINARY MELDS</span><strong>${m?.awarded_melds[ownTeam] ?? 0}<small> requires at least one trick</small></strong></div>`;
  if (m?.phase === "declarations") switchTab("meld");
  else switchTab(currentTab);
}
function renderBoard() {
  const m = state.match;
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
  const played = m.trick.plays.map(p => l`<div class="table-card ${positions[(p.player-m.setup.player+4)%4]}">${cardMarkup(p.card,{table:true,disabled:true})}</div>`).join("");
  $("table-board").innerHTML = l`<div class="board-wordmark">bela<small>CROATIAN BELA</small></div>${seats}${played}`;
  let message = m.phase==="declarations" ? t("Record public melds, then confirm their outcome.") : m.next_player===m.setup.player ? t("Your turn. Choose one of the legal cards.") : m.next_player!==null ? l`Player to act: ${m.next_player}. Record their card.` : t("The deal is finished. Scoring is confirmed.");
  if (m.winner!==null) message = l`Match finished. Winning team: ${m.winner}.`;
  $("turn-message").textContent = message;
}
function renderHand() {
  const m = state.match;
  $("hand-count").textContent = l`${m?.hand.length ?? 0} / 8`;
  $("my-hand").innerHTML = m?.hand.length ? m.hand.map(c => cardMarkup(c,{legal:m.legal_cards.includes(c),selected:selectedPlay===c,disabled:m.next_player!==m.setup.player || !m.legal_cards.includes(c)})).join("") : l`<div class="empty-hand">${m?t("You have played all your cards."):t("Your eight cards will appear here.")}</div>`;
  $("my-hand").querySelectorAll("[data-card]").forEach(button => button.addEventListener("click", () => {
    selectedPlay = button.dataset.card; switchTab("play"); renderHand(); renderPlay();
  }));
  $("hand-note").textContent = m && m.next_player===m.setup.player ? t("Highlighted cards are legal. Their order is not a recommendation.") : t("Other players' unrevealed cards stay hidden.");
}
function renderPlay() {
  const m = state.match, actor = m?.next_player;
  $("actor-badge").textContent = actor ?? "—";
  $("actor-name").textContent = actor===null || actor===undefined ? t("Waiting for the next move") : actor===m.setup.player?t("Your turn"):t("Player ")+actor+t(" is to act");
  $("actor-detail").textContent = m?.phase === "declarations" ? t("Finish ordinary declarations first.") : actor!==null && actor!==undefined ? t("Enter the card that was actually played.") : t("Open a match or a new deal.");
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
  $("library-content").innerHTML = state.saved.length ? l`<div class="library-grid">${state.saved.map(s=>l`<article class="saved-item"><div class="saved-icon">♧</div><h3>${escapeHtml(s.name)}</h3><p>${s.deals} deals · ${s.revision} revisions<br>${escapeHtml(new Date(s.modified*1000).toLocaleString("hr-HR"))}</p><button class="button secondary" data-load="${s.id}">Continue match →</button></article>`).join("")}</div>` : t('<div class="empty-section">Your saved matches will appear here.<br>You can also import an existing player archive.</div>');
  $("library-content").querySelectorAll("[data-load]").forEach(b=>b.addEventListener("click",action(async()=>{await mutate("/api/load",{id:b.dataset.load},t("Match loaded."));switchView("table");})));
}
async function openDemo() {
  await mutate("/api/demo",{},t("Opened a separate copy of the demo match."));
  switchView("table"); switchTab("play");
}
function renderSetupPicker() {
  picker($("setup-picker"),setupCards,card=>{toggleCard(setupCards,card);renderSetupPicker();});
  $("setup-selected").textContent = `${setupCards.size} / 8 selected`;
}
function openSetup(mode) {
  setupMode = mode;
  const m = state.match, s=m?.setup;
  setupCards = new Set(mode==="setup"?s.hand:[]);
  $("setup-title").textContent = mode==="new"?t("New match"):mode==="next"?t("Next deal"):t("Edit initial setup");
  $("setup-name").value = mode==="new"?t("My match"):m.name;
  $("setup-name").disabled = mode!=="new";
  $("setup-player").value = s?.player ?? 0;
  $("setup-player").disabled = mode!=="new";
  $("setup-dealer").value = mode==="next"?(s.dealer+1)%4:s?.dealer ?? 3;
  $("setup-dealer").disabled = mode==="next";
  $("setup-caller").value = mode==="setup"?s.caller:0;
  $("setup-trump").value = mode==="setup"?s.trump:"H";
  for(const team of [0,1]) {
    $(`setup-score${team}`).value = mode==="next"?m.score[team]:mode==="setup"?s.match_score[team]:0;
    $(`setup-score${team}`).disabled = mode==="next";
  }
  $("setup-submit").textContent = mode==="new"?t("Open match →"):mode==="next"?t("Start deal →"):t("Validate and save →");
  $("setup-error").hidden = true;
  renderSetupPicker(); $("setup-dialog").showModal();
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
$("new-match").addEventListener("click",()=>openSetup("new"));
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
    if(setupCards.size!==8)throw new Error(t("Select exactly eight cards for your starting hand."));
    const setup={player:Number($("setup-player").value),hand:sortedCards(setupCards),dealer:Number($("setup-dealer").value),caller:Number($("setup-caller").value),trump:$("setup-trump").value,match_score:[Number($("setup-score0").value),Number($("setup-score1").value)]};
    const ok=setupMode==="new"?await mutate("/api/new",{name:$("setup-name").value,setup},t("New match opened.")):await sendCommand({type:setupMode==="next"?"next_deal":"setup",setup},t("Setup validated and saved."));
    if(ok){$("setup-dialog").close();switchView("table");}
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
initKnowledge();
(async()=>{
  try{state=await request("/api/state");render();}
  catch(error){render();showError(t("Cannot connect to the local engine. Check that the dashboard is running and refresh the page. ")+error.message);}
})();

function refreshDialogLanguage() {
  if ($("setup-dialog").open) {
    $("setup-title").textContent = t(setupMode==="new"?"New match":setupMode==="next"?"Next deal":"Edit initial setup");
    $("setup-submit").textContent = t(setupMode==="new"?"Open match →":setupMode==="next"?"Start deal →":"Validate and save →");
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
  setBusy(busy);
  if($("rules-dialog").open) $("rules-content").textContent=(await request("/api/rules?lang="+language)).text;
}));
$("theme-toggle").addEventListener("click",()=>{
  const theme=document.documentElement.dataset.theme==="dark"?"light":"dark";
  document.documentElement.dataset.theme=theme;
  savePreference("bela.theme",theme);
  updateThemeButton();
});
