import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail, sportsTeams } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	sportsTeams: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail, sportsTeams } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'sports' } } }));

import SportsDetail from './SportsDetail.svelte';

const baseData = {
	configured: true,
	teams: [
		{
			league: 'nfl',
			league_label: 'NFL',
			team: 'DAL',
			team_name: 'Dallas Cowboys',
			games: [
				{
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
				},
			],
		},
	],
	trending: [],
	trending_leagues: ['nfl', 'nba', 'mlb', 'nhl', 'college-football', 'wnba'],
};

const trendingGame = {
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
	away_team: 'Ohio State Buckeyes',
	away_abbreviation: 'OSU',
	away_rank: 1,
	home_score: null,
	away_score: null,
	broadcast_links: [{ name: 'ABC', url: null }],
	venue: 'Darrell K Royal Stadium',
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

	it('renders each followed team with its upcoming games', () => {
		render(SportsDetail, { props: { data: baseData } });

		expect(screen.getByText('Sports Schedule')).toBeInTheDocument();
		expect(screen.getByText('Dallas Cowboys')).toBeInTheDocument();
		expect(screen.getByText('NFL')).toBeInTheDocument();
		expect(screen.getByText('@ New York Giants')).toBeInTheDocument();
		expect(screen.getByText('NBC')).toBeInTheDocument();
		expect(screen.getByRole('link', { name: 'NBC' })).toHaveAttribute('href', 'https://www.nbc.com/live');
		expect(screen.getByText('MetLife Stadium')).toBeInTheDocument();
	});

	it('renders an unknown broadcast name as plain text, not a link', () => {
		const data = {
			configured: true,
			teams: [
				{
					...baseData.teams[0],
					games: [
						{
							...baseData.teams[0].games[0],
							broadcasts: ['Regional Sports Network'],
							broadcast_links: [{ name: 'Regional Sports Network', url: null }],
						},
					],
				},
			],
			trending: [],
			trending_leagues: [],
		};

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('Regional Sports Network')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'Regional Sports Network' })).not.toBeInTheDocument();
	});

	it('shows a hint when no teams are configured', () => {
		render(SportsDetail, {
			props: { data: { configured: false, teams: [], trending: [], trending_leagues: [] } },
		});

		expect(screen.getByText('No teams configured yet — tap "Edit teams" to follow one.')).toBeInTheDocument();
	});

	it('shows a per-team hint when a team has no upcoming games', () => {
		const data = {
			configured: true,
			teams: [{ ...baseData.teams[0], games: [] }],
			trending: [],
			trending_leagues: [],
		};

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('No upcoming games scheduled.')).toBeInTheDocument();
	});

	it('shows a per-team error without hiding the other teams', () => {
		const data = {
			configured: true,
			teams: [
				{ ...baseData.teams[0], error: 'Unknown team.', games: [] },
				{
					league: 'nba',
					league_label: 'NBA',
					team: 'LAL',
					team_name: 'Los Angeles Lakers',
					games: [],
				},
			],
			trending: [],
			trending_leagues: [],
		};

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('Unknown team.')).toBeInTheDocument();
		expect(screen.getByText('Los Angeles Lakers')).toBeInTheDocument();
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
			teams: [
				...baseData.teams,
				{ league: 'nba', league_label: 'NBA', team: 'LAL', team_name: 'Los Angeles Lakers', games: [] },
			],
			trending: [],
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
		const data = { ...baseData, trending: [trendingGame] };

		render(SportsDetail, { props: { data } });

		expect(screen.getByText('Top Games Today')).toBeInTheDocument();
		expect(screen.getByText(/#1 Ohio State Buckeyes @ #3 Texas Longhorns/)).toBeInTheDocument();
		expect(screen.getByText('ABC')).toBeInTheDocument();
		expect(screen.queryByRole('link', { name: 'ABC' })).not.toBeInTheDocument();
	});

	it('surfaces trending errors without hiding the games that did load', () => {
		const data = {
			...baseData,
			trending: [trendingGame],
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
});
