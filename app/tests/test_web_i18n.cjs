// Run with: node app/tests/test_web_i18n.cjs
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const web=path.join(__dirname,"../src/bela/interfaces/web");
const elements=new Map();
const element=id=>{
  if(!elements.has(id)) elements.set(id,{textContent:"",value:"",setAttribute(){}});
  return elements.get(id);
};
const context=vm.createContext({
  CROATIAN:JSON.parse(fs.readFileSync(path.join(web,"hr.json"),"utf8")),
  localStorage:{getItem(){throw Error("blocked");},setItem(){throw Error("blocked");}},
  document:{documentElement:{lang:"en",dataset:{}},body:{},title:"",
    createTreeWalker(){return {nextNode(){return false;}};},
    querySelectorAll(){return [];},getElementById:element},
  NodeFilter:{SHOW_TEXT:4}
});
vm.runInContext(fs.readFileSync(path.join(web,"preferences.js"),"utf8"),context);
vm.runInContext(fs.readFileSync(path.join(web,"i18n.js"),"utf8"),context);
assert.equal(context.document.documentElement.lang,"en");
assert.equal(context.document.documentElement.dataset.theme,"light");
assert.equal(vm.runInContext('t("Game table")',context),"Game table");
vm.runInContext('language="hr"',context);
assert.equal(vm.runInContext('t("Game table")',context),"Stol za igru");
assert.equal(vm.runInContext('t("No card selected.")',context),"Nijedna karta nije odabrana.");
assert.equal(vm.runInContext('t("Player 2 has no melds")',context),"Igrač 2 nema zvanja");
assert.equal(vm.runInContext('l`Player ${2} revealed ${"My match"}`',context),"Igrač 2 pokazao My match");
assert.equal(vm.runInContext('t("phase-badge")',context),"phase-badge");
context.document.documentElement.dataset.theme="dark";
vm.runInContext('updateThemeButton()',context);
assert.equal(element("theme-toggle").textContent,"Dnevni način");
console.log("Web localization and preference checks passed.");
