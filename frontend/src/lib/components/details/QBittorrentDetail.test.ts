import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings, qbittorrentTestConnection } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	qbittorrentTestConnection: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { widgetDetail, updateWidgetSettings, qbittorrentTestConnection },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'qbittorrent' } } }));

import { user } from '$lib/stores/user';
import QBittorrentDetail from './QBittorrentDetail.svelte';

const notConnected = {
	connected: false,
	host: '',
	port: 8080,
	use_https: false,
	username: 'admin',
	has_password: false,
	torrent_count: 0,
	downloading_count: 0,
	seeding_count: 0,
	download_speed_bps: 0,
	upload_speed_bps: 0,
	torrents: [],
};

const connected = {
	...notConnected,
	connected: true,
	host: 'qbit.local',
	has_password: true,
	torrent_count: 1,
	downloading_count: 1,
	seeding_count: 0,
	download_speed_bps: 1_000_000,
	upload_speed_bps: 0,
	torrents: [
		{
			hash: 'h1',
			name: 'Ubuntu ISO',
			state: 'downloading',
			progress: 0.5,
			size_bytes: 4_000_000_000,
			download_speed_bps: 1_000_000,
			upload_speed_bps: 0,
			eta_seconds: 3600,
		},
	],
};

describe('QBittorrentDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint', () => {
		render(QBittorrentDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up qBittorrent.')).toBeInTheDocument();
	});

	it('renders stats and torrent list when connected', () => {
		render(QBittorrentDetail, { props: { data: connected } });

		expect(screen.getByText('Ubuntu ISO')).toBeInTheDocument();
		expect(screen.getByText('downloading')).toBeInTheDocument();
		expect(screen.getByText('50% of 4.0 GB')).toBeInTheDocument();
	});

	it('tests the connection and saves settings from the editor', async () => {
		qbittorrentTestConnection.mockResolvedValue({ ok: true, version: '4.6.0', error: null });
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(QBittorrentDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✓ Connected (qBittorrent 4.6.0)')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(widgetDetail).toHaveBeenCalledWith('qbittorrent');
	});

	it('shows a failed test-connection result', async () => {
		qbittorrentTestConnection.mockResolvedValue({
			ok: false,
			version: null,
			error: 'qBittorrent rejected credentials',
		});

		render(QBittorrentDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✗ qBittorrent rejected credentials')).toBeInTheDocument();
	});

	it('hides the edit-connection control for a non-admin', () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(QBittorrentDetail, { props: { data: connected } });

		expect(screen.queryByText('Edit connection')).not.toBeInTheDocument();
	});
});
