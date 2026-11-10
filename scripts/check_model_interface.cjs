const { chromium } = require(process.env.BIOGEN_PLAYWRIGHT || 'playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const p = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
    await p.goto('http://127.0.0.1:8765', { waitUntil: 'networkidle' });
    await p.locator('.case-item').first().click();
    await p.locator('[data-step="1"]').click();
    await p.locator('#predictButton').click();
    await p.waitForFunction(() => document.querySelectorAll('.prediction-row').length === 3 && !document.body.classList.contains('busy'));
    const predictions = await p.locator('.predictions').innerText();
    assert(predictions.includes('Ocimum tenuiflorum'));
    console.log(predictions);
    await p.evaluate(() => scrollTo(0, 0));
    await p.screenshot({ path: 'docs/identification-preview.png', fullPage: true });
    const id = await p.locator('.case-item.active').getAttribute('data-case');
    await p.goto(`http://127.0.0.1:8765/api/cases/${id}/report`);
    assert.equal(await p.locator('h1').innerText(), 'BIO-GEN research case');
    assert(await p.getByText('Download full case and history (JSON)').count());
    await p.goto(`http://127.0.0.1:8765/?case=${id}`, { waitUntil: 'networkidle' });
    await p.locator('.compound').first().waitFor();
    await p.evaluate(() => scrollTo(0, 0));
    await p.screenshot({ path: 'docs/BIO-GEN-preview.png', fullPage: true });
    fs.writeFileSync('docs/model-interface-verification.json', JSON.stringify({ passed: true, case_id: id, actual_prediction_text: predictions, report_checked: true, bookmarked_case_checked: true }, null, 2));
    console.log('Model inference, report and bookmarked case verified.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exit(1); });
