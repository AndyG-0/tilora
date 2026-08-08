import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import type { SportsSummaryGame, SportsTrendingGame } from '$lib/api';

const { updateWidgetSettings, widgetDetail, sportsTeams } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	sportsTeams: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail, sportsTeams } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'sports' } } }));

import SportsDetail from './SportsDetail.svelte';

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

const baseData = {
	configured: true,
	teams: [{ league: 'nfl', league_label: 'NFL', team: 'DAL', team_name: 'Dallas Cowboys' }],
	todays_games: [],
	trending: [],
	upcoming_games: [makeGame()],
	trending_leagues: ['nfl', 'nba', 'mlb', 'nhl', 'college-football', 'wnba'],
};

describe('SportsDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		// The team-abbreviation <select> only shows options once its league's
		// team list has loaded; every test that opens the editor needs this
		// resolved regardless of which league(s) it exercises.
		sportsTeams.mockResolvedValue([
			{ abbreviation: 'DAL', display_name: 'Dallas Cowboys' },
			{ abbreviation: 'LAL', display_name: 'Los Angeles Lakers' },
		]);
	});

	it("renders a followed team's upcoming game with league badge and details", () => {
		const { container } = render(SportsDetail, { props: { data: baseData } });

		expect(screen.getByText('Sports Schedule')).toBeInTheDocument();
		expect(screen.getByText("My Team's Upcoming Games")).toBeInTheDocument();
		expect(screen.getByText('NFL')).toBeInTheDocument();
		// The league badge and matchup text are siblings inside the same
		// span, so there's no single element whose own text is just the
		// matchup — check the rendered output instead of a single node.
		expect(container.textContent).toContain('Dallas Cowboys: @ New York Giants');
		expect(screen.getByText('NBC')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'NBC' })).toHaveAttribute('href', 'https://www.nbc.com/live');
		expect(screen.getByText('MetLife Stadium')).toBeInTheDocument();
	});

	it('renders an unknown broadcast name as plain text, not a link', () => {
		const data = {
			...baseData,
			upcoming_games: [
				makeGame({
					broadcasts: ['Regional Sports Network'],
					broadcast_links: [{ name: 'Regional Sports Network', url: null }],
				}),
			],
		};

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('Regional Sports Network')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'Regional Sports Network' })).not.toBeInTheDocument();
	});

	it('shows a hint when no teams are configured', () => {
		render(SportsDetail, {
			props: {
				data: {
					configured: false,
					teams: [],
					todays_games: [],
					trending: [],
					upcoming_games: [],
					trending_leagues: [],
				},
			},
		});

		expect(screen.getByText('No teams configured yet — tap "Edit teams" to follow one.')).toBeInTheDocument();
	});

	it('renders trending games even when no teams are configured', () => {
		render(SportsDetail, {
			props: {
				data: {
					configured: false,
					teams: [],
					todays_games: [],
					trending: [makeTrendingGame()],
					upcoming_games: [],
					trending_leagues: [],
				},
			},
		});

		// The "no teams configured" hint and the trending section are
		// independent siblings — both render at once when unconfigured.
		expect(screen.getByText('Top Games Today')).toBeInTheDocument();
		expect(screen.getByText('No teams configured yet — tap "Edit teams" to follow one.')).toBeInTheDocument();
	});

	it('shows a hint when a configured team has no upcoming games', () => {
		const data = { ...baseData, todays_games: [], upcoming_games: [] };

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('No upcoming games scheduled.')).toBeInTheDocument();
		// The today section is hidden entirely (no hint) when empty — most
		// days no followed team plays, so a daily "nothing today" line
		// would just be noise.
		expect(screen.queryByText("My Team's Games Today")).not.toBeInTheDocument();
	});

	it('shows a team-fetch error banner without hiding games from other teams', () => {
		const data = {
			...baseData,
			teams: [
				{ league: 'nfl', league_label: 'NFL', team: 'DAL', team_name: 'Dallas Cowboys', error: 'Unknown team.' },
				{ league: 'nba', league_label: 'NBA', team: 'LAL', team_name: 'Los Angeles Lakers' },
			],
			todays_games: [],
			upcoming_games: [
				makeGame({ league: 'nba', league_label: 'NBA', team: 'Los Angeles Lakers', opponent: 'New York Giants' }),
			],
		};

		const { container } = render(SportsDetail, { props: { data } });

		expect(screen.getByText("Couldn't load: Dallas Cowboys (NFL)")).toBeInTheDocument();
		expect(container.textContent).toContain('Los Angeles Lakers: @ New York Giants');
	});

	it('opens the editor prefilled with the current teams', async () => {
		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));

		const selects = await screen.findAllByRole('combobox');
		expect(selects[0]).toHaveValue('nfl');
		await vi.waitFor(() => expect(selects[1]).toHaveValue('DAL'));
	});

	it('opens the editor prefilled with the current trending leagues', async () => {
		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));

		expect(screen.getByLabelText('NFL')).toBeChecked();
		expect(screen.getByLabelText('NBA')).toBeChecked();
		expect(screen.getByLabelText('College Basketball (Men)')).not.toBeChecked();
		expect(screen.getByLabelText('College Basketball (Women)')).not.toBeChecked();
	});

	it('toggles a trending league checkbox and saves the updated selection', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByLabelText('NHL'));
		await fireEvent.click(screen.getByLabelText('College Basketball (Men)'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		const [, payload] = updateWidgetSettings.mock.calls[0];
		expect(new Set(payload.trending_leagues)).toEqual(
			new Set(['nfl', 'nba', 'mlb', 'college-football', 'wnba', 'college-basketball-men']),
		);
	});

	it('lets the user add a team row, edit it, and save', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			configured: true,
			teams: [...baseData.teams, { league: 'nba', league_label: 'NBA', team: 'LAL', team_name: 'Los Angeles Lakers' }],
			todays_games: [],
			trending: [],
			upcoming_games: baseData.upcoming_games,
			trending_leagues: baseData.trending_leagues,
		});

		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('+ Add team'));

		let selects = screen.getAllByRole('combobox');
		expect(selects).toHaveLength(4);

		await fireEvent.change(selects[2], { target: { value: 'nba' } });
		selects = screen.getAllByRole('combobox');
		await vi.waitFor(() => expect(selects[3]).not.toBeDisabled());
		await fireEvent.change(selects[3], { target: { value: 'LAL' } });

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('sports', {
			teams: [
				{ league: 'nfl', team: 'DAL' },
				{ league: 'nba', team: 'LAL' },
			],
			trending_leagues: expect.arrayContaining(baseData.trending_leagues),
		});
		expect(widgetDetail).toHaveBeenCalledWith('sports');
	});

	it('drops blank team rows when saving', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('+ Add team'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('sports', {
			teams: [{ league: 'nfl', team: 'DAL' }],
			trending_leagues: expect.arrayContaining(baseData.trending_leagues),
		});
	});

	it('removes a team row when its remove button is clicked', async () => {
		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		expect(screen.getAllByRole('combobox')).toHaveLength(2);

		await fireEvent.click(screen.getByLabelText('Remove team'));

		expect(screen.queryAllByRole('combobox')).toHaveLength(0);
		expect(screen.getByText('No teams yet — add one below.')).toBeInTheDocument();
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(SportsDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update sports settings.')).toBeInTheDocument();
	});

	it('renders trending games with ranks and broadcast links', () => {
		const data = { ...baseData, trending: [makeTrendingGame()] };

		const { container } = render(SportsDetail, { props: { data } });

		expect(screen.getByText('Top Games Today')).toBeInTheDocument();
		// The team names are each wrapped in their own <a>, so the combined
		// matchup text is split across elements — check the rendered output
		// rather than a single node.
		expect(container.textContent).toContain('#1 Ohio State Buckeyes @ #3 Texas Longhorns');
		expect(screen.getByText('ABC')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'ABC' })).not.toBeInTheDocument();
	});

	it('surfaces trending errors without hiding the games that did load', () => {
		const data = {
			...baseData,
			trending: [makeTrendingGame()],
			trending_errors: [{ league: 'nba', error: 'ESPN request failed.' }],
		};

		render(SportsDetail, { props: { data } });

		expect(screen.getByText("Couldn't load: nba")).toBeInTheDocument();
		expect(screen.getByText(/Ohio State Buckeyes/)).toBeInTheDocument();
	});

	it('does not render the trending section when there are no trending games', () => {
		render(SportsDetail, { props: { data: baseData } });

		expect(screen.queryByText('Top Games Today')).not.toBeInTheDocument();
	});

	it('renders today, top, and upcoming sections in that order', () => {
		const data = {
			configured: true,
			teams: baseData.teams,
			todays_games: [makeGame({ id: '1' })],
			trending: [makeTrendingGame({ id: '2' })],
			upcoming_games: [makeGame({ id: '3', opponent: 'Chicago Bears', home_team: 'Chicago Bears' })],
			trending_leagues: baseData.trending_leagues,
		};

		render(SportsDetail, { props: { data } });

		const today = screen.getByText("My Team's Games Today");
		const top = screen.getByText('Top Games Today');
		const upcoming = screen.getByText("My Team's Upcoming Games");

		// DOM order: today's section heading appears before top games, which
		// appears before the upcoming section heading.
		expect(today.compareDocumentPosition(top) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
		expect(top.compareDocumentPosition(upcoming) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
	});

	it("does not duplicate a followed team's today game inside the top games section", () => {
		// Dedup between todays_games and trending happens server-side; the
		// component just needs to render each list as given without merging
		// them.
		const data = {
			configured: true,
			teams: baseData.teams,
			todays_games: [makeGame({ id: '10' })],
			trending: [makeTrendingGame({ id: '11' })],
			upcoming_games: [],
			trending_leagues: baseData.trending_leagues,
		};

		const { container } = render(SportsDetail, { props: { data } });

		const occurrences = (container.textContent ?? '').split('Dallas Cowboys: @ New York Giants').length - 1;
		expect(occurrences).toBe(1);
	});
});
