// Read-only DOM probe. Invoke through an authorized browser controller.
// Reads rendered card faces only; never accesses app stores or game sockets.
() => {
  if (location.origin !== "https://bela.fun" || location.pathname !== "/home/game") {
    throw new Error("Expected the Bela.fun game page.");
  }
  const faces = [];
  const exposed = el => {
    for (let p = el; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if ((s.opacity !== "" && Number(s.opacity) === 0) || s.visibility === "hidden" || s.display === "none") return false;
      const matrix = /^(?:matrix3d|matrix)\(([^,]+)/.exec(s.transform);
      if (s.backfaceVisibility === "hidden" && matrix && Number(matrix[1]) < .99) return false;
    }
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.left >= 0 && r.top >= 0 &&
      r.right <= innerWidth && r.bottom <= innerHeight;
  };
  for (const el of document.querySelectorAll('img[src*="/decks/"]')) {
    const card = /\/([CHSD]_(?:7|8|9|10|J|Q|K|A))\./.exec(el.getAttribute("src") || "")?.[1];
    if (!card || !exposed(el)) continue;
    const r = el.getBoundingClientRect();
    let rotatingFace = false;
    for (let p=el.parentElement; p; p=p.parentElement) {
      if (p.style.backfaceVisibility === "hidden") rotatingFace = true;
    }
    const hand = el.closest(".cursor-pointer") || rotatingFace;
    const position = el.parentElement?.parentElement;
    if (hand) {
      faces.push({kind: "hand", card, x:r.x, y:r.y, cx:r.x+r.width/2, cy:r.y+r.height/2});
    } else if (position?.style.left === "50%" && position?.style.top === "50%") {
      const frame = position.parentElement.getBoundingClientRect();
      const dx = r.x+r.width/2-(frame.x+frame.width/2);
      const dy = r.y+r.height/2-(frame.y+frame.height/2);
      const player = Math.abs(dx)>Math.abs(dy) ? (dx>0?1:3) : (dy>0?0:2);
      faces.push({kind:"table", player, card, x:r.x, y:r.y});
    } else {
      const context=[];
      for(let p=el.parentElement,i=0;p&&i<7;p=p.parentElement,i++) {
        const text=(p.innerText||'').trim();if(text&&text.length<240)context.push(text);
      }
      faces.push({kind:"reveal",card,x:r.x,y:r.y,context});
    }
  }
  const status = document.body.innerText.split("\n").map(t=>t.trim())
    .filter(t=>/^(Your turn|You must call trump|Call trump or pass|.*'s turn|.*is deciding|Counting your declarations)/.test(t));
  const visibleAsset = el => exposed(el) || (Array.from(el.parentElement.children).some(child=>
    child.style.backgroundImage?.includes(el.getAttribute('src')) && exposed(child)));
  const bots = Array.from(document.querySelectorAll('img[alt="Bot"]')).filter(visibleAsset).map(el=>{
    const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};
  });
  const marks = Array.from(document.querySelectorAll('*')).filter(el=>el.children.length===0&&
    el.textContent.trim()==='D'&&exposed(el)).map(el=>{const r=el.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};});
  const suits = Array.from(document.querySelectorAll('img[src*="/suits/"]')).filter(visibleAsset).map(el=>{
    const r=el.getBoundingClientRect();return {src:el.getAttribute('src'),x:r.x+r.width/2,y:r.y+r.height/2,width:r.width};
  });
  return {url:location.href, status, faces, bots, marks, suits, text:document.body.innerText};
}
