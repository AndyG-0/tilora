import { test, expect, type Page } from '@playwright/test';
import { BACKEND_URL } from './env';

async function dismissDeviceModal(page: Page) {
	const modal = page.locator('.device-modal');
	if (await modal.isVisible({ timeout: 2500 }).catch(() => false)) {
		await modal.locator('button.confirm').click();
		await page
			.locator('.device-modal-backdrop')
			.waitFor({ state: 'detached', timeout: 2500 })
			.catch(() => {});
	}
}

test.describe('reports page', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/reports');
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
	});

	test('renders reports title, summary metrics, and tile cards', async ({ page }) => {
		await expect(page.locator('.report-header')).toBeVisible();

		// Summary stats grid and metric cards
		const summaryGrid = page.locator('.summary-grid');
		await expect(summaryGrid).toBeVisible();
		await expect(summaryGrid.locator('.metric-card').first()).toBeVisible();

		// Tile cards
		const tileCards = page.locator('article.tile-row-card');
		await expect(tileCards.first()).toBeVisible();
	});

	test('search input filters tile cards in report', async ({ page }) => {
		const searchInput = page.locator('.search-input-wrapper input');
		await expect(searchInput).toBeVisible();

		await searchInput.fill('Clock');
		const filteredCards = page.locator('article.tile-row-card');
		await expect(filteredCards.first().locator('.tile-name')).toContainText(/clock/i);
	});

	test('back button returns to dashboard', async ({ page }) => {
		const backBtn = page.locator('.back-button');
		await expect(backBtn).toBeVisible();
		await backBtn.click();

		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
	});

	test('admin can add a tile from the report page', async ({ page }) => {
		await page.getByLabel('Add Tile').click();
		const dialog = page.getByRole('dialog');
		await expect(dialog).toBeVisible();

		await dialog.getByLabel('Tile Type').selectOption('rss');
		await dialog.getByLabel('Tab').selectOption('home');
		await dialog.getByRole('button', { name: 'Add Tile' }).click();
		await expect(dialog).toHaveCount(0);

		await page.locator('.search-input-wrapper input').fill('RSS');
		const newCard = page.locator('article.tile-row-card').first();
		await expect(newCard).toBeVisible();

		// Clean up so this test stays order-independent.
		await newCard.getByRole('button', { name: /Delete/ }).click();
		await page.getByRole('button', { name: 'Delete Tile' }).click();
		await expect(newCard).toHaveCount(0);
	});

	test('admin assigns a tile to another member, force-deletes it, and the member only sees their own scoped tiles', async ({
		page,
		browser,
	}) => {
		// 1. Create a plain household member via a separate, unauthenticated
		// browser context (the standard profile-creation UI flow — see
		// auth-and-setup.spec.ts) so the admin session driving `page` is
		// untouched.
		const memberName = `E2E Member ${Date.now()}`;
		const memberContext = await browser.newContext({ storageState: undefined });
		const memberPage = await memberContext.newPage();
		await memberPage.goto('/login');
		await dismissDeviceModal(memberPage);
		await expect(memberPage.getByRole('heading', { name: /who's watching\?/i, level: 1 })).toBeVisible();
		await dismissDeviceModal(memberPage);
		await memberPage.getByRole('button', { name: /add profile/i }).click();
		await memberPage.getByLabel('Name').fill(memberName);
		await dismissDeviceModal(memberPage);
		await memberPage.getByRole('button', { name: /^create$/i }).click();
		await dismissDeviceModal(memberPage);
		await expect(memberPage).toHaveURL(/\/$/);

		// Reload as admin so the add-tile modal's "Assign To" list picks up
		// the just-created member (household users are fetched on mount).
		await page.goto('/reports');
		await page.getByLabel('Add Tile').click();
		const dialog = page.getByRole('dialog');
		await dialog.getByLabel('Tile Type').selectOption('rss');
		await dialog.getByLabel('Tab').selectOption('home');
		await dialog.getByLabel('Assign To').selectOption({ label: memberName });
		await dialog.getByRole('button', { name: 'Add Tile' }).click();
		await expect(dialog).toHaveCount(0);

		// 2. Admin sees the assigned tile, attributed to the member.
		await page.locator('.search-input-wrapper input').fill(memberName);
		const assignedCard = page.locator('article.tile-row-card').first();
		await expect(assignedCard).toBeVisible();
		await expect(assignedCard).toContainText(memberName);
		const tileId = (await assignedCard.locator('.id-item code').textContent())?.trim();
		expect(tileId).toBeTruthy();

		// 3. The admin-only owner filter narrows the list to just that member.
		await page.locator('.search-input-wrapper input').fill('');
		await page.getByLabel('Filter by user').selectOption({ label: memberName });
		await expect(page.locator('article.tile-row-card')).toHaveCount(1);
		await expect(page.locator('article.tile-row-card').first()).toContainText(memberName);
		await page.getByLabel('Filter by user').selectOption('all');

		// 4. The member's own report view has no admin controls and shows
		// their assigned tile plus shared/unowned builtins, nothing else.
		await memberPage.goto('/reports');
		await expect(memberPage.getByRole('heading', { level: 1 })).toBeVisible();
		await expect(memberPage.getByLabel('Add Tile')).toHaveCount(0);
		await expect(memberPage.getByLabel('Filter by user')).toHaveCount(0);
		await expect(memberPage.locator(`article.tile-row-card:has(code:text-is("${tileId}"))`)).toBeVisible();
		await expect(memberPage.locator('[data-widget-id="clock"]')).toHaveCount(0); // sanity: not the dashboard grid
		await memberContext.close();

		// 5. Admin force-deletes the member-owned custom tile — a hard delete,
		// not a per-device hide — verified via a follow-up API check.
		await page.locator('.search-input-wrapper input').fill(memberName);
		const cardToDelete = page.locator('article.tile-row-card').first();
		await cardToDelete.getByRole('button', { name: /Delete/ }).click();
		await page.getByRole('button', { name: 'Delete Tile' }).click();
		await expect(cardToDelete).toHaveCount(0);

		const res = await page.request.get(`${BACKEND_URL}/api/reports/tiles`);
		const body = await res.json();
		expect(body.tiles.some((t: { id: string }) => t.id === tileId)).toBe(false);
	});
});
