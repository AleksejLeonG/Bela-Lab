"use strict";
// Run before styles load so a remembered dark theme does not flash white.
function readPreference(key, fallback) {
  try { return localStorage.getItem(key) || fallback; } catch { return fallback; }
}
function savePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Private mode still works for this visit. */ }
}
document.documentElement.lang = readPreference("bela.language", "en") === "hr" ? "hr" : "en";
document.documentElement.dataset.theme = readPreference("bela.theme", "light") === "dark" ? "dark" : "light";
