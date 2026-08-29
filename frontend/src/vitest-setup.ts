import '@testing-library/jest-dom/vitest';
import { vi } from 'vitest';
import { register, init, waitLocale } from 'svelte-i18n';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

// All four locales are registered (mirroring the real app's bootstrap) so
// tests that explicitly switch locale can assert on translated text.
// Waiting for 'en' here means every test's `$_()` calls resolve real
// English strings synchronously by default, so existing assertions against
// literal English text keep passing unmodified.
register('en', () => import('./lib/i18n/locales/en.json'));
register('es', () => import('./lib/i18n/locales/es.json'));
register('fr', () => import('./lib/i18n/locales/fr.json'));
register('de', () => import('./lib/i18n/locales/de.json'));
init({ fallbackLocale: 'en', initialLocale: 'en' });
await waitLocale();

// jsdom doesn't implement ResizeObserver; components only use it to detect
// content-size changes (e.g. scrollFade), which isn't relevant in tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
	globalThis.ResizeObserver = class {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}

if (!globalThis.localStorage || typeof globalThis.localStorage.clear !== 'function') {
	let store: Record<string, string> = {};
	const mockStorage: Storage = {
		getItem: (key: string) => store[key] ?? null,
		setItem: (key: string, value: string) => {
			store[key] = String(value);
		},
		removeItem: (key: string) => {
			delete store[key];
		},
		clear: () => {
			store = {};
		},
		key: (index: number) => Object.keys(store)[index] ?? null,
		get length() {
			return Object.keys(store).length;
		},
	};
	Object.defineProperty(globalThis, 'localStorage', {
		value: mockStorage,
		configurable: true,
		writable: true,
	});
}

// jsdom doesn't implement the Web Animations API, which Svelte's transition
// directives (e.g. `transition:fade`) use internally via `element.animate()`.
// Without this, any test that swaps a `{#key}`-ed, transitioning element
// throws "element.animate is not a function" as an unhandled exception.
// Resolving `onfinish` on a microtask lets Svelte's two-phase transition
// (a zero-duration "delay" animation, then the real one) advance through
// both phases on its own.
if (typeof Element.prototype.animate !== 'function') {
	Element.prototype.animate = function () {
		const animation = {
			playState: 'running',
			currentTime: 0,
			effect: null,
			onfinish: null as (() => void) | null,
			cancel() {
				this.playState = 'idle';
			},
		};
		queueMicrotask(() => {
			animation.playState = 'finished';
			animation.onfinish?.();
		});
		return animation as unknown as Animation;
	};
}
