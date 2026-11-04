// Run against the local guest demo. A real secondary click includes the
// pointer-up that can immediately dismiss a newly opened browser popover.
import assert from 'node:assert/strict';
import test from 'node:test';
import { chromium } from 'playwright';

test('community actions survive a right-click and dismiss with Escape or an outside click', async () => {
	const browser = await chromium.launch();
	try {
		const page = await browser.newPage();
		await page.goto('http://localhost:7500/communities');
		const community = page.locator('.community-card').first();
		const actions = page.getByRole('group', { name: 'Community actions' });
		await community.click({ button: 'right' });
		await actions.getByRole('button', { name: 'Open community' }).waitFor();
		await page.keyboard.press('Escape');
		await actions.waitFor({ state: 'hidden' });
		assert.ok(await community.evaluate((element) => element === document.activeElement));
		await community.click({ button: 'right' });
		await actions.waitFor();
		await page.getByRole('heading', { level: 1 }).click();
		await actions.waitFor({ state: 'hidden' });
	} finally {
		await browser.close();
	}
});
