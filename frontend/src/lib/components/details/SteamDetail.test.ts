import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'steam' } } }));

import SteamDetail from './SteamDetail.svelte';

const notConfigured = {
	configured: false,
	player: null,
	current_game: null,
	recent_games: [],
	friends: [],
	steamid: '',
	has_api_key: false,
};

const configured = {
	configured: true,
	player: {
		steamid: '76561197960435530',
		name: 'Robin',
		avatar: 'https://example.com/avatar.jpg',
		status: 'Online',
		online: true,
		current_game: 'Half-Life 2',
	},
	current_game: 'Half-Life 2',
	recent_games: [
		{ appid: 220, name: 'Half-Life 2', playtime_2weeks_minutes: 120, playtime_forever_minutes: 4500, icon_url: null },
		{ appid: 400, name: 'Portal', playtime_2weeks_minutes: 0, playtime_forever_minutes: 300, icon_url: null },
	],
	friends: [
		{
			steamid: '111',
			name: 'Zeb',
			avatar: '',
			status: 'Online',
			online: true,
			current_game: 'Dota 2',
		},
		{
			steamid: '222',
			name: 'Amy',
			avatar: '',
			status: 'Offline',
			online: false,
			current_game: null,
		},
	],
	steamid: '76561197960435530',
	has_api_key: true,
};

describe('SteamDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a not-configured hint', () => {
		render(SteamDetail, { props: { data: notConfigured } });

		expect(
			screen.getByText('Not configured yet — tap "Edit settings" to add a Steam API key and SteamID64.'),
		).toBeInTheDocument();
	});

	it('renders the player, recent games, and friends when configured', () => {
		render(SteamDetail, { props: { data: configured } });

		expect(screen.getByText('Robin')).toBeInTheDocument();
		expect(screen.getAllByText('Half-Life 2').length).toBeGreaterThan(0);
		expect(screen.getByText('Portal')).toBeInTheDocument();
		expect(screen.getByText('Zeb')).toBeInTheDocument();
		expect(screen.getByText('Amy')).toBeInTheDocument();
		expect(screen.getByText('Dota 2')).toBeInTheDocument();
	});

	it('sorts friends in-game first, then online, then offline', () => {
		render(SteamDetail, { props: { data: configured } });

		const names = screen.getAllByText(/^(Zeb|Amy)$/).map((el) => el.textContent);
		expect(names).toEqual(['Zeb', 'Amy']);
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(SteamDetail, { props: { data: { ...configured, error: 'Steam rejected the request.' } } });

		expect(screen.getByText('Steam rejected the request.')).toBeInTheDocument();
	});

	it('opens the settings editor prefilled with the steamid but not the API key', async () => {
		render(SteamDetail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));

		expect(screen.getByPlaceholderText('76561197960435530')).toHaveValue('76561197960435530');
		expect(screen.getByPlaceholderText('Set — enter a new value to replace it')).toHaveValue('');
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...configured, steamid: '76561197960435530' });

		render(SteamDetail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('steam', { steamid: '76561197960435530' }),
		);
		expect(widgetDetail).toHaveBeenCalledWith('steam');
	});

	it('does not send an api_key when the field is left blank', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(configured);

		render(SteamDetail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		const [, settings] = updateWidgetSettings.mock.calls[0];
		expect(settings).not.toHaveProperty('api_key');
	});

	it('sends a new api_key when the user types one', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(configured);

		render(SteamDetail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.input(screen.getByPlaceholderText('Set — enter a new value to replace it'), {
			target: { value: 'new-secret-key' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('steam', {
				steamid: '76561197960435530',
				api_key: 'new-secret-key',
			}),
		);
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(SteamDetail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the Steam settings.')).toBeInTheDocument();
	});
});
