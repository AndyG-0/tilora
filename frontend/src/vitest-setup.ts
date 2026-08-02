import '@testing-library/jest-dom/vitest';

// jsdom doesn't implement ResizeObserver; components only use it to detect
// content-size changes (e.g. scrollFade), which isn't relevant in tests.
if (typeof globalThis.ResizeObserver === 'undefined') {
	globalThis.ResizeObserver = class {
		observe() {}
		unobserve() {}
		disconnect() {}
	};
}
