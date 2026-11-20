// Optional browser regression check against the isolated UI fixture (no card moves).
// BELA_PLAYWRIGHT may point to an installed Playwright module; BELA_BROWSER to Edge/Chromium.
const assert = require('node:assert/strict');
const {chromium} = require(process.env.BELA_PLAYWRIGHT || 'playwright');
const base = process.env.BELA_UI_URL || 'http://127.0.0.1:8778';

(async () => {
  const browser = await chromium.launch({headless:true, ...(process.env.BELA_BROWSER ? {executablePath:process.env.BELA_BROWSER} : {})});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:900}});
    const errors=[];
    page.on('pageerror', error => errors.push(String(error)));
    await page.addInitScript(() => {
      const original=setTimeout;
      window.setTimeout=(fn,ms,...args)=>[650,1600,1400,2300].includes(ms)?0:original(fn,ms,...args);
    });
    const before=await (await page.request.get(base+'/api/state')).json();
    await page.goto(base+'/?desktop=1');
    await page.waitForFunction(()=>appLoaded,{},{timeout:90000});
    async function geometry(view) {
      const size=await page.evaluate(()=>({width:innerWidth,height:innerHeight,scrollWidth:document.documentElement.scrollWidth,scrollHeight:document.documentElement.scrollHeight}));
      assert.ok(size.scrollWidth<=size.width+1, `${view}: horizontal overflow ${JSON.stringify(size)}`);
      if(size.width>1100 && ['play','review'].includes(view))assert.ok(size.scrollHeight<=size.height+1, `${view}: page overflow ${JSON.stringify(size)}`);
      assert.ok(await page.locator('#error-banner').isHidden(), await page.locator('#error-banner').textContent());
    }
    for(const viewport of [{width:1920,height:1080},{width:1440,height:900},{width:1366,height:768},{width:390,height:844}]) {
      await page.setViewportSize(viewport);
      await geometry('play');
    }
    await page.setViewportSize({width:1440,height:900});
    await page.locator('[data-inspector-tab=advice]').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('[data-inspector-tab=scores]').getAttribute('aria-selected'),'true');
    await page.keyboard.press('Control+,');
    assert.ok(await page.locator('label[for=language-select]').isVisible());
    await page.locator('#language-select').selectOption('hr');
    await page.locator('#card-style-select').selectOption('standard');
    await page.locator('#card-style-select').selectOption('hungarian');
    await page.locator('#language-select').selectOption('en');
    await page.locator('#theme-toggle').click();
    await page.keyboard.press('Escape');
    await page.keyboard.press('Control+3');
    await geometry('library');
    if(await page.locator('[data-review-match]').count()) {
      await page.locator('[data-review-match]').first().click();
      await page.locator('#review-deal').waitFor({timeout:90000});
      for(const viewport of [{width:1440,height:900},{width:1366,height:768},{width:390,height:844}]) {
        await page.setViewportSize(viewport);
        await geometry('review');
      }
    }
    await page.keyboard.press('Control+1');
    await page.locator('.app-tools-toggle').click();
    await page.locator('#app-settings-open').click();
    assert.ok(await page.locator('#app-settings').isVisible());
    await page.keyboard.press('Escape');
    const after=await (await page.request.get(base+'/api/state')).json();
    assert.equal(before.match?.id,after.match?.id);
    assert.equal(before.match?.revision,after.match?.revision);
    assert.equal(before.bot?.id,after.bot?.id);
    assert.equal(before.bot?.revision,after.bot?.revision);
    assert.deepEqual(errors,[]);
    console.log('PASS workspaces, viewport fit, keyboard tabs, preferences, mobile menus and unchanged game state.');
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
