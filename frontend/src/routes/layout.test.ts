import { render, screen } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { get } from 'svelte/store';

// +layout.svelte mounts Screensaver.svelte, which pulls in widgetComponents.ts's
// full Detail-component barrel, including PhotoDetail, which reads
// PUBLIC_API_BASE_URL from this module at import time.
vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

const {
	goto,
	registerDevice,
	currentUser,
	setupStatus,
	getPreferences,
	listWidgets,
	layoutStatus,
	pageState,
	getScreensaverSettings,
} = vi.hoisted(() => ({
	goto: vi.fn(),
	registerDevice: vi.fn(),
	currentUser: vi.fn(),
	setupStatus: vi.fn(),
	getPreferences: vi.fn(),
	// Resolved immediately (not just in beforeEach) because $lib/stores/widgets
	// calls this eagerly at module-import time, before any test body runs.
	listWidgets: vi.fn().mockResolvedValue([]),
	layoutStatus: vi.fn(),
	pageState: { url: new URL('http://localhost/') },
	// Never resolved by default so the screensaver stays inert (disabled) in
	// tests that don't care about it — mirrors getPreferences below.
	getScreensaverSettings: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$app/state', () => ({ page: pageState }));
vi.mock('$lib/api', () => ({
	api: {
		registerDevice,
		renameDevice: vi.fn(),
		currentUser,
		logoutUser: vi.fn(),
		setupStatus,
		getPreferences,
		listWidgets,
		layoutStatus,
		listDevices: vi.fn().mockResolvedValue([]),
		copyDeviceLayout: vi.fn(),
		getScreensaverSettings,
		updateScreensaverSettings: vi.fn(),
	},
	describeFetchError: (error: unknown) => (error instanceof TypeError ? 'network' : 'server'),
}));

import Layout from './+layout.svelte';
import { user, userLoaded } from '$lib/stores/user';
import { needsSetup, setupStatusLoaded, setupStatusError } from '$lib/stores/setup';
import { device } from '$lib/stores/device';

function emptyChildren() {
	return createRawSnippet(() => ({ render: () => '<div data-testid="app-content"></div>' }));
}

async function flush() {
	await new Promise((resolve) => setTimeout(resolve, 0));
	await new Promise((resolve) => setTimeout(resolve, 0));
}

describe('+layout.svelte', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		pageState.url = new URL('http://localhost/');
		user.set(null);
		userLoaded.set(false);
		needsSetup.set(false);
		setupStatusLoaded.set(false);
		setupStatusError.set(null);
		device.set(null);
		registerDevice.mockResolvedValue({ id: 'd1', name: 'New Device', is_new: false });
		getPreferences.mockReturnValue(new Promise(() => {}));
		getScreensaverSettings.mockReturnValue(new Promise(() => {}));
		// Most tests don't exercise the "copy layout from another device" prompt —
		// reporting a layout already exists keeps it from ever being offered.
		layoutStatus.mockResolvedValue({ has_layout: true });
	});

	it('redirects to /setup on a fresh install with no admin yet', async () => {
		setupStatus.mockResolvedValue({ needs_setup: true });
		currentUser.mockRejectedValue(new Error('401'));

		render(Layout, { props: { children: emptyChildren() } });
		await flush();

		expect(goto).toHaveBeenCalledWith('/setup');
	});

	it('redirects away from /setup once setup has already been completed', async () => {
		pageState.url = new URL('http://localhost/setup');
		setupStatus.mockResolvedValue({ needs_setup: false });
		currentUser.mockRejectedValue(new Error('401'));

		render(Layout, { props: { children: emptyChildren() } });
		await flush();

		expect(goto).toHaveBeenCalledWith('/login');
	});

	it('redirects to /login when setup is complete and there is no session', async () => {
		setupStatus.mockResolvedValue({ needs_setup: false });
		currentUser.mockRejectedValue(new Error('401'));

		render(Layout, { props: { children: emptyChildren() } });
		await flush();

		expect(goto).toHaveBeenCalledWith('/login');
	});

	it('does not redirect once a session is present', async () => {
		setupStatus.mockResolvedValue({ needs_setup: false });
		currentUser.mockResolvedValue({ id: 'u1', name: 'Alice', avatar: null, role: 'admin' });

		render(Layout, { props: { children: emptyChildren() } });
		await flush();

		expect(goto).not.toHaveBeenCalled();
		expect(get(user)).toEqual({ id: 'u1', name: 'Alice', avatar: null, role: 'admin' });
	});

	it('shows an unreachable-backend message and does not redirect when the backend is unreachable', async () => {
		setupStatus.mockRejectedValue(new TypeError('Failed to fetch'));
		currentUser.mockRejectedValue(new TypeError('Failed to fetch'));

		render(Layout, { props: { children: emptyChildren() } });
		await flush();

		expect(screen.getByText('Could not reach the Tilora backend')).toBeInTheDocument();
		expect(screen.queryByTestId('app-content')).not.toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();
	});
});
