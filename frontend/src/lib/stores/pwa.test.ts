import { describe, expect, it, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import { pwaState, initPwa, promptInstall, applyUpdate, dismissUpdate } from './pwa';

describe('pwa store', () => {
	beforeEach(() => {
		vi.restoreAllMocks();
		pwaState.set({
			canInstall: false,
			isStandalone: false,
			updateAvailable: false,
			isOnline: true,
		});
	});

	it('initializes with default values', () => {
		const state = get(pwaState);
		expect(state.canInstall).toBe(false);
		expect(state.isStandalone).toBe(false);
		expect(state.updateAvailable).toBe(false);
		expect(state.isOnline).toBe(true);
	});

	it('dismissUpdate resets updateAvailable to false', () => {
		pwaState.set({
			canInstall: false,
			isStandalone: false,
			updateAvailable: true,
			isOnline: true,
		});

		dismissUpdate();
		expect(get(pwaState).updateAvailable).toBe(false);
	});

	it('initPwa registers event listeners and updates store on online/offline events', () => {
		const cleanup = initPwa();

		window.dispatchEvent(new Event('offline'));
		expect(get(pwaState).isOnline).toBe(false);

		window.dispatchEvent(new Event('online'));
		expect(get(pwaState).isOnline).toBe(true);

		cleanup();
	});

	it('handles beforeinstallprompt and enables canInstall', async () => {
		const cleanup = initPwa();

		const promptMock = vi.fn().mockResolvedValue(undefined);
		const userChoicePromise = Promise.resolve({ outcome: 'accepted' as const, platform: 'web' });

		const event = Object.assign(new Event('beforeinstallprompt'), {
			prompt: promptMock,
			userChoice: userChoicePromise,
			platforms: ['web'],
		});

		window.dispatchEvent(event);

		expect(get(pwaState).canInstall).toBe(true);

		const accepted = await promptInstall();
		expect(accepted).toBe(true);
		expect(promptMock).toHaveBeenCalledTimes(1);
		expect(get(pwaState).canInstall).toBe(false);

		cleanup();
	});

	it('handles rejected install prompt gracefully', async () => {
		const cleanup = initPwa();

		const promptMock = vi.fn().mockResolvedValue(undefined);
		const userChoicePromise = Promise.resolve({ outcome: 'dismissed' as const, platform: 'web' });

		const event = Object.assign(new Event('beforeinstallprompt'), {
			prompt: promptMock,
			userChoice: userChoicePromise,
			platforms: ['web'],
		});

		window.dispatchEvent(event);
		expect(get(pwaState).canInstall).toBe(true);

		const accepted = await promptInstall();
		expect(accepted).toBe(false);
		expect(get(pwaState).canInstall).toBe(false);

		cleanup();
	});

	it('handles appinstalled event by marking isStandalone true', () => {
		const cleanup = initPwa();

		window.dispatchEvent(new Event('appinstalled'));

		const state = get(pwaState);
		expect(state.canInstall).toBe(false);
		expect(state.isStandalone).toBe(true);

		cleanup();
	});

	it('applyUpdate sends SKIP_WAITING to waiting service worker or reloads', async () => {
		const postMessageMock = vi.fn();
		const waitingWorker = { postMessage: postMessageMock };

		// Mock navigator.serviceWorker.getRegistration
		const getRegistrationMock = vi.fn().mockResolvedValue({
			waiting: waitingWorker,
		});

		Object.defineProperty(navigator, 'serviceWorker', {
			value: {
				register: vi.fn().mockResolvedValue({}),
				addEventListener: vi.fn(),
				removeEventListener: vi.fn(),
				getRegistration: getRegistrationMock,
			},
			configurable: true,
		});

		applyUpdate();
		await new Promise((resolve) => setTimeout(resolve, 10));

		expect(getRegistrationMock).toHaveBeenCalled();
		expect(postMessageMock).toHaveBeenCalledWith({ type: 'SKIP_WAITING' });
	});
});
