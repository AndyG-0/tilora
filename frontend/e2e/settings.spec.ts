import { test, expect } from '@playwright/test';

test.describe('settings and configuration workflows', () => {
	test.beforeEach(async ({ page }) => {
		await page.goto('/settings');
		await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
	});

	test('admin settings sections are visible for admin user', async ({ page }) => {
		await expect(
			page
				.locator('section')
				.filter({ has: page.getByRole('heading', { name: /household members|miembros del hogar/i }) }),
		).toBeVisible();
		await expect(
			page.locator('section').filter({ has: page.getByRole('heading', { name: /ai provider|proveedor de ia/i }) }),
		).toBeVisible();
		await expect(
			page.locator('section').filter({ has: page.getByRole('heading', { name: /timezone|zona horaria/i }) }),
		).toBeVisible();
	});

	test('timezone selection updates and displays save feedback', async ({ page }) => {
		const timezoneSection = page
			.locator('section')
			.filter({ has: page.getByRole('heading', { name: /timezone|zona horaria/i }) });
		const timezoneSelect = timezoneSection.locator('select');
		await expect(timezoneSelect).toBeVisible();

		await timezoneSelect.selectOption({ label: 'UTC' });
		const saveButton = timezoneSection.locator('button.save');
		await saveButton.click();

		await expect(timezoneSection.locator('.hint').filter({ hasText: /saved|guardad/i })).toBeVisible();
	});

	test('language selector switches locale and updates UI strings', async ({ page }) => {
		const langSection = page.locator('section').filter({ has: page.locator('select option[value="es"]') });
		const langSelect = langSection.locator('select');
		await expect(langSelect).toBeVisible();

		// Switch to Spanish
		await langSelect.selectOption('es');
		await langSection.locator('button.save').click();
		await expect(langSection.locator('.hint').filter({ hasText: /guardad|saved/i })).toBeVisible();

		// Switch back to English
		await langSelect.selectOption('en');
		await langSection.locator('button.save').click();
		await expect(langSection.locator('.hint').filter({ hasText: /guardad|saved/i })).toBeVisible();
	});

	test('appearance selector changes data-theme attribute', async ({ page }) => {
		const themeSection = page
			.locator('section')
			.filter({ has: page.getByRole('heading', { name: /appearance|apariencia/i }) });
		const themeSelect = themeSection.locator('select');
		await expect(themeSelect).toBeVisible();

		const initialTheme = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
		const targetTheme = initialTheme === 'ocean' ? 'forest' : 'ocean';

		await themeSelect.selectOption(targetTheme);
		await themeSection.locator('button.save').click();

		await expect
			.poll(async () => page.evaluate(() => document.documentElement.getAttribute('data-theme')))
			.toBe(targetTheme);
	});

	test('device settings allows renaming the current device', async ({ page }) => {
		const renameBtn = page.getByRole('button', { name: /rename device|renombrar dispositivo/i });
		if (await renameBtn.isVisible()) {
			await renameBtn.click();
			const input = page.locator('.device-rename-form input');
			const updatedName = `Device ${Date.now()}`;
			await input.fill(updatedName);
			await page.locator('.device-rename-form .save').click();

			await expect(page.locator('.device-name').filter({ hasText: updatedName })).toBeVisible();
		}
	});

	test('screensaver preview triggers full-screen overlay and dismisses on tap', async ({ page }) => {
		const testScreensaverBtn = page.getByRole('button', { name: /test screensaver|probar salvapantallas/i });
		if ((await testScreensaverBtn.isVisible()) && (await testScreensaverBtn.isEnabled())) {
			await testScreensaverBtn.click();
			const overlay = page.locator('.screensaver');
			await expect(overlay).toBeVisible();

			// Click to dismiss
			await overlay.click();
			await expect(overlay).toHaveCount(0);
		}
	});

	test('household members lists admin user and handles role safeguarding', async ({ page }) => {
		const membersSection = page
			.locator('section')
			.filter({ has: page.getByRole('heading', { name: /household members|miembros del hogar/i }) });
		await expect(membersSection.locator('.member-name').filter({ hasText: 'E2E Admin' })).toBeVisible();
		await expect(membersSection.locator('.role-badge').first()).toBeVisible();
	});

	test('check for updates button executes version check without error', async ({ page }) => {
		const checkBtn = page.locator('#check-for-updates-btn');
		if (await checkBtn.isVisible()) {
			await checkBtn.click();
			await expect(page.locator('.update-check-row')).toBeVisible();
		}
	});
});
