import { test, expect, type Page } from '@playwright/test';

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

test.describe('auth and setup flows', () => {
	test('unauthenticated user visiting dashboard is redirected to /login', async ({ browser }) => {
		const context = await browser.newContext({ storageState: undefined });
		const page = await context.newPage();

		await page.goto('/');
		await dismissDeviceModal(page);
		await expect(page).toHaveURL(/\/login$/);
		await expect(page.getByRole('heading', { name: /who's watching\?/i, level: 1 })).toBeVisible();

		await context.close();
	});

	test('first-run setup page validates input and submits admin creation', async ({ browser }) => {
		const context = await browser.newContext({ storageState: undefined });
		const page = await context.newPage();

		// Mock setup status as needs_setup: true
		await page.route('**/api/setup/status', (route) => {
			route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ needs_setup: true }),
			});
		});

		await page.route('**/api/setup/admin', (route) => {
			route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ id: 'new-admin-id', name: 'Admin User', role: 'admin' }),
			});
		});

		await page.route('**/api/users/me', (route) => {
			route.fulfill({
				status: 200,
				contentType: 'application/json',
				body: JSON.stringify({ id: 'new-admin-id', name: 'Admin User', role: 'admin' }),
			});
		});

		await page.goto('/setup');
		await dismissDeviceModal(page);
		await expect(page.getByRole('heading', { name: /welcome to tilora/i, level: 1 })).toBeVisible();

		const nameInput = page.getByPlaceholder('Alice');
		const pinInput = page.getByPlaceholder(/4.*8 digits/i);
		const createButton = page.locator('.confirm-button');

		// Button disabled without name
		await expect(createButton).toBeDisabled();

		// Invalid short PIN shows error
		await nameInput.fill('Admin User');
		await pinInput.fill('12');
		await dismissDeviceModal(page);
		await createButton.click();
		await expect(page.locator('.hint.error')).toBeVisible();

		// Valid PIN allows creation
		await pinInput.fill('5678');
		await dismissDeviceModal(page);
		await createButton.click();
		await expect(page).toHaveURL(/\/(login)?$/);

		await context.close();
	});

	test('login page supports PIN pad entry, error handling, profile creation, and PIN-less login', async ({
		browser,
	}) => {
		const testUserName = `TestUser_${Date.now()}`;
		const testUserPin = '7890';

		const context = await browser.newContext({ storageState: undefined });
		const page = await context.newPage();

		await page.goto('/login');
		await dismissDeviceModal(page);
		await expect(page.getByRole('heading', { name: /who's watching\?/i, level: 1 })).toBeVisible();

		// 1. Create a new user with PIN from the login screen
		await dismissDeviceModal(page);
		await page.getByRole('button', { name: /add profile/i }).click();
		await expect(page.locator('.add-form')).toBeVisible();

		await page.getByLabel('Name').fill(testUserName);
		await page.getByLabel('PIN').fill(testUserPin);
		await page.getByRole('button', { name: /^create$/i }).click();

		// Successfully logged in after creation
		await dismissDeviceModal(page);
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('.top-bar')).toBeVisible();

		// 2. Log out
		const profileButton = page.locator('.profile-menu-wrap .icon-button');
		await profileButton.click();
		await page.getByRole('button', { name: /log out|cerrar sesión/i }).click();
		await expect(page).toHaveURL(/\/login$/);

		// 3. Select the PIN-protected profile
		await dismissDeviceModal(page);
		const userProfileButton = page.getByRole('button', { name: new RegExp(testUserName, 'i') });
		await expect(userProfileButton).toBeVisible();
		await userProfileButton.click();

		// PIN Pad is shown
		const pinPad = page.locator('.pin-pad');
		await expect(pinPad).toBeVisible();

		// 4. Enter wrong PIN and verify error
		for (const digit of ['1', '2', '3', '4']) {
			await pinPad.getByRole('button', { name: digit, exact: true }).click();
		}
		await pinPad.getByLabel('Submit PIN').click();
		await expect(page.locator('.hint.error')).toHaveText(/incorrect pin/i);

		// 5. Enter correct PIN
		for (const digit of ['7', '8', '9', '0']) {
			await pinPad.getByRole('button', { name: digit, exact: true }).click();
		}
		await pinPad.getByLabel('Submit PIN').click();

		// Successfully logged in
		await dismissDeviceModal(page);
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('.top-bar')).toBeVisible();

		// 6. Log out and verify PIN-less profile logs in directly
		await profileButton.click();
		await page.getByRole('button', { name: /log out|cerrar sesión/i }).click();
		await expect(page).toHaveURL(/\/login$/);

		await dismissDeviceModal(page);
		const adminButton = page.getByRole('button', { name: /e2e admin/i });
		await expect(adminButton).toBeVisible();
		await adminButton.click();

		await dismissDeviceModal(page);
		await expect(page).toHaveURL(/\/$/);
		await expect(page.locator('.top-bar')).toBeVisible();

		await context.close();
	});
});
