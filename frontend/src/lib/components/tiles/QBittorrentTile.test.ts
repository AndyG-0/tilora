import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import QBittorrentTile from './QBittorrentTile.svelte';

describe('QBittorrentTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(QBittorrentTile, { props: { widgetId: 'qbittorrent' } });

		expect(screen.getByText('Loading qBittorrent…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({
			connected: false,
			host: '',
			port: 8080,
			use_https: false,
			username: 'admin',
			has_password: false,
		});

		render(QBittorrentTile, { props: { widgetId: 'qbittorrent' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('renders the fetched summary', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			host: 'qbit.local',
			port: 8080,
			use_https: false,
			username: 'admin',
			has_password: true,
			torrent_count: 3,
			downloading_count: 1,
			seeding_count: 2,
			download_speed_bps: 1_000_000,
			upload_speed_bps: 500_000,
		});

		render(QBittorrentTile, { props: { widgetId: 'qbittorrent' } });

		expect(await screen.findByText('3 torrents')).toBeInTheDocument();
		expect(screen.getByText('↓ 8.0 Mbps')).toBeInTheDocument();
		expect(screen.getByText('↑ 4.0 Mbps')).toBeInTheDocument();
		expect(screen.getByText('1 downloading · 2 seeding')).toBeInTheDocument();
	});
});
