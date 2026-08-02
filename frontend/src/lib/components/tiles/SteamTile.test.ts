import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SteamTile from './SteamTile.svelte';

describe('SteamTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SteamTile, { props: { widgetId: 'steam' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-configured hint', async () => {
		widgetSummary.mockResolvedValue({
			configured: false,
			player: null,
			current_game: null,
			recent_games: [],
			steamid: '',
			has_api_key: false,
		});

		render(SteamTile, { props: { widgetId: 'steam' } });

		expect(await screen.findByText('Not configured')).toBeInTheDocument();
	});

	it('shows an error message when the plugin surfaces a fetch error', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			player: null,
			current_game: null,
			recent_games: [],
			steamid: '76561197960435530',
			has_api_key: true,
			error: 'Steam rejected the request — check the API key.',
		});

		render(SteamTile, { props: { widgetId: 'steam' } });

		expect(await screen.findByText('Steam rejected the request — check the API key.')).toBeInTheDocument();
	});

	it('renders the current game when playing, with recent games', async () => {
		widgetSummary.mockResolvedValue({
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
				{
					appid: 220,
					name: 'Half-Life 2',
					playtime_2weeks_minutes: 120,
					playtime_forever_minutes: 4500,
					icon_url: null,
				},
				{ appid: 400, name: 'Portal', playtime_2weeks_minutes: 0, playtime_forever_minutes: 300, icon_url: null },
			],
			steamid: '76561197960435530',
			has_api_key: true,
		});

		render(SteamTile, { props: { widgetId: 'steam' } });

		expect(await screen.findByText('Robin')).toBeInTheDocument();
		expect(screen.getAllByText('Half-Life 2').length).toBeGreaterThan(0);
		expect(screen.getByText('Portal')).toBeInTheDocument();
	});

	it('shows the persona status when not currently playing anything', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			player: {
				steamid: '76561197960435530',
				name: 'Robin',
				avatar: '',
				status: 'Away',
				online: true,
				current_game: null,
			},
			current_game: null,
			recent_games: [],
			steamid: '76561197960435530',
			has_api_key: true,
		});

		render(SteamTile, { props: { widgetId: 'steam' } });

		expect(await screen.findByText('Away')).toBeInTheDocument();
	});
});
