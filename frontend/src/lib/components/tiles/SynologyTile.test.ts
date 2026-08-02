import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SynologyTile from './SynologyTile.svelte';

describe('SynologyTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SynologyTile, { props: { widgetId: 'synology' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({
			connected: false,
			host: '',
			port: 5000,
			use_https: false,
			username: '',
			has_password: false,
			volumes: [],
		});

		render(SynologyTile, { props: { widgetId: 'synology' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('shows a no-volumes-found state when connected with no volumes', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'syno.local',
			port: 5000,
			use_https: false,
			username: 'admin',
			has_password: true,
			volumes: [],
		});

		render(SynologyTile, { props: { widgetId: 'synology' } });

		expect(await screen.findByText('No volumes found')).toBeInTheDocument();
	});

	it('renders the fetched volumes', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'syno.local',
			port: 5000,
			use_https: false,
			username: 'admin',
			has_password: true,
			volumes: [
				{ name: 'Volume 1', used_percent: 25.0, status: 'normal' },
				{ name: 'Volume 2', used_percent: 90.0, status: 'warning' },
			],
		});

		render(SynologyTile, { props: { widgetId: 'synology' } });

		expect(await screen.findByText('Volume 1')).toBeInTheDocument();
		expect(screen.getByText('Volume 2')).toBeInTheDocument();
		expect(screen.getByText('25%')).toBeInTheDocument();
		expect(screen.getByText('90%')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'syno.local',
			port: 5000,
			use_https: false,
			username: 'admin',
			has_password: true,
			volumes: [],
			error: 'Could not reach the Synology NAS',
		});

		render(SynologyTile, { props: { widgetId: 'synology' } });

		expect(await screen.findByText('Could not reach the Synology NAS')).toBeInTheDocument();
	});
});
