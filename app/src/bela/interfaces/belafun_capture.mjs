"use strict";

// Browser-independent capture orchestration. Supply a read-only DOM reader
// through the authorized browser controller. This module never clicks cards.
async function capturePractice(readSnapshot, writeCapture, options = {}) {
  const {maxReads = 240, stopAfterDeal = false, remainingHandSize, minStableMs = 80} = options;
  if (!Number.isInteger(maxReads) || maxReads < 1 || maxReads > 1000) {
    throw new Error("maxReads must be between 1 and 1000");
  }
  const snapshots = [];
  const warnings = [];
  const stableTricks = [];
  let previous = null, stableCount = 0, stableSince = Date.now(), fullSeen = false, reason = "capture_limit";
  for (let i = 0; i < maxReads; i++) {
    let snapshot;
    try { snapshot = await readSnapshot(); }
    catch (error) { warnings.push("Browser observation failed; stop and resynchronize."); reason = "read_error"; break; }
    const table = snapshot.faces.filter(f => f.kind === "table").sort((a,b) => a.player-b.player);
    const hand = snapshot.faces.filter(f => f.kind === "hand");
    const signature = JSON.stringify(table.map(f => [f.player, f.card]));
    const same = previous && signature === previous.signature && table.every((f,j) =>
      Math.abs(f.x - previous.table[j].x) < .5 && Math.abs(f.y - previous.table[j].y) < .5);
    stableCount = same ? stableCount + 1 : 1;
    if (!same) stableSince = Date.now();
    const stable = stableCount >= 3 && Date.now() - stableSince >= minStableMs;
    // Keep a frame in memory before doing any disk work. Moving cards can cross
    // seat boundaries: accept a full table only after three stationary frames.
    snapshots.push({snapshot, stable});
    if (stable && table.length === 4 && new Set(table.map(f => f.player)).size === 4 &&
        new Set(table.map(f => f.card)).size === 4) {
      fullSeen = true;
      if (!stableTricks.some(t => t.signature === signature)) stableTricks.push({signature, table});
    }
    previous = {signature, table};
    if (fullSeen && stable && table.length < 4) {
      if (stopAfterDeal && table.length === 0) { reason = "deal_complete"; break; }
      if (!stopAfterDeal && snapshot.status.includes("Your turn") && hand.length === remainingHandSize) {
        reason = "next_turn"; break;
      }
    }
  }
  const result = {reason, snapshots, stableTricks, warnings};
  // Logging failures must not prevent observation while bots are playing.
  // The complete in-memory result is returned even if persistence fails.
  try { await writeCapture(result); }
  catch (error) { warnings.push("Capture file could not be saved; observations remain in memory."); }
  return result;
}

export {capturePractice};
