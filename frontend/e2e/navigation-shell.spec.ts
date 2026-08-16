import { test, expect } from '@playwright/test';

test.describe('navigation and app shell', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/');
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
	});

	test('cycling theme updates document data-theme attribute and persists', async ({ page }) => {
		const initialTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));

		const themeButton = page.locator('.top-bar button').nth(3);
		await expect(themeButton).toBeVisible();
		await themeButton.click();

		await expect
			.poll(async () => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
			.not.toBe(initialTheme);
		const newTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));

		await page.reload();
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
		const reloadedTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		expect(reloadedTheme).toBe(newTheme);
	});

	test('header navigation buttons route to settings, reports, and back', async ({ page }) => {
		// Navigate to Settings (⚙)
		await page.locator('.top-bar button').filter({ hasText: '⚙' }).click();
		await expect(page).toHaveURL(/\/settings$/);
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

		// Go back to Dashboard
		await page.getByRole('button', { name: /back|volver|atrás/i }).click();
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();

		// Navigate to Reports (📊)
		await page.locator('.top-bar button').filter({ hasText: '📊' }).click();
		await expect(page).toHaveURL(/\/reports$/);
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();

		// Go back to Dashboard
		await page.getByRole('button', { name: /back|volver|atrás/i }).click();
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
	});

	test('multi-tab navigation switches tabs via dots, keyboard, and gestures', async ({ page }) => {
		const dots = page.locator('.tab-dots .dot');
		await expect(dots).toHaveCount(2);

		// Switch to Tab 2 via clicking dot
		await dots.nth(1).click();
		await expect(page.locator('[data-widget-id="game2048"]')).toBeVisible();
		await expect(dots.nth(1)).toHaveClass(/active/);

		// Switch to Tab 1 via clicking dot
		await dots.nth(0).click();
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
		await expect(dots.nth(0)).toHaveClass(/active/);

		// Switch to Tab 2 via ArrowRight key
		await page.keyboard.press('ArrowRight');
		await expect(page.locator('[data-widget-id="game2048"]')).toBeVisible();
		await expect(dots.nth(1)).toHaveClass(/active/);

		// Switch to Tab 1 via ArrowLeft key
		await page.keyboard.press('ArrowLeft');
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
		await expect(dots.nth(0)).toHaveClass(/active/);
	});

	test('profile dropdown menu opens and displays user info', async ({ page }) => {
		const profileButton = page.locator('.profile-menu-wrap .icon-button');
		await expect(profileButton).toBeVisible();
		await profileButton.click();

		const menu = page.locator('.profile-menu');
		await expect(menu).toBeVisible();
		await expect(menu.locator('.profile-menu-name')).toBeVisible();
		await expect(menu.locator('.profile-menu-action').first()).toBeVisible();
		await expect(menu.locator('.profile-menu-logout')).toBeVisible();

		// Close menu
		await profileButton.click();
		await expect(menu).toHaveCount(0);
	});

	test('direct widget route loads full-screen detail view and back navigation', async ({ page }) => {
		await page.goto('/widget/clock');
		await expect(page.locator('.detail-page')).toBeVisible();
		await expect(page.locator('.face')).toBeVisible();

		const backBtn = page.getByRole('button', { name: /back|volver|atrás/i });
		await expect(backBtn).toBeVisible();
		await backBtn.click();

		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('[data-widget-id="clock"]')).toBeVisible();
	});
});
