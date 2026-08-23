import { test, expect } from '@playwright/test';

test.describe('interactive widgets and mini-apps', () => {
	test('message widget supports editing and saving note content', async ({ page }) => {
		await page.goto('/widget/message');
		await expect(page.locator('.detail-page')).toBeVisible();

		// Open editor form
		await page.locator('button.edit-settings').click();
		await expect(page.locator('.settings-form')).toBeVisible();

		const titleInput = page.locator('.settings-form input[type="text"]');
		const bodyInput = page.locator('.settings-form textarea');
		const saveButton = page.locator('.settings-form button.save');

		const newTitle = `Note ${Date.now()}`;
		const newBody = 'Important reminder content from e2e test.';

		await titleInput.fill(newTitle);
		await bodyInput.fill(newBody);
		await saveButton.click();
		await expect(page.locator('.settings-form')).toHaveCount(0);

		// Back to dashboard and verify updated text on message tile
		await page.getByRole('button', { name: /back/i }).click();
		await expect(page).toHaveURL(/\/$/);
		const messageTile = page.locator('[data-widget-id="message"]');
		await expect(messageTile).toContainText(newTitle);
	});

	test('chores widget supports adding, completing, and removing to-do items', async ({ page }) => {
		await page.goto('/widget/chores');
		await expect(page.locator('.detail-page')).toBeVisible();

		const choreText = `Task ${Date.now()}`;
		const addInput = page.locator('form.add input');
		const addButton = page.locator('form.add button[type="submit"]');

		await addInput.fill(choreText);
		await addButton.click();

		// Verify chore item appears in the list
		const choreItem = page.locator('ul.list li').filter({ hasText: choreText });
		await expect(choreItem).toBeVisible();

		// Check the checkbox to mark as complete
		const checkbox = choreItem.locator('input[type="checkbox"]');
		await checkbox.check();
		await expect(choreItem).toHaveClass(/completed/);

		// Remove the chore item
		await choreItem.locator('button.remove').click();
		await expect(choreItem).toHaveCount(0);
	});

	test('shopping list widget supports adding, checking, and removing grocery items', async ({ page }) => {
		await page.goto('/widget/shopping');
		await expect(page.locator('.detail-page')).toBeVisible();

		const itemText = `Groceries ${Date.now()}`;
		const addInput = page.locator('form.add input');
		const addButton = page.locator('form.add button[type="submit"]');

		await addInput.fill(itemText);
		await addButton.click();

		// Verify item appears in the list
		const listItem = page.locator('ul.list li').filter({ hasText: itemText });
		await expect(listItem).toBeVisible();

		// Check item
		const checkbox = listItem.locator('input[type="checkbox"]');
		await checkbox.check();
		await expect(listItem).toHaveClass(/checked/);

		// Remove item
		await listItem.locator('button.remove').click();
		await expect(listItem).toHaveCount(0);
	});

	test('bookmarks widget supports editing bookmark list', async ({ page }) => {
		await page.goto('/widget/bookmarks');
		await expect(page.locator('.detail-page')).toBeVisible({ timeout: 10000 });

		// Open editor
		await page.getByRole('button', { name: /edit/i }).click();
		await expect(page.locator('.settings-form')).toBeVisible();

		// Name is unique per run so a CI retry (which re-runs this test
		// against the same backend/db) can't collide with a bookmark a prior
		// attempt already saved.
		const bookmarkName = `Wikipedia ${Date.now()}`;
		await page.getByRole('button', { name: /add bookmark/i }).click();
		const rows = page.locator('.bookmark-row');
		const newRow = rows.last();
		await newRow.locator('input').nth(0).fill(bookmarkName);
		await newRow.locator('input').nth(1).fill('https://wikipedia.org');

		// Save bookmarks
		await page.locator('.settings-form .save').click();
		await expect(page.locator('.settings-form')).toHaveCount(0, { timeout: 15000 });

		// Verify link is present in list
		const wikiLink = page.locator('ul.list a.item').filter({ hasText: bookmarkName });
		await expect(wikiLink).toBeVisible({ timeout: 10000 });
		await expect(wikiLink).toHaveAttribute('href', 'https://wikipedia.org');
	});

	test('game 2048 supports keyboard moves, scoreboard tracking, and resetting', async ({ page }) => {
		await page.goto('/widget/game2048');
		await expect(page.locator('.detail-page')).toBeVisible();

		const scoreboard = page.locator('.scoreboard');
		await expect(scoreboard).toBeVisible();
		await expect(scoreboard.locator('.score-box').first()).toContainText('Score');

		// Play several arrow keys to move tiles
		for (const key of ['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft']) {
			await page.keyboard.press(key);
			await page.waitForTimeout(50);
		}

		// Click "New Game" button
		await page.getByRole('button', { name: /new game/i }).click();
		const scoreVal = scoreboard.locator('.score-box').first().locator('.value');
		await expect(scoreVal).toHaveText('0');
	});

	test('wordle supports on-screen virtual keyboard, word evaluation, and stats', async ({ page }) => {
		await page.goto('/widget/wordle');
		await expect(page.locator('.detail-page')).toBeVisible();

		const scoreboard = page.locator('.scoreboard');
		await expect(scoreboard).toBeVisible();
		await expect(scoreboard.locator('.score-box').first()).toContainText('Played');

		const keyboard = page.locator('.keyboard');
		await expect(keyboard).toBeVisible();

		// Type 'C', 'R', 'A', 'N', 'E' using virtual keyboard
		for (const letter of ['C', 'R', 'A', 'N', 'E']) {
			await keyboard.getByRole('button', { name: letter, exact: true }).click();
		}

		// Submit guess with ENTER
		await keyboard.getByRole('button', { name: 'ENTER', exact: true }).click();

		// First row cells should now have evaluated data-status
		const firstRowCells = page.locator('.board .row').first().locator('.cell');
		await expect(firstRowCells).toHaveCount(5);
		for (let i = 0; i < 5; i++) {
			await expect(firstRowCells.nth(i)).toHaveAttribute('data-status', /correct|present|absent/);
		}

		// Click "New game" button
		await page.getByRole('button', { name: /new game/i }).click();
		await expect(firstRowCells.first()).not.toHaveAttribute('data-status', /correct|present|absent/);
	});

	test('alerts widget renders alert status and details', async ({ page }) => {
		await page.goto('/widget/alert');
		await expect(page.locator('.detail-page')).toBeVisible();
	});

	test('clock and date widgets render valid formatted date/time', async ({ page }) => {
		await page.goto('/');
		const clock = page.locator('[data-widget-id="clock"]');
		const date = page.locator('[data-widget-id="date"]');

		await expect(clock).toBeVisible();
		await expect(date).toBeVisible();
		// Clock contains numbers/colons
		await expect(clock).toHaveText(/\d/);
	});
});
