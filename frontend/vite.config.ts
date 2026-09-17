import adapter from '@sveltejs/adapter-node';
import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	optimizeDeps: {
		// leaflet is only ever reached via a dynamic import() (see FlightsMap.svelte),
		// so Vite's dependency scanner won't find it during the initial crawl. Without
		// this, the first test to render a flights map triggers a *mid-session*
		// re-optimization + full-page reload, which can race with whatever other
		// page happens to be loaded at that moment and flake it.
		include: ['leaflet'],
	},
	server: {
		host: '0.0.0.0',
		port: 5173,
		strictPort: false,
		allowedHosts: true,
		proxy: {
			'/api': {
				target: 'http://127.0.0.1:8000',
				changeOrigin: true,
			},
		},
		warmup: {
			// The dashboard grid resolves every tile/detail/screensaver component
			// on demand via dynamic import() (see widgetComponents.ts) so the
			// production bundle stays split per widget type. In dev, that means
			// the *first* real page load with a populated dashboard asks Vite to
			// transform a dozen-plus component files all at once; while those
			// transforms are in flight, the client runtime can observe a
			// partially-resolved module graph and throw ("Cannot read properties
			// of undefined (reading 'call')"), which tears down and immediately
			// recreates the affected effects -- visible as the whole grid
			// blinking. Warming these up at server start means they're already
			// transformed before any browser ever requests them.
			clientFiles: [
				'./src/lib/components/tiles/*.svelte',
				'./src/lib/components/details/*.svelte',
				'./src/lib/components/screensaver/**/*.svelte',
			],
		},
	},
	plugins: [
		sveltekit({
			compilerOptions: {
				// Force runes mode for the project, except for libraries. Can be removed in svelte 6.
				runes: ({ filename }) => (filename.split(/[/\\]/).includes('node_modules') ? undefined : true),
			},

			// adapter-node builds a standalone Node server, which is what the
			// kiosk deployment runs via systemd (see deploy/dashboard-frontend.service).
			adapter: adapter(),
		}),
		svelteTesting(),
	],
	test: {
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{js,ts}'],
		setupFiles: ['./src/vitest-setup.ts'],
	},
});
