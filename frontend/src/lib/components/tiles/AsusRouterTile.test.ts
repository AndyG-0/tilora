import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import AsusRouterTile from './AsusRouterTile.svelte';

describe('AsusRouterTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(AsusRouterTile, { props: { widgetId: 'asus_router' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({
			connected: false,
			wan_connected: false,
			client_count: 0,
			host: '',
			ssh_port: 22,
			username: '',
			has_password: false,
		});

		render(AsusRouterTile, { props: { widgetId: 'asus_router' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('renders WAN status and client count when connected', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			wan_connected: true,
			client_count: 3,
			host: 'router.local',
			ssh_port: 22,
			username: 'admin',
			has_password: true,
		});

		render(AsusRouterTile, { props: { widgetId: 'asus_router' } });

		expect(await screen.findByText('WAN up')).toBeInTheDocument();
		expect(screen.getByText('3 connected')).toBeInTheDocument();
	});

	it('shows WAN down and singular client count', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			wan_connected: false,
			client_count: 1,
			host: 'router.local',
			ssh_port: 22,
			username: 'admin',
			has_password: true,
		});

		render(AsusRouterTile, { props: { widgetId: 'asus_router' } });

		expect(await screen.findByText('WAN down')).toBeInTheDocument();
		expect(screen.getByText('1 connected')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			wan_connected: false,
			client_count: 0,
			host: 'router.local',
			ssh_port: 22,
			username: 'admin',
			has_password: true,
			error: 'Could not reach the router',
		});

		render(AsusRouterTile, { props: { widgetId: 'asus_router' } });

		expect(await screen.findByText('Could not reach the router')).toBeInTheDocument();
	});
});
