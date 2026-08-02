import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

const { updateWidgetSettings, widgetDetail, startIcloudAuth, verifyIcloudAuth } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	startIcloudAuth: vi.fn(),
	verifyIcloudAuth: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { updateWidgetSettings, widgetDetail, startIcloudAuth, verifyIcloudAuth },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'photos' } } }));

import PhotoDetail from './PhotoDetail.svelte';

describe('PhotoDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the slideshow for a local provider', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'local',
					count: 1,
					interval_seconds: 30,
					photos: [{ filename: 'a.jpg', url: '/api/photos/photos/a.jpg' }],
				},
			},
		});

		const img = screen.getByAltText('a.jpg');
		expect(img).toHaveAttribute('src', 'http://api.test/api/photos/photos/a.jpg');
		expect(screen.getByText('1 / 1')).toBeInTheDocument();
	});

	it('shows a hint when there are no photos', () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 0, interval_seconds: 30, photos: [] } },
		});

		expect(screen.getByText('No photos found.')).toBeInTheDocument();
	});

	it('shows an indexing hint instead of "no photos found" while the first scan is running', () => {
		render(PhotoDetail, {
			props: {
				data: { provider: 'local', count: 0, interval_seconds: 30, photos: [], indexing: true },
			},
		});

		expect(screen.getByText('Indexing…')).toBeInTheDocument();
		expect(screen.queryByText('No photos found.')).not.toBeInTheDocument();
	});

	it('shows the index error instead of "no photos found" when the last scan failed', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'local',
					count: 0,
					interval_seconds: 30,
					photos: [],
					index_error: 'could not reach the source',
				},
			},
		});

		expect(screen.getByText('could not reach the source')).toBeInTheDocument();
		expect(screen.queryByText('No photos found.')).not.toBeInTheDocument();
	});

	it('shows a set-folder button for a local provider', () => {
		render(PhotoDetail, {
			props: {
				data: { provider: 'local', count: 0, interval_seconds: 30, photos: [], directory: null },
			},
		});

		expect(screen.getByText('Set folder')).toBeInTheDocument();
	});

	it('lets the user save a folder path and recursive toggle for a local provider', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			provider: 'local',
			count: 1,
			interval_seconds: 30,
			photos: [{ filename: 'a.jpg', url: '/api/photos/photos/a.jpg' }],
			directory: '/Volumes/Pictures',
			recursive: true,
		});

		render(PhotoDetail, {
			props: {
				data: { provider: 'local', count: 0, interval_seconds: 30, photos: [], directory: null },
			},
		});

		await fireEvent.click(screen.getByText('Set folder'));
		const input = screen.getByPlaceholderText('/path/to/photos');
		await fireEvent.input(input, { target: { value: '/Volumes/Pictures' } });
		await fireEvent.click(screen.getByLabelText('Include subfolders'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('photos', {
			directory: '/Volumes/Pictures',
			recursive: true,
		});
		expect(widgetDetail).toHaveBeenCalledWith('photos');
	});

	it('shows a public-link warning and a manage button for icloud_shared', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'icloud_shared',
					count: 0,
					interval_seconds: 30,
					photos: [],
					album_token: null,
				},
			},
		});

		expect(screen.getByText(/Shared Album links are public/)).toBeInTheDocument();
		expect(screen.getByText('Set album link')).toBeInTheDocument();
	});

	it('lets the user save a new album link for icloud_shared', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			provider: 'icloud_shared',
			count: 0,
			interval_seconds: 30,
			photos: [],
			album_token: 'https://www.icloud.com/sharedalbum/#tok',
		});

		render(PhotoDetail, {
			props: {
				data: { provider: 'icloud_shared', count: 0, interval_seconds: 30, photos: [], album_token: null },
			},
		});

		await fireEvent.click(screen.getByText('Set album link'));
		const input = screen.getByPlaceholderText('https://www.icloud.com/sharedalbum/#...');
		await fireEvent.input(input, { target: { value: 'https://www.icloud.com/sharedalbum/#tok' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('photos', {
			album_token: 'https://www.icloud.com/sharedalbum/#tok',
		});
		expect(widgetDetail).toHaveBeenCalledWith('photos');
	});

	it('shows a set-up button for an immich provider with no base URL yet', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 0,
					interval_seconds: 30,
					photos: [],
					immich_base_url: null,
					has_immich_api_key: false,
					immich_album_id: null,
				},
			},
		});

		expect(screen.getByText('Set up Immich')).toBeInTheDocument();
	});

	it('shows a change-settings button for an already-configured immich provider', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 0,
					interval_seconds: 30,
					photos: [],
					immich_base_url: 'http://192.168.1.50:2283/api',
					has_immich_api_key: true,
					immich_album_id: 'album-1',
				},
			},
		});

		expect(screen.getByText('Change Immich settings')).toBeInTheDocument();
	});

	it('renders the slideshow for an immich provider', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 1,
					interval_seconds: 30,
					photos: [{ filename: 'asset-1', url: '/api/photos/photos/asset-1' }],
					immich_base_url: 'http://192.168.1.50:2283/api',
					has_immich_api_key: true,
					immich_album_id: 'album-1',
				},
			},
		});

		expect(screen.getByAltText('asset-1')).toBeInTheDocument();
	});

	it('lets the user save immich settings, sending the api key when one is entered', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			provider: 'immich',
			count: 1,
			interval_seconds: 30,
			photos: [{ filename: 'asset-1', url: '/api/photos/photos/asset-1' }],
			immich_base_url: 'http://192.168.1.50:2283/api',
			has_immich_api_key: true,
			immich_album_id: 'album-1',
		});

		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 0,
					interval_seconds: 30,
					photos: [],
					immich_base_url: null,
					has_immich_api_key: false,
					immich_album_id: null,
				},
			},
		});

		await fireEvent.click(screen.getByText('Set up Immich'));
		await fireEvent.input(screen.getByPlaceholderText('http://192.168.1.50:2283/api'), {
			target: { value: 'http://192.168.1.50:2283/api' },
		});
		await fireEvent.input(screen.getByPlaceholderText('API key'), {
			target: { value: 'immich-key' },
		});
		await fireEvent.input(screen.getByPlaceholderText('Album ID'), {
			target: { value: 'album-1' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('photos', {
			base_url: 'http://192.168.1.50:2283/api',
			album_id: 'album-1',
			api_key: 'immich-key',
		});
		expect(widgetDetail).toHaveBeenCalledWith('photos');
	});

	it('leaves the stored immich api key unchanged when the field is left blank', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			provider: 'immich',
			count: 1,
			interval_seconds: 30,
			photos: [{ filename: 'asset-1', url: '/api/photos/photos/asset-1' }],
			immich_base_url: 'http://192.168.1.50:2283/api',
			has_immich_api_key: true,
			immich_album_id: 'album-2',
		});

		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 0,
					interval_seconds: 30,
					photos: [],
					immich_base_url: 'http://192.168.1.50:2283/api',
					has_immich_api_key: true,
					immich_album_id: 'album-1',
				},
			},
		});

		await fireEvent.click(screen.getByText('Change Immich settings'));
		const albumInput = screen.getByPlaceholderText('Album ID');
		await fireEvent.input(albumInput, { target: { value: 'album-2' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		// api_key is omitted entirely — the backend only overwrites the stored
		// key when the incoming payload includes a non-empty value.
		expect(updateWidgetSettings).toHaveBeenCalledWith('photos', {
			base_url: 'http://192.168.1.50:2283/api',
			album_id: 'album-2',
		});
	});

	it('never pre-fills the immich api key field with a real value', async () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'immich',
					count: 0,
					interval_seconds: 30,
					photos: [],
					immich_base_url: 'http://192.168.1.50:2283/api',
					has_immich_api_key: true,
					immich_album_id: 'album-1',
				},
			},
		});

		await fireEvent.click(screen.getByText('Change Immich settings'));
		const apiKeyInput = screen.getByPlaceholderText('Set — enter a new value to replace it') as HTMLInputElement;

		expect(apiKeyInput.value).toBe('');
	});

	it('shows a connect prompt for a disconnected icloud_private widget', () => {
		render(PhotoDetail, {
			props: {
				data: { provider: 'icloud_private', count: 0, interval_seconds: 30, photos: [], connected: false },
			},
		});

		expect(screen.getByText('Connect iCloud')).toBeInTheDocument();
	});

	it('renders the slideshow for a connected icloud_private widget', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'icloud_private',
					count: 1,
					interval_seconds: 30,
					photos: [{ filename: 'id-1', url: '/api/photos/photos/id-1' }],
					connected: true,
				},
			},
		});

		expect(screen.queryByText('Connect iCloud')).not.toBeInTheDocument();
		expect(screen.getByAltText('id-1')).toBeInTheDocument();
	});

	it('walks through the icloud_private connect + 2FA flow', async () => {
		startIcloudAuth.mockResolvedValue({ connected: false, requires_2fa: true });
		verifyIcloudAuth.mockResolvedValue({ connected: true });
		widgetDetail.mockResolvedValue({
			provider: 'icloud_private',
			count: 1,
			interval_seconds: 30,
			photos: [{ filename: 'id-1', url: '/api/photos/photos/id-1' }],
			connected: true,
		});

		render(PhotoDetail, {
			props: {
				data: { provider: 'icloud_private', count: 0, interval_seconds: 30, photos: [], connected: false },
			},
		});

		await fireEvent.click(screen.getByText('Connect iCloud'));
		await vi.waitFor(() => expect(startIcloudAuth).toHaveBeenCalled());

		const code = await screen.findByPlaceholderText('123456');
		await fireEvent.input(code, { target: { value: '123456' } });
		await fireEvent.click(screen.getByText('Verify'));

		await vi.waitFor(() => expect(verifyIcloudAuth).toHaveBeenCalledWith('123456'));
		expect(await screen.findByAltText('id-1')).toBeInTheDocument();
	});

	const threePhotos = [
		{ filename: 'a.jpg', url: '/api/photos/photos/a.jpg' },
		{ filename: 'b.jpg', url: '/api/photos/photos/b.jpg' },
		{ filename: 'c.jpg', url: '/api/photos/photos/c.jpg' },
	];

	it('ArrowRight advances to the next photo', async () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos } },
		});

		await fireEvent.keyDown(window, { key: 'ArrowRight' });

		expect(screen.getByAltText('b.jpg')).toBeInTheDocument();
		expect(screen.getByText('2 / 3')).toBeInTheDocument();
	});

	it('ArrowLeft wraps to the last photo from index 0', async () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos } },
		});

		await fireEvent.keyDown(window, { key: 'ArrowLeft' });

		expect(screen.getByAltText('c.jpg')).toBeInTheDocument();
		expect(screen.getByText('3 / 3')).toBeInTheDocument();
	});

	it('swiping left on the slideshow advances to the next photo', async () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos } },
		});

		const slideshow = screen.getByAltText('a.jpg').closest('.slideshow')!;
		await fireEvent.touchStart(slideshow, { touches: [{ clientX: 200, clientY: 0 }] });
		await fireEvent.touchEnd(slideshow, { changedTouches: [{ clientX: 100, clientY: 0 }] });

		expect(screen.getByAltText('b.jpg')).toBeInTheDocument();
	});

	it('a vertical-dominant touch does not navigate', async () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos } },
		});

		const slideshow = screen.getByAltText('a.jpg').closest('.slideshow')!;
		await fireEvent.touchStart(slideshow, { touches: [{ clientX: 200, clientY: 0 }] });
		await fireEvent.touchEnd(slideshow, { changedTouches: [{ clientX: 150, clientY: 200 }] });

		expect(screen.getByAltText('a.jpg')).toBeInTheDocument();
	});

	it('manual navigation restarts the auto-advance timer', async () => {
		vi.useFakeTimers();
		try {
			render(PhotoDetail, {
				props: {
					data: { provider: 'local', count: 3, interval_seconds: 10, photos: threePhotos },
				},
			});

			await fireEvent.keyDown(window, { key: 'ArrowRight' }); // -> b.jpg, timer restarted
			await vi.advanceTimersByTimeAsync(9_000);

			// still on b.jpg — the restarted 10s timer hasn't fired yet
			expect(screen.getByAltText('b.jpg')).toBeInTheDocument();
		} finally {
			vi.useRealTimers();
		}
	});

	it('does not render prev/next buttons for a single photo', () => {
		render(PhotoDetail, {
			props: {
				data: {
					provider: 'local',
					count: 1,
					interval_seconds: 30,
					photos: [{ filename: 'a.jpg', url: '/api/photos/photos/a.jpg' }],
				},
			},
		});

		expect(screen.queryByLabelText('Next photo')).not.toBeInTheDocument();
		expect(screen.queryByLabelText('Previous photo')).not.toBeInTheDocument();
	});

	it('renders prev/next buttons for multiple photos', () => {
		render(PhotoDetail, {
			props: { data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos } },
		});

		expect(screen.getByLabelText('Next photo')).toBeInTheDocument();
		expect(screen.getByLabelText('Previous photo')).toBeInTheDocument();
	});

	it('ignores arrow keys while typing in the folder path input', async () => {
		render(PhotoDetail, {
			props: {
				data: { provider: 'local', count: 3, interval_seconds: 30, photos: threePhotos, directory: null },
			},
		});

		await fireEvent.click(screen.getByText('Set folder'));
		const input = screen.getByPlaceholderText('/path/to/photos');
		input.focus();
		await fireEvent.keyDown(input, { key: 'ArrowRight' });

		expect(screen.getByAltText('a.jpg')).toBeInTheDocument();
	});
});
