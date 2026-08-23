// Regression coverage for edit-mode tile drag-to-rearrange, resize,
// add, delete, and widget renaming. Runs under both the `desktop-chromium` (mouse)
// and `mobile-safari` (touch) projects.
import { test, expect, type Locator, type Page } from '@playwright/test';

// Dispatches synthetic PointerEvents rather than driving page.mouse or real
// TouchEvents. See CONTRIBUTING.md.
async function dragGesture(page: Page, from: Locator, deltaX: number, deltaY: number, steps = 12) {
	const pointerType = (await page.evaluate(() => 'ontouchstart' in window)) ? 'touch' : 'mouse';
	const box = await from.boundingBox();
	if (!box) throw new Error('drag source has no bounding box');
	const startX = box.x + box.width / 2;
	const startY = box.y + box.height / 2;

	const opts = (x: number, y: number) => ({
		pointerId: 1,
		pointerType,
		isPrimary: true,
		bubbles: true,
		cancelable: true,
		clientX: x,
		clientY: y,
	});

	await from.dispatchEvent('pointerdown', opts(startX, startY));
	for (let i = 1; i <= steps; i++) {
		const x = startX + (deltaX * i) / steps;
		const y = startY + (deltaY * i) / steps;
		await page.dispatchEvent('body', 'pointermove', opts(x, y));
		await page.waitForTimeout(20);
	}
	await page.dispatchEvent('body', 'pointerup', opts(startX + deltaX, startY + deltaY));
}

test.describe('dashboard tile editing', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
	});

	test.afterEach(async ({ page }) => {
		const doneButton = page.getByLabel('Done rearranging');
		if (await doneButton.isVisible().catch(() => false)) await doneButton.click();
	});

	test('drag-to-rearrange swaps two tiles and persists', async ({ page }) => {
		await page.getByLabel('Rearrange tiles').click();
		const clock = page.locator('[data-widget-id="clock"]');
		const date = page.locator('[data-widget-id="date"]');
		const clockBefore = await clock.boundingBox();
		const dateBefore = await date.boundingBox();
		if (!clockBefore || !dateBefore) throw new Error('tiles not laid out');

		await dragGesture(page, clock, dateBefore.x - clockBefore.x, dateBefore.y - clockBefore.y);

		await expect.poll(async () => (await clock.boundingBox())?.x).toBe(dateBefore.x);
		await expect.poll(async () => (await clock.boundingBox())?.y).toBe(dateBefore.y);

		await page.reload();
		await expect(clock).toBeVisible();
		await page.getByLabel('Rearrange tiles').click();
		const clockAfterReload = await clock.boundingBox();
		expect(clockAfterReload?.x).toBe(dateBefore.x);
		expect(clockAfterReload?.y).toBe(dateBefore.y);
	});

	test('resizing a tile grows it and persists', async ({ page }) => {
		await page.getByLabel('Rearrange tiles').click();
		const message = page.locator('[data-widget-id="message"]');
		const before = await message.boundingBox();
		if (!before) throw new Error('message tile not laid out');

		const handle = message.locator('.resize-handle');
		await dragGesture(page, handle, 0, 150);

		await expect.poll(async () => (await message.boundingBox())?.height).toBeGreaterThan(before.height);
		const grownHeight = (await message.boundingBox())!.height;

		await page.reload();
		await expect(message).toBeVisible();
		const afterReload = await message.boundingBox();
		expect(afterReload?.height).toBeCloseTo(grownHeight, 0);
	});

	test('resizing a tile into an occupied region pushes the sibling down and persists', async ({ page }) => {
		await page.getByLabel('Rearrange tiles').click();
		// clock (col1,row1) sits directly above message (col1-2,row2) in the
		// fixture — growing clock's rowSpan by one row lands it on message.
		const clock = page.locator('[data-widget-id="clock"]');
		const message = page.locator('[data-widget-id="message"]');
		const messageBefore = await message.boundingBox();
		if (!messageBefore) throw new Error('message tile not laid out');

		const handle = clock.locator('.resize-handle');
		await dragGesture(page, handle, 0, 150);

		await expect.poll(async () => (await message.boundingBox())?.y).toBeGreaterThan(messageBefore.y);
		const clockAfterDrag = await clock.boundingBox();
		const messageAfterDrag = await message.boundingBox();
		expect(messageAfterDrag!.y).toBeGreaterThanOrEqual(clockAfterDrag!.y + clockAfterDrag!.height);

		await page.reload();
		await expect(clock).toBeVisible();
		const messageAfterReload = await message.boundingBox();
		expect(messageAfterReload?.y).toBeCloseTo(messageAfterDrag!.y, 0);
	});

	test('adding a widget opens picker and places new tile on dashboard', async ({ page }) => {
		await page.getByLabel('Rearrange tiles').click();
		const countBefore = await page.locator('[data-widget-id]').count();

		await page.getByRole('button', { name: '+ Add widget' }).click();
		await expect(page.locator('.widget-picker')).toBeVisible();

		// Add a date widget
		await page.getByRole('button', { name: 'Date', exact: true }).click();
		await expect.poll(() => page.locator('[data-widget-id]').count()).toBe(countBefore + 1);

		// Find the newly added tile and clean it up
		const ids = await page
			.locator('[data-widget-id]')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-widget-id')));
		const newId = ids.find((id) => id?.startsWith('date-'));
		if (newId) {
			const addedLocator = page.locator(`[data-widget-id="${newId}"]`);
			await addedLocator.locator('.remove-button').click();
			await expect(addedLocator).toHaveCount(0);
		}
	});

	test('deleting a tile removes it and it stays removed after reload', async ({ page }) => {
		await page.getByLabel('Rearrange tiles').click();
		const idsBefore = await page
			.locator('[data-widget-id]')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-widget-id')));

		await page.getByRole('button', { name: '+ Add widget' }).click();
		await page.getByRole('button', { name: 'Clock', exact: true }).click();

		await expect.poll(() => page.locator('[data-widget-id]').count()).toBe(idsBefore.length + 1);
		const idsAfter = await page
			.locator('[data-widget-id]')
			.evaluateAll((els) => els.map((el) => el.getAttribute('data-widget-id')));
		const addedId = idsAfter.find((id) => !idsBefore.includes(id));
		if (!addedId) throw new Error('add widget did not create a new tile');
		const addedLocator = page.locator(`[data-widget-id="${addedId}"]`);

		await addedLocator.locator('.remove-button').click();
		await expect(addedLocator).toHaveCount(0);

		await page.reload();
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
		await expect(addedLocator).toHaveCount(0);
	});

	test('renaming a widget updates its title', async ({ page }) => {
		await page.goto('/widget/message');
		await expect(page.locator('.tile-name h1')).toBeVisible();

		const renameBtn = page.locator('button.rename-link');
		if (await renameBtn.isVisible()) {
			await renameBtn.click();
			const input = page.locator('.rename-form input');
			await input.fill('Renamed Note');
			await page.locator('.rename-form button.save').click();
			await expect(page.locator('.tile-name h1')).toHaveText('Renamed Note');

			// Restore name
			await renameBtn.click();
			await input.fill('E2E');
			await page.locator('.rename-form button.save').click();
		}
	});
});
