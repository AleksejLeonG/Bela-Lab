import {capturePractice} from './belafun_capture.mjs';

// Invoke only inside the authorized browser controller. The engine callback
// runs locally; all observations and clicks use the supplied browser tab API.
export class OnlineDeal {
  constructor({tab, read, request, data, report}) {
    Object.assign(this, {tab, read, request, data, report});
  }

  async play() {
    const before = await this.read();
    if (!before.status.includes('Your turn')) throw new Error('Not our turn');
    const info = await this.request(['--inspect']);
    const order = leader => (a,b) => (a.player-leader+4)%4-(b.player-leader+4)%4;
    this.data.visible_hand = before.faces.filter(f=>f.kind==='hand').map(f=>f.card);
    this.data.visible_trick = before.faces.filter(f=>f.kind==='table').sort(order(info.leader))
      .map(f=>({player:f.player,card:f.card}));
    const advice = await this.request();
    const fresh = await this.read();
    const target = fresh.faces.find(f=>f.kind==='hand'&&f.card===advice.card);
    const sameHand = JSON.stringify(fresh.faces.filter(f=>f.kind==='hand').map(f=>f.card).sort()) ===
      JSON.stringify([...this.data.visible_hand].sort());
    if (!target || !sameHand || !fresh.status.includes('Your turn')) throw new Error('Position changed before play');
    await this.tab.click([target.cx,target.cy]);
    this.report.decisions.push({deal:this.report.deals.length+1,card:advice.card,bela:advice.bela,
      samples:advice.analysis.completed_samples,seconds:advice.analysis.elapsed_seconds});
    const cap = await capturePractice(this.read, async()=>{}, {maxReads:1000,
      remainingHandSize:this.data.visible_hand.length-1,stopAfterDeal:this.data.visible_hand.length===1});
    this.report.captures.push({reason:cap.reason,tricks:cap.stableTricks,warnings:cap.warnings});
    const candidate = cap.stableTricks.find(t=>info.trick.every(p=>t.table.some(c=>c.card===p.card&&c.player===p.player))&&
      t.table.some(c=>c.card===advice.card&&c.player===0));
    if (!candidate) throw new Error('No verified full trick captured; stop');
    const ordered = Array.from({length:4},(_,i)=>candidate.table.find(c=>c.player===(info.leader+i)%4));
    for (const p of ordered) {
      const existing = this.data.events.find(e=>e.type==='play'&&e.card===p.card);
      if (existing) {
        if (existing.player!==p.player) throw new Error('Conflicting public owner');
      } else this.data.events.push({type:'play',player:p.player,card:p.card,
        bela:p.player===0&&p.card===advice.card?advice.bela:false});
    }
    const after = await this.request(['--inspect']);
    if (after.completed_tricks===8) {
      this.report.deals.push({setup:this.data.setup,events:[...this.data.events],score:after.score});
      return {deal_finished:true,score:after.score,tricks:after.trick_counts,card:advice.card};
    }
    let last = cap.snapshots.at(-1).snapshot;
    const expected = (4-after.leader)%4;
    const isNext = snapshot => snapshot.status.includes('Your turn') &&
      snapshot.faces.filter(f=>f.kind==='table').length===expected &&
      snapshot.faces.filter(f=>f.kind==='table').every(f=>
        !this.data.events.some(e=>e.type==='play'&&e.card===f.card));
    // "Your turn" can linger while a collected trick disappears. Wait for
    // exactly the public cards required before seat 0's actual next turn.
    for(let i=0;!isNext(last)&&i<1000;i++) last=await this.read();
    if (!isNext(last)) throw new Error('No verified next-turn prefix');
    const partial = last.faces.filter(f=>f.kind==='table').sort(order(after.leader));
    for (const p of partial) this.data.events.push({type:'play',player:p.player,card:p.card,bela:false});
    this.data.visible_hand = last.faces.filter(f=>f.kind==='hand').map(f=>f.card);
    this.data.visible_trick = partial.map(f=>({player:f.player,card:f.card}));
    const ready = await this.request(['--inspect']);
    if (ready.next_player!==0) throw new Error('Recorded turn is not ours');
    return {card:advice.card,tricks:after.completed_tricks,reason:cap.reason,next_trick:this.data.visible_trick};
  }
}
