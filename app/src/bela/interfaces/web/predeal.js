"use strict";
let predealDraft=null, setupStage="six";
const predealKey="bela.predeal.v1";
function savePredeal(){
  try{if(predealDraft)localStorage.setItem(predealKey,JSON.stringify(predealDraft));else localStorage.removeItem(predealKey);}catch{}
}
function clearPredeal(){predealDraft=null;savePredeal();renderPredeal();}
function renderPredeal(){
  $("predeal-panel").hidden=!predealDraft;
  $("trump-context").textContent=t(predealDraft?"Review advice for this deal before recording the actual call.":
    "Select your six cards before picking up the talon. This tool is separate from the open match.");
  if(!predealDraft)return;
  $("predeal-name").textContent=predealDraft.name;
  const rec=typeof trumpResult!=="undefined"?trumpResult?.recommendation:null;
  $("predeal-recommendation").textContent=rec?t("Advice: ")+(rec.action==="pass"?t("Pass"):
    `${t("Call")} ${suitPrefix(rec.suit)} ${suitNames()[rec.suit]}`):trumpRunning?t("Getting trump advice…"):
    typeof trumpError!=="undefined"&&trumpError?trumpError:t("Select Get trump advice to compare your six cards.");
  $("predeal-continue").disabled=trumpRunning||trumpCards.size!==6;
  $("trump-player").disabled=predealDraft.mode==="next";
  $("trump-dealer").disabled=predealDraft.mode==="next";
}
function beginCallingSetup(){
  if(setupCards.size!==6)throw new Error(t("Select exactly six cards before the talon."));
  predealDraft={mode:setupMode,name:$("setup-name").value,
    player:Number($("setup-player").value),dealer:Number($("setup-dealer").value),
    score:[Number($("setup-score0").value),Number($("setup-score1").value)],
    six:sortedCards(setupCards),source:context()};
  savePredeal();$("setup-dialog").close();showCallingDraft();startTrump();
}
function showCallingDraft(){
  trumpCards=new Set(predealDraft.six);
  $("trump-player").value=predealDraft.player;$("trump-dealer").value=predealDraft.dealer;
  trumpChanged();switchView("trump");renderPredeal();
}
function continueCallingSetup(){
  if(!predealDraft||trumpCards.size!==6)return;
  if(JSON.stringify(predealDraft.source)!==JSON.stringify(context())){
    showError(t("The current match changed. Start deal setup again."));return;
  }
  predealDraft.six=sortedCards(trumpCards);
  predealDraft.player=Number($("trump-player").value);predealDraft.dealer=Number($("trump-dealer").value);
  savePredeal();setupMode=predealDraft.mode;setupStage="eight";setupCards=new Set(predealDraft.six);
  $("setup-name").value=predealDraft.name;$("setup-name").disabled=true;
  $("setup-player").value=predealDraft.player;$("setup-player").disabled=true;
  $("setup-dealer").value=predealDraft.dealer;$("setup-dealer").disabled=true;
  for(const team of [0,1]){$(`setup-score${team}`).value=predealDraft.score[team];$(`setup-score${team}`).disabled=true;}
  // Record what actually happened, including another player's call after a pass.
  // A recommendation must never silently become the recorded trump/caller.
  $("setup-caller").value="";$("setup-trump").value="";
  $("setup-error").hidden=true;renderSetupStage();renderSetupPicker();$("setup-dialog").showModal();
}
function renderSetupStage(){
  const six=setupStage==="six";
  $("setup-caller-label").hidden=six;$("setup-trump-label").hidden=six;
  $("setup-caller").disabled=six;$("setup-trump").disabled=six;
  $("setup-title").textContent=t(six?(setupMode==="next"?"Next deal · six cards":"New match · six cards"):
    predealDraft&&setupMode!=="setup"?"Confirm the call and add two cards":"Edit initial setup");
  $("setup-hand-title").textContent=t(six?"First six cards":"Full eight-card hand");
  $("setup-hand-hint").textContent=t(setupMode==="setup"?"Enter your hand after picking up the talon. Seats 0–3 follow the order of play.":six?"Enter only the six cards you can see before trump is called.":
    "Record the actual caller and trump, then add your final two cards. Your original six stay selected.");
  $("setup-submit").textContent=t(six?"Get trump advice →":setupMode==="new"?"Open match →":setupMode==="next"?"Start deal →":"Validate and save →");
  $("setup-back").hidden=six||setupMode==="setup";
}
function restorePredeal(){
  try{
    const d=JSON.parse(localStorage.getItem(predealKey));
    if(!d||!["new","next"].includes(d.mode)||typeof d.name!=="string"||
      !Array.isArray(d.six)||d.six.length>6||new Set(d.six).size!==d.six.length||d.six.some(c=>!DECK.includes(c))||
      ![d.player,d.dealer].every(s=>Number.isInteger(s)&&s>=0&&s<=3)||
      !Array.isArray(d.score)||d.score.length!==2||d.score.some(s=>!Number.isInteger(s)||s<0)||
      JSON.stringify(d.source)!==JSON.stringify(context()))return;
    predealDraft=d;showCallingDraft();
  }catch{}
}
function initPredeal(){
  $("predeal-continue").addEventListener("click",continueCallingSetup);
  $("predeal-cancel").addEventListener("click",()=>{clearPredeal();renderTrump();switchView("table");});
  $("setup-back").addEventListener("click",()=>{$("setup-dialog").close();showCallingDraft();});
}
