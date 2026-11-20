"use strict";

const hungarianDeck=()=>document.documentElement.dataset.cardStyle!=="standard";
const deckSuitFiles={H:"hearts",S:"leaves",D:"bells",C:"acorns"};
const deckSuitNames=()=>document.documentElement.dataset.suitNames==="hungarian"?{H:t("Hearts"),S:t("Leaves"),D:t("Bells"),C:t("Acorns")}:
  {H:t("Hearts"),S:t("Spades"),D:t("Diamonds"),C:t("Clubs")};
function suitMarkup(suit){
  return `<span class="standard-suit" aria-hidden="true">${SYMBOLS[suit]}</span><img class="hungarian-suit" src="/cards/${deckSuitFiles[suit]}.svg" alt="" aria-hidden="true">`;
}
function deckRank(rank){return hungarianDeck()?({"7":"VII","8":"VIII","9":"IX","10":"X",J:t("Unter"),Q:t("Ober"),K:t("King"),A:t("Ace")}[rank]||rank):rank;}
// Plain-text contexts use suit names; graphical contexts use the actual suit icons.
function suitPrefix(suit){return hungarianDeck()?"":SYMBOLS[suit];}

function updateDeckOptions(){
  for(const id of ["setup-trump","knowledge-suit"]){
    const select=$(id);if(!select)continue;
    for(const option of select.options)if(deckSuitFiles[option.value])option.textContent=
      (hungarianDeck()?"":SYMBOLS[option.value]+" ")+deckSuitNames()[option.value];
  }
}

function refreshDeckPresentation(){
  // Changing appearance must preserve pending entry and unsaved review feedback.
  const fields=[...document.querySelectorAll("input[id],select[id],textarea[id]")]
    .filter(node=>node.type!=="file").map(node=>({id:node.id,value:node.value,checked:node.checked}));
  const notesOpen=$("review-notes")?.open;
  render();renderTrump();
  if(reviewData)renderReview();
  if($("setup-dialog").open)renderSetupPicker();
  refreshDialogLanguage();
  for(const field of fields){const node=$(field.id);if(node){node.value=field.value;node.checked=field.checked;}}
  if($("review-notes")&&notesOpen!==undefined)$("review-notes").open=notesOpen;
  if(reviewDirty&&$("review-note-status"))$("review-note-status").textContent=t("Unsaved note");
  updateDeckOptions();
}

function initDeck(){
  const select=$("card-style-select");select.value=hungarianDeck()?"hungarian":"standard";
  select.addEventListener("change",()=>{
    const style=select.value==="standard"?"standard":"hungarian";
    document.documentElement.dataset.cardStyle=style;savePreference("bela.cardStyle",style);
    refreshDeckPresentation();
  });
  updateDeckOptions();
}
