import { test, expect } from '@playwright/test';

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
});
