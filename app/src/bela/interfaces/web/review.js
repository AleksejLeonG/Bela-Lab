"use strict";

let reviewData=null, reviewDeal=0, reviewFrame=0, reviewSerial=0, reviewDirty=false, reviewSaving=false;
let reviewMatchId=null;

async function loadReview(matchId=reviewMatchId){
  if(reviewSaving)return;
  if(reviewDirty&&!confirm(t("Discard unsaved review note?"))){
    if($("review-match"))$("review-match").value=reviewData.match_id;return;
  }
  stopGameReview();abandonReviewAnalysis();
  const serial=++reviewSerial;
  if(typeof matchId!=="string")matchId=reviewMatchId;
  const requestedId=matchId||state.match?.id||state.saved[0]?.id;
  $("review-content").textContent=t("Loading review…");
  try{
    const data=await request("/api/review"+(requestedId?"?match_id="+encodeURIComponent(requestedId):""));
    if(serial!==reviewSerial)return;
    reviewData=data;reviewMatchId=data.match_id;reviewDirty=false;
    reviewDeal=Math.min(reviewDeal,data.deals.length-1);reviewFrame=0;
    renderReview();
  }catch(error){if(serial===reviewSerial)$("review-content").textContent=error.message;}
}

function renderReview(){renderAnalysisBoard();}

function reviewNavigate(fn){
  if(reviewSaving)return;
  if(reviewDirty&&!confirm(t("Discard unsaved review note?"))){
    $("review-deal").value=String(reviewDeal);$("review-step").value=String(reviewFrame);return;
  }
  reviewDirty=false;abandonReviewAnalysis();fn();renderReview();
}
function wireReview(){
  $("review-refresh").onclick=()=>loadReview();
  $("review-match").onchange=event=>{const id=event.target.value;loadReview(id);};
  $("review-deal").onchange=event=>reviewNavigate(()=>{reviewDeal=Number(event.target.value);reviewFrame=0;});
  if(!$("review-step"))return;
  $("review-prev").onclick=()=>reviewNavigate(()=>reviewFrame--);
  $("review-next").onclick=()=>reviewNavigate(()=>reviewFrame++);
  $("review-step").onchange=event=>reviewNavigate(()=>reviewFrame=Number(event.target.value));
  document.querySelectorAll("[data-review-trick]").forEach(button=>button.onclick=()=>reviewNavigate(()=>reviewFrame=reviewData.deals[reviewDeal].frames.findIndex(f=>f.trick_number===Number(button.dataset.reviewTrick))));
  const form=$("review-note-form");form.oninput=()=>{reviewDirty=true;$("review-note-status").textContent=t("Unsaved note");};
  form.onsubmit=action(async event=>{
    event.preventDefault();
    const frame=reviewData.deals[reviewDeal].frames[reviewFrame];
    if(reviewSaving)return;
    reviewSaving=true;
    form.querySelectorAll("input,select,textarea,button").forEach(node=>node.disabled=true);
    try{
      const result=await request("/api/review/feedback",{expected_id:reviewData.match_id,expected_revision:reviewData.revision,
        key:frame.key,version:frame.feedback.version,flagged:$("review-flag").checked,
        alternative:$("review-alternative").value,note:$("review-note").value});
      frame.feedback=result.feedback;reviewDirty=false;renderReview();$("review-note-status").textContent=t("Review note saved.");
    }finally{reviewSaving=false;form.querySelectorAll("input,select,textarea,button").forEach(node=>node.disabled=false);}
  });
}

window.addEventListener("beforeunload",event=>{if(reviewDirty){event.preventDefault();event.returnValue="";}});
