"use strict";
let language = document.documentElement.lang;
const translationPattern = new RegExp(Object.keys(CROATIAN).sort((a,b)=>b.length-a.length)
  .map(key=>{
    const escaped=key.replace(/[.*+?^${}()|[\]\\]/g,"\\$&");
    return /^[A-Za-z]+$/.test(key)?"\\b"+escaped+"\\b":escaped;
  }).join("|"),"g");
function t(text) {
  if (language !== "hr") return text;
  return text.replace(translationPattern, match=>CROATIAN[match]);
}
// Translate literal segments only; match names and other user data stay untouched.
function l(strings, ...values) {
  return strings.reduce((result, segment, index)=>result+t(segment)+(index<values.length?values[index]:""), "");
}
const staticText = [];
const staticAttributes = [];
const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
while (walker.nextNode()) {
  const node=walker.currentNode;
  if(node.textContent.trim()) staticText.push([node,node.textContent]);
}
document.querySelectorAll("[aria-label]").forEach(node=>staticAttributes.push([node,node.getAttribute("aria-label")]));
function applyStaticLanguage() {
  document.documentElement.lang=language;
  document.title=t("Bela — workbench");
  for(const [node,source] of staticText) if(node.isConnected) node.textContent=t(source);
  for(const [node,source] of staticAttributes) if(node.isConnected) node.setAttribute("aria-label",t(source));
}
function updateThemeButton() {
  const dark=document.documentElement.dataset.theme==="dark";
  document.getElementById("theme-toggle").textContent=t(dark?"Day mode":"Night mode");
  document.getElementById("theme-toggle").setAttribute("aria-pressed",String(dark));
}
applyStaticLanguage();
document.getElementById("language-select").value=language;
updateThemeButton();
