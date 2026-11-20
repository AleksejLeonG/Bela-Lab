"use strict";

let botTimer=null,botPaused=false;
const botMode=()=>state.mode==="bots";
const botContext=()=>({expected_id:state.bot?.id??null,expected_revision:state.bot?.revision??0});
const botHandCard=(card,options)=>`<div class="bot-hand-card" data-bot-hand-card="${card}">${cardMarkup(card,options)}<div class="bot-card-estimate" aria-live="polite"></div></div>`;

async function botAction(route,payload={}){
  if(busy)return;
  clearTimeout(botTimer);setBusy(true);
  try{
    state=await request(route,{...botContext(),...payload});
    selectedPlay=null;$("error-banner").hidden=true;render();
  }catch(error){botPaused=true;showError(error.message);throw error;}
  finally{setBusy(false);scheduleBotTurn();}
}

function scheduleBotTurn(){
  clearTimeout(botTimer);
  const m=state.match,b=state.bot;
  if(!botMode()||!b||busy||botPaused||currentView!=="table"||b.declarations_pending||$("declarations-dialog")?.open||$("app-settings")?.open)return;
  if(b.calling){
    if(b.calling_player!==0)botTimer=setTimeout(()=>botAction("/api/bot/step").catch(()=>{}),b.caller!==null?2300:1400);
    return;
  }
  if(b.awaiting_trick||m?.phase==="playing"&&m.next_player!==0){
    botTimer=setTimeout(()=>botAction("/api/bot/step").catch(()=>{}),b.awaiting_trick?1600:650);
  }
}

function openBotSetup(){
  $("bot-name").value=t("Practice match");$("bot-dialog").showModal();
}

function renderBotMode(){
  document.body.classList.toggle("bot-mode",botMode());
  document.querySelectorAll("[data-game-mode]").forEach(button=>{
    const active=button.dataset.gameMode===(state.mode||"manual");
    button.setAttribute("aria-pressed",String(active));button.classList.toggle("active",active);
  });
  const panel=$("bot-controls");panel.hidden=!botMode();
  if(!botMode()){scheduleBotTurn();return;}
  const existingHand=document.querySelector("#view-table .hand-panel");
  if(existingHand?.parentElement===$("table-board"))document.querySelector("#view-table .board-panel").after(existingHand);
  $("edit-setup").hidden=true;$("undo").hidden=true;$("insert-first").disabled=true;
  const b=state.bot,m=state.match,e=escapeHtml;
  let html="";
  if(!b){
    html=`<h2>${t("Play a real match")}</h2><p>${t("You and a bot partner face two opponents. Cards are dealt automatically; click a card when it is your turn.")}</p><button id="bot-start-empty" class="button primary full">${t("Start bot match")}</button>`;
    $("table-board").innerHTML=`<div class="table-placeholder"><div class="empty-suit">♣</div><h3>${t("Your seat is ready")}</h3><p>${t("Start a bot match. No manual card entry needed.")}</p></div>`;
    $("turn-message").textContent=t("Start a bot match to play.");
  }else if(b.calling){
    const callingHand=sortedCards(new Set(b.hand));
    html=botCallingMarkup(b);
    $("match-name").textContent=b.name;
    $("phase-badge").textContent=t("Trump calling");
    $("hand-count").textContent=`${callingHand.length} / 8`;
    $("hand-note").textContent=t("Your final two cards stay hidden until trump is called.");
    const faceDownCard=`<div class="bot-hand-card"><div class="playing-card talon-card" role="img" aria-label="${e(t("Face-down card"))}"><span aria-hidden="true">◆</span></div></div>`;
    $("my-hand").innerHTML=callingHand.map(card=>botHandCard(card,{disabled:true})).join("")+faceDownCard.repeat(2);
    $("table-board").innerHTML=`<div class="calling-stage">${botCallingTimeline(b)}</div>`;
    $("turn-message").textContent=b.caller!==null?t("Trump has been called. Revealing the final two cards next."):
      t("Calling position")+" "+b.position+" / 4 · "+t("Player")+" "+b.calling_player;
  }else{
    const finished=m.winner!==null,ended=m.phase!=="playing";
    html=`<span class="section-kicker">${t("PLAY AGAINST BOTS")}</span><h2>${t(finished?"Match finished":ended?"Deal finished":m.next_player===0&&!b.awaiting_trick?"Your turn":"At the table")}</h2><p>${t(ended?"Every move has been saved. Open Analysis to review your decisions.":m.next_player===0?"Choose a legal card from your hand.":botPaused?"Bots are paused.":"Waiting for the next player.")}</p>`;
    if(ended)html+=`<div class="bot-result"><strong>${m.score.join(" – ")}</strong><span>${t("Match score")}</span>${m.result?.recorded?`<p>${t("This deal")}: ${m.result.recorded.join(" – ")}</p>`:""}</div>${!finished?`<button id="bot-next" class="button primary full">${t("Next deal")}</button>`:""}<button id="bot-review" class="button secondary full">${t("Review this match")}</button>`;
    if(!ended&&!b.declarations_pending)html+=`<section id="bot-live-advice" class="bot-live-advice" aria-live="polite"></section>`;
    else if(!ended)html+=`<button id="bot-pause" class="button secondary full">${t(botPaused?"Resume bots":"Pause bots")}</button>`;
    html+=`<p class="input-hint">${t("Existing bot strategies run locally. They are not rated, and no paid service is used.")}</p>`;
    const presence=m.events.filter(row=>row.event.type==="presence").map(row=>row.event);
    html+=`<details class="bot-declarations"><summary>${t("Declarations")} · ${m.awarded_melds.join(" – ")}</summary>${b.declarations?botDeclarationsMarkup(b,m):presence.map(event=>`<p>${t("Player")} ${event.player}: ${t(event.has_meld?"Has melds":"No melds")}</p>`).join("")}</details>`;
    if(b.awaiting_trick){
      const last=m.completed_tricks.at(-1);
      $("turn-message").textContent=t("Trick winner")+": "+t("Player")+" "+last.winner+" · "+last.points+" "+t("card points");
    }else if(!ended)$("turn-message").textContent=t(m.next_player===0?"Your turn. Click a legal card in your hand.":botPaused?"Bots are paused.":"A bot is choosing its card…");
    if(b.declarations_pending){
      $("table-board").querySelector(".table-declaration-stage")?.remove();
      html=`<h2>${t("Declarations")}</h2><p>${t("Review the public declarations before the first trick. Only the winning team's meld cards are revealed.")}</p><button id="bot-start-play" class="button primary full">${t("Confirm declarations and play")}</button>`;
      $("phase-badge").textContent=t("Declarations");
      $("turn-message").textContent=t("Review declarations, then confirm to start play.");
      $("table-board").insertAdjacentHTML("beforeend",`<div class="table-declaration-stage">${botDeclarationsMarkup(b,m)}</div>`);
    }
  }
  panel.innerHTML=html;
  const publicMelds=panel.querySelector(".bot-declarations"),liveAdvice=panel.querySelector("#bot-live-advice");
  if(publicMelds&&liveAdvice)panel.insertBefore(publicMelds,liveAdvice);
  $("bot-start-empty")?.addEventListener("click",openBotSetup);
  panel.querySelectorAll("[data-bot-call]").forEach(button=>button.onclick=action(()=>botAction("/api/bot/call",{suit:button.dataset.botCall})));
  $("bot-pass")?.addEventListener("click",action(()=>botAction("/api/bot/call",{suit:null})));
  $("bot-next")?.addEventListener("click",action(()=>botAction("/api/bot/next")));
  $("bot-review")?.addEventListener("click",()=>{reviewMatchId=m.id;switchView("review");});
  $("bot-pause")?.addEventListener("click",()=>{botPaused=!botPaused;renderBotMode();});
  $("bot-start-play")?.addEventListener("click",action(()=>botAction("/api/bot/step")));
  $("next-deal").hidden=true;
  $("bot-show-declarations")?.remove();
  if(!b?.calling&&b?.declarations){
    $("table-contract").insertAdjacentHTML("beforeend",`<button id="bot-show-declarations" class="button secondary" type="button">${t("Show declarations")}</button>`);
    $("bot-show-declarations").onclick=()=>{
      clearTimeout(botTimer);renderDeclarationsDialog();$("declarations-dialog").showModal();
    };
  }
  if($("declarations-dialog").open)renderDeclarationsDialog();
  const handPanel=document.querySelector("#view-table .hand-panel");
  if(handPanel)$("table-board").append(handPanel);
  $("my-hand").style.setProperty("--hand-count",Math.max(1,$("my-hand").children.length));
  scheduleBotTurn();
  syncBotAdvice();
  if(typeof renderAppWorkspace==="function")renderAppWorkspace();
}

function botCallingTimeline(b){
  return `<span class="section-kicker">${t("TRUMP CALLING")}</span><p class="calling-score">${t("Match total")}: ${b.score.join(" – ")}</p><h3>${b.caller!==null?t("Player")+" "+b.caller+" · "+escapeHtml(suitNames()[b.trump]):t("Calling position")+" "+b.position+" / 4"}</h3><ol class="calling-sequence">${[1,2,3,4].map(position=>{
    const player=(b.dealer+position)%4,passed=b.passes.includes(player),called=player===b.caller,acting=player===b.calling_player;
    return `<li class="${acting?"calling-active":""} ${called?"calling-called":""}"><span>${position}</span><strong>${player===0?t("You"):player===2?t("Partner"):t("Opponent")} · ${t("Player")} ${player}${player===b.dealer?" · "+t("Dealer"):""}</strong><small>${called?suitMarkup(b.trump)+" "+escapeHtml(suitNames()[b.trump]):passed?t("Pass"):acting?t("Calling now"):"—"}</small></li>`;
  }).join("")}</ol>`;
}

function botCallingMarkup(b){
  if(b.calling_player===0)return `<span class="section-kicker">${t("TRUMP ADVICE")}</span><h2>${t("Your calling turn")}</h2><p>${t("Calling position")} ${b.position} / 4 · ${t("Dealer")} ${b.dealer}</p><section class="trump-auto-advice"><div class="trump-recommendation-icon">${b.suggestion?suitMarkup(b.suggestion):"↪"}</div><div><span>${t("Suggested action")}</span><strong>${b.suggestion?t("Call")+" "+escapeHtml(suitNames()[b.suggestion]):t("Pass")}</strong><small>${t("Based on your first six cards")}</small></div></section><div class="trump-ranked-choices">${b.rankings.map((r,i)=>`<button class="trump-choice ${r.suit===b.suggestion?"trump-choice-recommended":""}" data-bot-call="${r.suit}"><span class="trump-choice-icon">${suitMarkup(r.suit)}</span><span class="trump-choice-name"><strong>${escapeHtml(suitNames()[r.suit])}</strong><small>${b.hand.filter(c=>c[0]===r.suit).length} ${t("cards in suit")}${r.suit===b.suggestion?" · "+t("Suggested"):""}</small></span><span class="trump-choice-score"><strong>${r.score}</strong><small>${t("Strength")}</small></span></button>`).join("")}</div><button id="bot-pass" class="button ${b.suggestion===null&&!b.forced?"primary":"secondary"} full" ${b.forced?"disabled":""}>${t(b.forced?"Dealer must call":b.suggestion===null?"Pass · suggested":"Pass")}</button><p class="input-hint">${t("Hand-strength scores, not probabilities. The decision is yours.")}</p>`;
  return `<h2>${t(b.caller!==null?"Trump called":"Bots are calling")}</h2><p>${t("Calling position")} ${b.position} / 4</p><p>${t("Your final two cards stay hidden until trump is called.")}</p><button id="bot-pause" class="button secondary full">${t(botPaused?"Resume bots":"Pause bots")}</button>`;
}

function botDeclarationsMarkup(b,m){
  const d=b.declarations;
  if(!d)return "";
  return `<h3>${t("Declarations")}</h3><div class="declaration-presence">${d.presence.map(p=>`<div><strong>${t("Player")} ${p.player}${p.player===0?" · "+t("You"):""}</strong><span>${t(p.has_meld?"Has melds":"No melds")}</span></div>`).join("")}</div><p class="declaration-award">${d.winning_team===null?t("No ordinary melds"):t(d.winning_team===0?"Our team wins declarations":"Opponents win declarations")} · ${m.awarded_melds.join(" – ")}</p>${d.reveals.map(reveal=>`<div class="declaration-reveal"><strong>${t("Player")} ${reveal.player}</strong>${reveal.melds.map(meld=>`<div><span>${t(meld.kind==="sequence"?"Sequence":"Four of a kind")} · ${meld.points} ${t("points")} · ${t("High card")} ${escapeHtml(deckRank(meld.high))}</span><div class="declaration-card-row">${meld.cards.map(c=>cardMarkup(c,{disabled:true})).join("")}</div></div>`).join("")}</div>`).join("")}<p class="input-hint">${t("Bela is announced automatically when the first trump king or queen is played while holding both.")}</p>`;
}

function renderDeclarationsDialog(){
  if(!state.bot?.declarations||!state.match)return;
  const bela=state.match.bela_players;
  $("declarations-dialog-content").innerHTML=botDeclarationsMarkup(state.bot,state.match)+
    `<div class="declarations-bela"><strong>${t("Bela")}</strong><p>${bela.length?bela.map(player=>t("Player")+" "+player+" · 20 "+t("points")).join(", "):t("Bela has not been announced.")}</p></div>`;
}

function initBotPlay(){
  $("declarations-dialog").addEventListener("close",scheduleBotTurn);
  document.querySelectorAll("[data-game-mode]").forEach(button=>button.onclick=action(async()=>{
    if(busy)return;
    clearTimeout(botTimer);botPaused=false;
    await mutate("/api/mode",{mode:button.dataset.gameMode},t("Game mode changed."));
  }));
  $("bot-form").onsubmit=action(async event=>{
    event.preventDefault();botPaused=false;
    await botAction("/api/bot/new",{name:$("bot-name").value,profile:$("bot-profile").value});
    $("bot-dialog").close();
  });
}

function showLiveDetails(title,content){
  let dialog=$("live-details-dialog");
  if(!dialog){dialog=document.createElement("dialog");dialog.id="live-details-dialog";document.body.append(dialog);}
  dialog.innerHTML=`<div class="dialog-heading"><h2>${escapeHtml(title)}</h2><button type="button" class="close-button" aria-label="${t("Close")}">×</button></div><div class="live-details-content">${content}</div>`;
  dialog.querySelector(".close-button").onclick=()=>dialog.close();dialog.showModal();
}
