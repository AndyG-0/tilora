import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'bf6' } } }));

import BF6Detail from './BF6Detail.svelte';

const notConfigured = {
	configured: false,
	server: null,
	player: null,
	server_name: '',
	player_name: '',
	platform: 'pc',
};

const server = {
	server_id: 'abc',
	name: 'The Truth Hurts #2 Hardcore Tsuru Reef',
	region: 'Oceania',
	map: 'Tsuru Reef',
	mode: 'Conquest large',
	player_count: 24,
	max_players: 64,
	owner_name: 'Rogero1984',
};

const player = {
	user_name: 'levelcap',
	avatar: 'https://example.com/avatar.png',
	score: 87585,
	kills: 314,
	deaths: 374,
	wins: 7,
	loses: 18,
	assists: 201,
	kill_death: 0.84,
	win_percent: '28.0%',
	accuracy: '20.4%',
	headshots: '18.15%',
	kills_per_minute: 0.9,
	kills_per_match: 12.56,
	time_played: '5:50:06',
	matches_played: 25,
};

const configured = {
	configured: true,
	server,
	player,
	server_name: 'Tsuru',
	player_name: 'LevelCap',
	platform: 'steam',
};

describe('BF6Detail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a not-configured hint', () => {
		render(BF6Detail, { props: { data: notConfigured } });

		expect(
			screen.getByText('Not configured yet — tap "Edit settings" to add a server name and/or player name to track.'),
		).toBeInTheDocument();
	});

	it('renders server details when configured', () => {
		render(BF6Detail, { props: { data: configured } });

		expect(screen.getByText('The Truth Hurts #2 Hardcore Tsuru Reef')).toBeInTheDocument();
		expect(screen.getByText('24/64 players')).toBeInTheDocument();
		expect(screen.getByText('Conquest large on Tsuru Reef')).toBeInTheDocument();
		expect(screen.getByText('Oceania')).toBeInTheDocument();
	});

	it('renders player stats when configured', () => {
		render(BF6Detail, { props: { data: configured } });

		expect(screen.getByText('levelcap')).toBeInTheDocument();
		expect(screen.getByText('314')).toBeInTheDocument();
		expect(screen.getByText('374')).toBeInTheDocument();
		expect(screen.getByText('0.84')).toBeInTheDocument();
		expect(screen.getByText('28.0%')).toBeInTheDocument();
		expect(screen.getByText('20.4%')).toBeInTheDocument();
	});

	it('shows an error line when the plugin surfaces a fetch error', () => {
		render(BF6Detail, { props: { data: { ...configured, error: 'No server found.' } } });

		expect(screen.getByText('No server found.')).toBeInTheDocument();
	});

	it('shows a no-data hint for a configured but dataless server/player', () => {
		const dataless = {
			configured: true,
			server: null,
			player: null,
			server_name: 'Tsuru',
			player_name: 'LevelCap',
			platform: 'pc',
		};

		render(BF6Detail, { props: { data: dataless } });

		expect(screen.getByText('No server data available.')).toBeInTheDocument();
		expect(screen.getByText('No player stats available.')).toBeInTheDocument();
	});

	it('opens the settings editor prefilled with current settings', async () => {
		render(BF6Detail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));

		expect(screen.getByPlaceholderText('e.g. Tsuru Reef')).toHaveValue('Tsuru');
		expect(screen.getByPlaceholderText('e.g. LevelCap')).toHaveValue('LevelCap');
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(configured);

		render(BF6Detail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('bf6', {
				server_name: 'Tsuru',
				player_name: 'LevelCap',
				platform: 'steam',
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('bf6');
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(BF6Detail, { props: { data: configured } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not save the Battlefield 6 settings.')).toBeInTheDocument();
	});

	it('hides the avatar image if it fails to load, instead of leaving a broken image', async () => {
		const { container } = render(BF6Detail, { props: { data: configured } });

		const avatar = container.querySelector('img.avatar');
		expect(avatar).toBeInTheDocument();
		await fireEvent.error(avatar!);

		expect(container.querySelector('img.avatar')).not.toBeInTheDocument();
	});
});
