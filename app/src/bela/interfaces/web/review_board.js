"use strict";

function renderAnalysisBoard(){
  if(!reviewData)return;
  const deal=reviewData.deals[reviewDeal],frames=deal.frames,e=escapeHtml;
  reviewFrame=Math.max(0,Math.min(reviewFrame,frames.length-1));
  const frame=frames[reviewFrame],own=deal.setup.player,team=own%2;
  const matchOptions=state.saved.map(m=>`<option value="${e(m.id)}" ${m.id===reviewData.match_id?"selected":""}>${e(m.name)}</option>`).join("");
  let html=`<div class="analysis-toolbar"><div><h2>${e(reviewData.name)}</h2></div><div class="analysis-open"><label>${t("Saved match")}<select id="review-match">${matchOptions}</select></label><button id="review-refresh" class="button secondary">${t("Reload review")}</button></div></div>
    <div class="analysis-score-strip"><div><span>${t("Our team")}</span><strong>${deal.setup.match_score[team]}</strong></div><div><span>${t("Their team")}</span><strong>${deal.setup.match_score[1-team]}</strong></div><div><span>${t("Trump")}</span><strong class="${red(deal.setup.trump)?"red":""}">${suitPrefix(deal.setup.trump)} ${suitNames()[deal.setup.trump]}</strong></div><div><span>${t("Caller")}</span><strong>${t("Player")} ${deal.setup.caller}</strong></div></div>`;
  html+=`<section id="review-coach" class="panel review-coach"></section>`;
  if(!frame){
    $("review-content").innerHTML=html+`<div class="panel analysis-no-moves"><h3>${t("No cards recorded in this deal yet.")}</h3><p>${t("Record moves in Live game, then return here to explore the decisions.")}</p><label>${t("Deal")}<select id="review-deal">${reviewDealOptions()}</select></label><button id="review-live" class="button secondary">${t("Return to live game")}</button></div>`;
    wireReview();renderReviewCoach();$("review-live").onclick=()=>switchView("table");return;
  }
  const pos=frame.position,positions=["bottom","right","top","left"];
  const seats=[0,1,2,3].map(offset=>{
    const player=(own+offset)%4,role=offset===0?t("You"):offset===2?t("Partner"):t("Opponent");
    return `<div class="seat ${positions[offset]} ${pos.next_player===player?"on-turn":""}"><span class="avatar">${player}</span><div><div class="seat-name">${role} · ${player}</div><div class="seat-meta">${pos.remaining_counts[player]} ${t("cards")}${player!==own?" · "+t("hidden"):""}</div></div></div>`;
  }).join("");
  const plays=trickCardsMarkup(pos.trick.plays,own);
  const hand=frame.hand_before.map(c=>cardMarkup(c,{legal:frame.legal_cards.includes(c),selected:c===frame.played.card,disabled:true})).join("");
  html+=`<div class="analysis-layout"><div class="analysis-play-column"><section class="panel analysis-table-panel"><div class="analysis-table-heading"><span class="pill">${t("Trick")} ${frame.trick_number} / 8</span><span>${t("Position before recorded move")}</span><span class="pill live">${pos.next_player===own?t("Your decision"):t("Player")+" "+pos.next_player}</span></div><div id="review-table" class="table-board analysis-table"><div class="board-wordmark">bela<small>${t("ANALYSIS")}</small></div>${seats}${plays}</div><div class="analysis-recorded"><span>${t("Recorded move")}: <strong>${t("Player")} ${frame.played.player} → ${e(cardLabel(frame.played.card))}${frame.played.bela?" · Bela":""}</strong></span><button id="review-flag-toggle" class="text-button">${frame.feedback.flagged?"⚑ "+t("Flagged decision"):"⚐ "+t("Add a review note")}</button></div></section>
    <section class="panel analysis-hand-panel"><div class="analysis-hand-heading"><h3>${t("Your hand before this move")}</h3><span>${frame.hand_before.length} / 8</span></div><div id="review-hand" class="analysis-hand">${hand||`<p>${t("You have played all your cards.")}</p>`}</div><p id="review-hand-hint" class="input-hint">${t("Selected card was played. Legal cards are marked when it is your turn.")}</p></section>
    <div class="analysis-public-summary"><span>${t("Card points so far")}: <strong>${pos.trick_points[team]} – ${pos.trick_points[1-team]}</strong></span><span>${t("Tricks")}: <strong>${pos.trick_counts[team]} – ${pos.trick_counts[1-team]}</strong></span><span>${t("Ordinary melds")}: <strong>${pos.awarded_melds[team]} – ${pos.awarded_melds[1-team]}</strong></span></div>
    <details class="panel analysis-public"><summary>${t("Public information at this position")}</summary><p>${t("Only events already known at this decision are included.")}</p><ol>${pos.events.map(event=>`<li>${e(friendlyEvent(event))}</li>`).join("")}</ol></details></div><aside id="review-engine" class="panel analysis-engine" aria-live="polite"></aside></div>
    <section class="panel analysis-timeline"><div class="analysis-timeline-heading"><h3>${t("Deal timeline")}</h3><label>${t("Deal")}<select id="review-deal">${reviewDealOptions()}</select></label></div><div class="review-tricks">${[...new Set(frames.map(f=>f.trick_number))].map(n=>`<button class="button secondary ${n===frame.trick_number?"is-current":""}" aria-pressed="${n===frame.trick_number}" data-review-trick="${n}">${t("Trick")} ${n}${frames.some(f=>f.trick_number===n&&f.feedback.flagged)?" ⚑":""}</button>`).join("")}</div><div class="review-controls"><button id="review-prev" class="button secondary" ${reviewFrame===0?"disabled":""}>← ${t("Previous move")}</button><select id="review-step" aria-label="${t("Recorded move")}">${frames.map((f,i)=>`<option value="${i}" ${i===reviewFrame?"selected":""}>${t("Trick")} ${f.trick_number} · ${t("Player")} ${f.played.player}: ${e(cardLabel(f.played.card))}${f.feedback.flagged?" ⚑":""}</option>`).join("")}</select><button id="review-next" class="button secondary" ${reviewFrame===frames.length-1?"disabled":""}>${t("Next move")} →</button></div>
    <details class="analysis-all-moves"><summary>${t("All recorded moves")}</summary><div class="analysis-move-list">${frames.map((f,i)=>`<button class="text-button ${i===reviewFrame?"is-current":""}" data-review-move="${i}" aria-current="${i===reviewFrame?"step":"false"}"><span>${i+1}.</span> ${t("Player")} ${f.played.player} · ${e(cardLabel(f.played.card))}${f.feedback.flagged?" ⚑":""}</button>`).join("")}</div></details><p class="input-hint">${frame.trick_complete?`${t("After this move")}: ${t("Trick winner")} ${frame.trick.winner} · ${frame.trick.points} ${t("card points")}.`:""} ${deal.recorded?`${t("Final recorded deal points")}: ${deal.recorded.join(" – ")} · ${t("Final match score")}: ${deal.score.join(" – ")}`:""}</p></section>
    <details id="review-notes" class="panel analysis-notes" ${frame.feedback.flagged||frame.feedback.note?"open":""}><summary>${t("Review note")}${frame.feedback.flagged?" ⚑":""}</summary>${reviewNoteMarkup(frame)}</details>`;
  if(reviewData.unreadable_logs)html+=`<p>${t("Some advice logs could not be read.")}</p>`;
  $("review-content").innerHTML=html;
  document.querySelector(".analysis-play-column").appendChild(document.querySelector(".analysis-timeline"));
  document.querySelector(".analysis-play-column").appendChild($("review-notes"));
  arrangeReviewWorkspace();
  wireReview();renderReviewEngine();renderReviewCoach();
  $("review-flag-toggle").onclick=()=>{setReviewTab("notes");$("review-notes").open=true;$("review-note").focus();};
  document.querySelectorAll("[data-review-move]").forEach(button=>button.onclick=()=>reviewNavigate(()=>reviewFrame=Number(button.dataset.reviewMove)));
}

function reviewDealOptions(){return reviewData.deals.map((d,i)=>`<option value="${i}" ${i===reviewDeal?"selected":""}>${d.number} · ${d.score.join(" – ")}</option>`).join("");}

function reviewNoteMarkup(frame){
  const note=frame.feedback,e=escapeHtml;
  return `<form id="review-note-form" class="review-note"><label class="checkbox-line"><input id="review-flag" type="checkbox" ${note.flagged?"checked":""}> ${t("Flag as suspicious")}</label><label>${t("My preferred card")}<select id="review-alternative"><option value="">—</option>${frame.legal_cards.map(c=>`<option value="${c}" ${note.alternative===c?"selected":""}>${e(cardLabel(c))}</option>`).join("")}</select></label><label>${t("What looks wrong?")}<textarea id="review-note" rows="4" maxlength="4000">${e(note.note)}</textarea></label><button class="button primary" type="submit">${t("Save review note")}</button><span id="review-note-status" role="status"></span></form>`;
}
