import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import BF6Tile from './BF6Tile.svelte';

describe('BF6Tile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-configured hint', async () => {
		widgetSummary.mockResolvedValue({
			configured: false,
			server: null,
			player: null,
			server_name: '',
			player_name: '',
			platform: 'pc',
		});

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Not configured')).toBeInTheDocument();
	});

	it('shows an error message when both lookups fail', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			server: null,
			player: null,
			server_name: 'Tsuru',
			player_name: '',
			platform: 'pc',
			error: "No server found matching 'Tsuru'.",
		});

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText("No server found matching 'Tsuru'.")).toBeInTheDocument();
	});

	it('renders server population and map/mode when configured with server data', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			server: {
				server_id: 'abc',
				name: 'The Truth Hurts #2',
				region: 'Oceania',
				map: 'Tsuru Reef',
				mode: 'Conquest large',
				player_count: 24,
				max_players: 64,
				owner_name: null,
			},
			player: null,
			server_name: 'Tsuru',
			player_name: '',
			platform: 'pc',
		});

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('24/64')).toBeInTheDocument();
		expect(screen.getByText('players')).toBeInTheDocument();
		expect(screen.getByText('Conquest large on Tsuru Reef')).toBeInTheDocument();
	});

	it('renders player K/D and win percent when configured with player data', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			server: null,
			player: {
				user_name: 'levelcap',
				avatar: null,
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
			},
			server_name: '',
			player_name: 'LevelCap',
			platform: 'pc',
		});

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('levelcap')).toBeInTheDocument();
		expect(screen.getByText('0.84 K/D')).toBeInTheDocument();
		expect(screen.getByText('28.0% win')).toBeInTheDocument();
	});

	it('renders both server and player when both are configured', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			server: {
				server_id: 'abc',
				name: 'The Truth Hurts #2',
				region: 'Oceania',
				map: 'Tsuru Reef',
				mode: 'Conquest large',
				player_count: 24,
				max_players: 64,
				owner_name: null,
			},
			player: {
				user_name: 'levelcap',
				avatar: null,
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
			},
			server_name: 'Tsuru',
			player_name: 'LevelCap',
			platform: 'pc',
		});

		render(BF6Tile, { props: { widgetId: 'bf6', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('24/64')).toBeInTheDocument();
		expect(screen.getByText('levelcap')).toBeInTheDocument();
	});
});
