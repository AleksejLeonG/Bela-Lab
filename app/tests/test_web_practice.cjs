"use strict";
const assert = require("node:assert/strict");
let capturePractice;
const table = [0,1,2,3].map(player => ({kind:"table",player,card:["C_J","C_8","C_7","C_Q"][player],x:player*20,y:100}));
const full = {status:["Prika's turn"], faces:table};
const next = {status:["Your turn"],faces:[{kind:"hand",card:"H_A"}]};
async function run(frames, write, options={}) {
  let i=0;
  return capturePractice(async()=>frames[Math.min(i++,frames.length-1)],write,{maxReads:20,remainingHandSize:1,minStableMs:0,...options});
}
(async()=>{
  ({capturePractice} = await import("../src/bela/interfaces/belafun_capture.mjs"));
  // Even a failed disk write preserves the complete captured public trick.
  const failure = await run([full,full,full,next,next,next],async()=>{throw new Error("disk unavailable");});
  assert.equal(failure.reason,"next_turn");
  assert.equal(failure.stableTricks.length,1);
  assert.equal(failure.warnings.length,1);
  assert.ok(failure.snapshots.length>=6);
  // Moving cards and duplicate seat assignments must not become a settled trick.
  const moving = {status:full.status,faces:table.map(f=>({...f,player:2}))};
  const rejected = await run([moving,moving,moving,next,next,next],async()=>{});
  assert.equal(rejected.reason,"capture_limit");
  assert.equal(rejected.stableTricks.length,0);
  const changing = await run([full,{...full,faces:table.map(f=>({...f,x:f.x+20}))},next,next,next],async()=>{});
  assert.equal(changing.stableTricks.length,0);
  // Last-deal observation terminates without issuing another game action.
  const finished = await run([full,full,full,{status:[],faces:[]},{status:[],faces:[]},{status:[],faces:[]}],async()=>{}, {stopAfterDeal:true});
  assert.equal(finished.reason,"deal_complete");
  let saved;
  const broken = await capturePractice(async()=>{throw new Error("browser lost");},async v=>{saved=v;});
  assert.equal(broken.reason,"read_error");
  assert.equal(saved.snapshots.length,0);
  console.log("Practice capture checks passed.");
})().catch(error=>{console.error(error);process.exitCode=1;});
