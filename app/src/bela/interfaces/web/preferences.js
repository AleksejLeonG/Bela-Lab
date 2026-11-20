"use strict";
let desktopShell=typeof location!=="undefined" && location.search.includes("desktop=1");
try { desktopShell=desktopShell||sessionStorage.getItem("bela.desktop")==="1"; if(desktopShell)sessionStorage.setItem("bela.desktop","1"); } catch { /* Session storage may be unavailable. */ }
document.documentElement.dataset.shell=desktopShell?"desktop":"browser";
// Run before styles load so a remembered dark theme does not flash white.
function readPreference(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function savePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Private mode still works for this visit. */ }
}
document.documentElement.lang = readPreference("bela.language", "en") === "hr" ? "hr" : "en";
document.documentElement.dataset.theme = readPreference("bela.theme", "light") === "dark" ? "dark" : "light";
document.documentElement.dataset.cardStyle = readPreference("bela.cardStyle", "hungarian") === "standard" ? "standard" : "hungarian";

document.documentElement.dataset.suitNames=readPreference("bela.suitNames","standard")==="hungarian"?"hungarian":"standard";
