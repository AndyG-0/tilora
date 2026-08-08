import { beforeEach, describe, expect, it, vi } from 'vitest';
import { get } from 'svelte/store';

const { getScreensaverSettings, updateScreensaverSettings } = vi.hoisted(() => ({
	getScreensaverSettings: vi.fn(),
	updateScreensaverSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { getScreensaverSettings, updateScreensaverSettings } }));

beforeEach(() => {
	vi.resetModules();
	getScreensaverSettings.mockReset();
	updateScreensaverSettings.mockReset();
});

const DEFAULTS = {
	enabled: false,
	idle_timeout_seconds: 300,
	rotation_interval_seconds: 25,
	widget_ids: [],
	text_animation_style: 'marquee',
	led_color: '#ff8a00',
	text_pause_seconds: 8,
};

describe('screensaver store', () => {
	it('starts null before anything is loaded', async () => {
		const { screensaverSettings } = await import('./screensaver');

		expect(get(screensaverSettings)).toBeNull();
	});

	it('loadScreensaverSettings populates the store from the server', async () => {
		getScreensaverSettings.mockResolvedValue({ ...DEFAULTS, enabled: true });

		const { screensaverSettings, loadScreensaverSettings } = await import('./screensaver');
		await loadScreensaverSettings();

		expect(get(screensaverSettings)).toEqual({ ...DEFAULTS, enabled: true });
	});

	it('loadScreensaverSettings leaves the store untouched when the request fails', async () => {
		getScreensaverSettings.mockRejectedValue(new Error('network error'));

		const { screensaverSettings, loadScreensaverSettings } = await import('./screensaver');
		await loadScreensaverSettings();

		expect(get(screensaverSettings)).toBeNull();
	});

	it('persistScreensaverSettings sends the partial update and stores the merged response', async () => {
		updateScreensaverSettings.mockResolvedValue({ ...DEFAULTS, idle_timeout_seconds: 60 });

		const { screensaverSettings, persistScreensaverSettings } = await import('./screensaver');
		await persistScreensaverSettings({ idle_timeout_seconds: 60 });

		expect(updateScreensaverSettings).toHaveBeenCalledWith({ idle_timeout_seconds: 60 });
		expect(get(screensaverSettings)).toEqual({ ...DEFAULTS, idle_timeout_seconds: 60 });
	});

	it('persistScreensaverSettings rejects when the request fails', async () => {
		updateScreensaverSettings.mockRejectedValue(new Error('network error'));

		const { persistScreensaverSettings } = await import('./screensaver');

		await expect(persistScreensaverSettings({ enabled: true })).rejects.toThrow('network error');
	});

	it('forceScreensaverPreview starts false and can be toggled', async () => {
		const { forceScreensaverPreview } = await import('./screensaver');

		expect(get(forceScreensaverPreview)).toBe(false);

		forceScreensaverPreview.set(true);

		expect(get(forceScreensaverPreview)).toBe(true);
	});
});
