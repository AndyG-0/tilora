import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const {
	widgetDetail,
	updateWidgetSettings,
	jellyfinChildren,
	jellyfinItemDetail,
	jellyfinSubtitleUrl,
	jellyfinImageUrl,
	jellyfinStreamUrl,
	jellyfinHlsMasterUrl,
	jellyfinStopPlayback,
	updatePreferences,
	getPreferences,
} = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
	jellyfinChildren: vi.fn(),
	jellyfinItemDetail: vi.fn(),
	jellyfinSubtitleUrl: vi.fn(),
	jellyfinImageUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/image`),
	jellyfinStreamUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/stream`),
	jellyfinHlsMasterUrl: vi.fn(
		(wId: string, itemId: string, opts: { playSessionId: string }) =>
			`https://example.com/${wId}/${itemId}/hls/master.m3u8?play_session_id=${opts.playSessionId}`,
	),
	jellyfinStopPlayback: vi.fn().mockResolvedValue({ status: 'ok' }),
	updatePreferences: vi.fn().mockResolvedValue({}),
	getPreferences: vi.fn().mockResolvedValue({}),
}));
vi.mock('$lib/api', () => ({
	api: {
		widgetDetail,
		updateWidgetSettings,
		jellyfinChildren,
		jellyfinItemDetail,
		jellyfinSubtitleUrl,
		jellyfinImageUrl,
		jellyfinStreamUrl,
		jellyfinHlsMasterUrl,
		jellyfinStopPlayback,
		updatePreferences,
		getPreferences,
	},
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'jellyfin' } } }));

import { user } from '$lib/stores/user';
import JellyfinDetail from './JellyfinDetail.svelte';

const notConnected = {
	connected: false,
	content_mode: 'added' as const,
	resume_available: false,
};

const connected = {
	...notConnected,
	connected: true,
};

describe('JellyfinDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		jellyfinChildren.mockResolvedValue([]);
		jellyfinItemDetail.mockResolvedValue(null);
		user.set({ id: 'admin-user', name: 'Admin', avatar: null, role: 'admin' });
	});

	it('shows a not-connected hint and never calls jellyfinChildren', async () => {
		render(JellyfinDetail, { props: { data: notConnected } });

		expect(screen.getByText('Not connected yet — set up Jellyfin in Network Settings.')).toBeInTheDocument();
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

	it('changes the tile content mode and refetches detail', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...connected, content_mode: 'played' });

		render(JellyfinDetail, { props: { data: { ...connected, resume_available: true } } });
		await screen.findByText('Tile content');

		await fireEvent.click(screen.getByRole('button', { name: 'Continue watching' }));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalledWith('jellyfin', { content_mode: 'played' }));
		expect(widgetDetail).toHaveBeenCalledWith('jellyfin');
	});

	it('disables played/both content modes and shows a hint when resume is unavailable', async () => {
		render(JellyfinDetail, { props: { data: { ...connected, resume_available: false } } });

		await screen.findByText('Tile content');

		expect(screen.getByRole('button', { name: 'Continue watching' })).toBeDisabled();
		expect(screen.getByRole('button', { name: 'Both' })).toBeDisabled();
		expect(
			screen.getByText('Continue Watching needs username/password auth — switch the auth mode above to enable it.'),
		).toBeInTheDocument();
	});

	it('hides the tile content controls for a non-admin', async () => {
		user.set({ id: 'member-user', name: 'Member', avatar: null, role: 'member' });

		render(JellyfinDetail, { props: { data: connected } });

		await screen.findByText('Nothing here.');
		expect(screen.queryByText('Tile content')).not.toBeInTheDocument();
	});
});
