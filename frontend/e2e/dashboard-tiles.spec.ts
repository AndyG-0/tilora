// Regression coverage for edit-mode tile drag-to-rearrange, resize, and
// delete. Runs under both the `desktop-chromium` (mouse) and `mobile-safari`
// (touch) projects — the latter exists specifically to catch the class of
// bug this suite was written for: a tile that "bounces back" to its start
// position when dragged or resized on an iPhone, even though the same
// gesture works fine with a mouse. Every assertion is relative to whatever
// state the fixture is already in, so the two projects (which share one
// backend/db — see playwright.config.ts) don't depend on run order or on
// being the very first test to touch a given tile.
import { test, expect, type Locator, type Page } from '@playwright/test';

// Dispatches synthetic PointerEvents rather than driving page.mouse or real
// TouchEvents. Two things forced this: the app's drag/resize code listens
// exclusively to Pointer Events (never raw Touch Events), and — confirmed by
// tracing this app under mobile-safari — WebKit only synthesizes
// PointerEvents from *trusted* native touch input, never from a
// JS-dispatched TouchEvent, so `element.dispatchEvent('touchstart', ...)`
// (Playwright's own documented pattern at playwright.dev/docs/touch-events)
// silently never reaches onCellPointerDown/onCellPointerMove at all.
// Dispatching `pointerdown`/`pointermove`/`pointerup` directly, with
// `pointerType` set explicitly, does reach the app's real handlers in both
// engines. The tradeoff: these events are untrusted at the dispatch level,
// so this can't exercise WebKit's native gesture-recognition/pointercancel
// behavior (e.g. the touch system preempting a drag for a scroll) — only
// Playwright's public API has no way to produce trusted multi-step touch
// input. This suite therefore catches pointerType-conditional app-logic bugs
// but not native-gesture-cancellation bugs; see CONTRIBUTING.md.
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
		await page.getByLabel('Rearrange widgets').click();
	});

	test.afterEach(async ({ page }) => {
		const doneButton = page.getByLabel('Done rearranging');
		if (await doneButton.isVisible().catch(() => false)) await doneButton.click();
	});

	test('drag-to-rearrange swaps two tiles and persists', async ({ page }) => {
		const clock = page.locator('[data-widget-id="clock"]');
		const date = page.locator('[data-widget-id="date"]');
		const clockBefore = await clock.boundingBox();
		const dateBefore = await date.boundingBox();
		if (!clockBefore || !dateBefore) throw new Error('tiles not laid out');

		await dragGesture(page, clock, dateBefore.x - clockBefore.x, dateBefore.y - clockBefore.y);

		// Clock should now sit where date used to be — not just visually (a
		// leftover drag transform could fake that), but as the tile's real
		// grid position, which only a successful PUT /api/widgets/layout
		// followed by a re-render produces.
		await expect.poll(async () => (await clock.boundingBox())?.x).toBe(dateBefore.x);
		await expect.poll(async () => (await clock.boundingBox())?.y).toBe(dateBefore.y);

		await page.reload();
		await expect(clock).toBeVisible();
		// Re-enter edit mode before measuring: at the narrow breakpoint `.grid`'s
		// rows are `minmax(12rem, auto)` inside a `min-height: 100vh` container,
		// so leftover space stretches into each row (ordinary CSS Grid
		// `align-content: normal` behavior) — and edit mode adds its own "+ Add
		// widget" tile as a real 4th grid row, which eats that leftover space
		// and shrinks every row from ~200px back to the 12rem floor. `dateBefore`
		// above was captured while already in edit mode (see beforeEach), so
		// comparing against a post-reload measurement taken outside edit mode
		// would be comparing two different row heights, not a broken swap.
		await page.getByLabel('Rearrange widgets').click();
		const clockAfterReload = await clock.boundingBox();
		expect(clockAfterReload?.x).toBe(dateBefore.x);
		expect(clockAfterReload?.y).toBe(dateBefore.y);
	});

	test('resizing a tile grows it and persists', async ({ page }) => {
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

	test('deleting a tile removes it and it stays removed after reload', async ({ page }) => {
		// Adds a throwaway tile rather than deleting one of the fixture's
		// three, so this test stays repeatable across both projects without
		// depleting the fixture the other tests rely on. Widget order isn't
		// DOM-append order (it's not guaranteed to put the new tile last), so
		// the added tile is found by id-set difference, not `.last()`.
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
});
