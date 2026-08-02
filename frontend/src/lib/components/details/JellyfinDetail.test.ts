import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const {
	widgetDetail,
	updateWidgetSettings,
	jellyfinTestConnection,
	jellyfinChildren,
	jellyfinImageUrl,
	jellyfinStreamUrl,
} = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	jellyfinTestConnection: vi.fn(),
	jellyfinChildren: vi.fn(),
	jellyfinImageUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/image`),
	jellyfinStreamUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/stream`),
}));
vi.mock('$lib/api', () => ({
	api: {
		widgetDetail,
		updateWidgetSettings,
		jellyfinTestConnection,
		jellyfinChildren,
		jellyfinImageUrl,
		jellyfinStreamUrl,
	},
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'jellyfin' } } }));

import JellyfinDetail from './JellyfinDetail.svelte';

const notConnected = {
	connected: false,
	host: '',
	port: 8096,
	use_https: false,
	auth_mode: 'api_key' as const,
	username: '',
	library_ids: [],
	has_api_key: false,
	has_password: false,
	playback_mode: 'compatible' as const,
};

const connected = {
	...notConnected,
	connected: true,
	host: 'jellyfin.local',
	has_api_key: true,
};

describe('JellyfinDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		jellyfinChildren.mockResolvedValue([]);
	});

	it('shows a not-connected hint and never calls jellyfinChildren', async () => {
		render(JellyfinDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — tap "Edit connection" to set up Jellyfin.')).toBeInTheDocument();
		expect(jellyfinChildren).not.toHaveBeenCalled();
	});

	it('loads and renders root items when connected, showing posters only for items that have one', async () => {
		jellyfinChildren.mockResolvedValue([
			{
				id: '1',
				name: 'With Poster',
				has_poster: true,
				is_folder: false,
				year: 2020,
				runtime_minutes: 90,
				overview: '',
			},
			{
				id: '2',
				name: 'Without Poster',
				has_poster: false,
				is_folder: false,
				year: null,
				runtime_minutes: null,
				overview: '',
			},
		]);

		render(JellyfinDetail, { props: { data: connected } });

		expect(await screen.findByText('With Poster')).toBeInTheDocument();
		expect(screen.getByText('Without Poster')).toBeInTheDocument();
		expect(screen.getByAltText('With Poster')).toBeInTheDocument();
		expect(screen.queryByAltText('Without Poster')).not.toBeInTheDocument();
		expect(jellyfinChildren).toHaveBeenCalledWith('jellyfin', undefined);
	});

	it('navigates into a folder and updates the breadcrumb', async () => {
		jellyfinChildren.mockResolvedValueOnce([
			{
				id: 'f1',
				name: 'Movies Folder',
				has_poster: false,
				is_folder: true,
				year: null,
				runtime_minutes: null,
				overview: '',
			},
		]);
		jellyfinChildren.mockResolvedValueOnce([]);

		render(JellyfinDetail, { props: { data: connected } });

		const folder = await screen.findByText('Movies Folder');
		await fireEvent.click(folder);

		expect(await screen.findByText('Nothing here.')).toBeInTheDocument();
		expect(screen.getByText('Movies Folder', { selector: '.crumb' })).toBeInTheDocument();
		expect(jellyfinChildren).toHaveBeenLastCalledWith('jellyfin', 'f1');
	});

	it('opens the player for a playable item and closes it', async () => {
		jellyfinChildren.mockResolvedValue([
			{ id: '1', name: 'A Movie', has_poster: true, is_folder: false, year: 2020, runtime_minutes: 90, overview: '' },
		]);

		render(JellyfinDetail, { props: { data: connected } });

		const item = await screen.findByText('A Movie');
		await fireEvent.click(item);

		expect(screen.getByRole('dialog', { name: 'A Movie' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Close player' }));

		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});

	it('tests the connection and saves settings from the editor', async () => {
		jellyfinTestConnection.mockResolvedValue({ ok: true, server_name: 'My Server', error: null });
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue(connected);

		render(JellyfinDetail, { props: { data: connected } });

		await fireEvent.click(screen.getByText('Edit connection'));
		await fireEvent.click(screen.getByText('Test connection'));

		expect(await screen.findByText('✓ Connected to My Server')).toBeInTheDocument();

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(widgetDetail).toHaveBeenCalledWith('jellyfin');
	});
});
