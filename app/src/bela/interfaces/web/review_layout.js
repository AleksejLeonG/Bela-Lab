"use strict";

let reviewTab="analysis";
function setReviewTab(tab){
  reviewTab=["summary","analysis","moves","notes"].includes(tab)?tab:"summary";
  document.querySelectorAll("[data-review-tab]").forEach(button=>{
    const selected=button.dataset.reviewTab===reviewTab;
    button.classList.toggle("active",selected);button.setAttribute("aria-selected",String(selected));button.tabIndex=selected?0:-1;
  });
  document.querySelectorAll("[data-review-pane]").forEach(pane=>pane.hidden=pane.dataset.reviewPane!==reviewTab);
}

function arrangeReviewWorkspace(){
  const layout=document.querySelector(".analysis-layout"),engine=$("review-engine");
  if(!layout||!engine)return;
  layout.classList.add("review-workspace");
  const side=document.createElement("aside");side.className="panel review-workbench";
  side.innerHTML=`<div class="review-workbench-tabs" role="tablist" aria-label="${t("Review tools")}">${[["analysis","Compare cards"],["summary","Match summary"],["moves","Move list"],["notes","My notes"]].map(([id,label])=>`<button type="button" role="tab" id="review-tab-${id}" data-review-tab="${id}" aria-controls="review-pane-${id}">${t(label)}</button>`).join("")}</div>${["summary","analysis","moves","notes"].map(id=>`<section id="review-pane-${id}" class="review-workbench-pane" data-review-pane="${id}" role="tabpanel" aria-labelledby="review-tab-${id}"></section>`).join("")}`;
  layout.append(side);
  const table=$("review-table"),hand=document.querySelector(".analysis-hand-panel");
  if(table&&hand){table.append(hand);$("review-hand").style.setProperty("--hand-count",Math.max(1,$("review-hand").children.length));}
  const timeline=document.querySelector(".analysis-timeline");
  if(timeline){
    const nextOwn=document.createElement("button");nextOwn.type="button";
    nextOwn.id="review-next-decision";nextOwn.className="button secondary";
    nextOwn.textContent=t("Your next decision")+" →";
    const frames=reviewData.deals[reviewDeal].frames;
    const index=frames.findIndex((frame,i)=>i>reviewFrame&&frame.position.can_analyse);
    nextOwn.disabled=index<0;nextOwn.onclick=()=>reviewNavigate(()=>reviewFrame=index);
    timeline.querySelector(".analysis-timeline-heading").prepend(nextOwn);
  }
  $("review-pane-summary").append($("review-coach"));
  $("review-pane-analysis").append(engine);
  const moves=document.querySelector(".analysis-all-moves");
  moves.open=true;$("review-pane-moves").append(document.querySelector(".review-tricks"),moves);
  const publicInfo=document.querySelector(".analysis-public");
  if(publicInfo)$("review-pane-moves").append(publicInfo);
  const notes=$("review-notes");notes.open=true;$("review-pane-notes").append(notes);
  side.querySelectorAll("[data-review-tab]").forEach(button=>button.onclick=()=>setReviewTab(button.dataset.reviewTab));
  const frame=reviewData.deals[reviewDeal].frames[reviewFrame];
  const trickMoves=reviewData.deals[reviewDeal].frames.map((f,i)=>({frame:f,index:i})).filter(row=>row.frame.trick_number===frame.trick_number);
  const context=document.createElement("section");context.className="review-trick-context";
  context.innerHTML=`<h3>${t("Trick")} ${frame.trick_number} / 8</h3><div>${trickMoves.map(row=>`<button type="button" class="${row.index===reviewFrame?"is-current":""}" data-context-move="${row.index}"><span>${t("Player")} ${row.frame.played.player}</span><strong>${escapeHtml(cardLabel(row.frame.played.card))}</strong></button>`).join("")}</div>`;
  context.querySelectorAll("[data-context-move]").forEach(button=>button.onclick=()=>reviewNavigate(()=>reviewFrame=Number(button.dataset.contextMove)));
  side.append(context);
  if(typeof bindTabKeyboard==="function")bindTabKeyboard(side,"data-review-tab",setReviewTab);
  setReviewTab(reviewTab);
}

window.addEventListener("keydown",event=>{
  if(typeof currentView==="undefined"||currentView!=="review"||event.altKey||event.ctrlKey||event.metaKey)return;
  if(event.target.closest("input,textarea,select,[contenteditable=true],dialog"))return;
  const id=event.key==="ArrowLeft"?"review-prev":event.key==="ArrowRight"?"review-next":null;
  if(id&&$(id)&&!$(id).disabled){event.preventDefault();$(id).click();}
});
