import { fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { locale, waitLocale } from 'svelte-i18n';
import type { SportsSummaryGame, SportsTrendingGame } from '$lib/api';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SportsTile from './SportsTile.svelte';

function makeGame(overrides: Partial<SportsSummaryGame> = {}): SportsSummaryGame {
	return {
		id: '1',
		date: '2026-09-14T00:20Z',
		state: 'pre',
		completed: false,
		status_detail: '9/13 - 8:20 PM EDT',
		home_team: 'New York Giants',
		home_abbreviation: 'NYG',
		away_team: 'Dallas Cowboys',
		away_abbreviation: 'DAL',
		home_score: null,
		away_score: null,
		broadcasts: ['NBC'],
		broadcast_links: [{ name: 'NBC', url: 'https://www.nbc.com/live' }],
		venue: 'MetLife Stadium',
		is_home: false,
		opponent: 'New York Giants',
		league: 'nfl',
		league_label: 'NFL',
		team: 'Dallas Cowboys',
		team_espn_url: 'https://www.espn.com/nfl/team/_/name/dal',
		...overrides,
	};
}

function makeTrendingGame(overrides: Partial<SportsTrendingGame> = {}): SportsTrendingGame {
	return {
		id: '2',
		league: 'college-football',
		league_label: 'College Football',
		date: '2026-09-14T17:00Z',
		state: 'pre',
		completed: false,
		status_detail: '9/14 - 1:00 PM EDT',
		home_team: 'Texas Longhorns',
		home_abbreviation: 'TEX',
		home_rank: 3,
		home_espn_url: 'https://www.espn.com/college-football/team/_/name/tex',
		away_team: 'Ohio State Buckeyes',
		away_abbreviation: 'OSU',
		away_rank: 1,
		away_espn_url: 'https://www.espn.com/college-football/team/_/name/osu',
		home_score: null,
		away_score: null,
		broadcast_links: [{ name: 'ABC', url: null }],
		venue: 'Darrell K Royal Stadium',
		...overrides,
	};
}

describe('SportsTile', () => {
	afterEach(async () => {
		locale.set('en');
		await waitLocale();
	});

	it('translates a live game status when the locale changes', async () => {
		locale.set('fr');
		await waitLocale();
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [
				makeGame({
					state: 'in',
					status_detail: 'Q3 4:12',
					broadcasts: [],
					broadcast_links: [],
					venue: null,
				}),
			],
			trending: [],
			upcoming_games: [],
		});

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('En direct — Q3 4:12')).toBeInTheDocument();
	});

	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-configured hint', async () => {
		widgetSummary.mockResolvedValue({ configured: false, todays_games: [], trending: [], upcoming_games: [] });

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No teams configured')).toBeInTheDocument();
	});

	it('shows a no-upcoming-games hint when configured but empty', async () => {
		widgetSummary.mockResolvedValue({ configured: true, todays_games: [], trending: [], upcoming_games: [] });

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No upcoming games')).toBeInTheDocument();
	});

	it("renders a followed team's game today in the today section", async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [makeGame()],
			trending: [],
			upcoming_games: [],
		});

		const { container } = render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('NFL')).toBeInTheDocument();
		// The team name is wrapped in its own <a>, so the combined matchup
		// text is split across elements — check the rendered output rather
		// than a single node.
		expect(container.textContent).toContain('Dallas Cowboys @ New York Giants');
		expect(screen.getByText('NBC')).toBeInTheDocument();
		// The upcoming-games section always renders while configured (even
		// empty, as a hint), so it still counts as a second visible section
		// and the today label is shown.
		expect(screen.getByText("My Team's Games Today")).toBeInTheDocument();
	});

	it("renders a followed team's next game with broadcast info in the upcoming section", async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [],
			trending: [],
			upcoming_games: [makeGame()],
		});

		const { container } = render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('NFL')).toBeInTheDocument();
		expect(container.textContent).toContain('Dallas Cowboys @ New York Giants');
		expect(screen.getByText('NBC')).toBeInTheDocument();
	});

	it('shows a live badge with the status detail for in-progress games', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [
				makeGame({
					id: '2',
					state: 'in',
					status_detail: 'Q3 4:12',
					home_score: '10',
					away_score: '14',
					broadcasts: [],
					broadcast_links: [],
					venue: null,
				}),
			],
			trending: [],
			upcoming_games: [],
		});

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Live — Q3 4:12')).toBeInTheDocument();
	});

	it('renders today, top, and upcoming sections in that order with labels when all three have content', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [makeGame({ id: '1' })],
			trending: [makeTrendingGame({ id: '2' })],
			upcoming_games: [makeGame({ id: '3', opponent: 'Chicago Bears', home_team: 'Chicago Bears' })],
		});

		const { container } = render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		const today = await screen.findByText("My Team's Games Today");
		const top = screen.getByText('Top Games Today');
		const upcoming = screen.getByText("My Team's Upcoming Games");

		// DOM order: today's section label appears before top games, which
		// appears before the upcoming section label.
		expect(today.compareDocumentPosition(top) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		expect(top.compareDocumentPosition(upcoming) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		expect(container.textContent).toContain('#1 Ohio State Buckeyes @ #3 Texas Longhorns');
	});

	it('renders trending games even when no teams are configured', async () => {
		widgetSummary.mockResolvedValue({
			configured: false,
			todays_games: [],
			upcoming_games: [],
			trending: [makeTrendingGame()],
		});

		const { container } = render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		await screen.findByText('College Football');
		expect(container.textContent).toContain('#1 Ohio State Buckeyes @ #3 Texas Longhorns');
		expect(screen.queryByText('No teams configured')).not.toBeInTheDocument();
		// No followed-team sections render when there are no followed teams,
		// and with only one section present the redundant label is skipped too.
		expect(screen.queryByText("My Team's Games Today")).not.toBeInTheDocument();
		expect(screen.queryByText('Top Games Today')).not.toBeInTheDocument();
		expect(screen.queryByText("My Team's Upcoming Games")).not.toBeInTheDocument();
	});

	it("does not duplicate a followed team's today game inside the top games section", async () => {
		// Dedup between todays_games and trending happens server-side; the
		// tile just needs to render each list as given without merging them.
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [makeGame({ id: '10' })],
			trending: [makeTrendingGame({ id: '11' })],
			upcoming_games: [],
		});

		const { container } = render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		await screen.findByText('NFL');
		const occurrences = (container.textContent ?? '').split('Dallas Cowboys @ New York Giants').length - 1;
		expect(occurrences).toBe(1);
		expect(container.textContent).toContain('#1 Ohio State Buckeyes @ #3 Texas Longhorns');
	});

	it('renders a broadcast link as a clickable anchor when a URL is known', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [makeGame()],
			trending: [],
			upcoming_games: [],
		});

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		const link = await screen.findByRole('link', { name: 'NBC' });
		expect(link).toHaveAttribute('href', 'https://www.nbc.com/live');
	});

	it('renders a broadcast name as plain text when no URL is known', async () => {
		widgetSummary.mockResolvedValue({
			configured: false,
			todays_games: [],
			upcoming_games: [],
			trending: [makeTrendingGame()],
		});

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('ABC')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'ABC' })).not.toBeInTheDocument();
	});

	it("links a team's name to its ESPN team page without also opening the widget detail view", async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			todays_games: [makeGame()],
			trending: [],
			upcoming_games: [],
		});

		render(SportsTile, { props: { widgetId: 'sports', refreshIntervalSeconds: 60 } });

		const link = await screen.findByRole('link', { name: 'Dallas Cowboys' });
		expect(link).toHaveAttribute('href', 'https://www.espn.com/nfl/team/_/name/dal');

		await fireEvent.click(link);

		expect(goto).not.toHaveBeenCalled();
	});
});
