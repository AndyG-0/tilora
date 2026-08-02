import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import SportsTile from './SportsTile.svelte';

describe('SportsTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-configured hint', async () => {
		widgetSummary.mockResolvedValue({ configured: false, games: [], trending: [] });

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('No teams configured')).toBeInTheDocument();
	});

	it('shows a no-upcoming-games hint when configured but empty', async () => {
		widgetSummary.mockResolvedValue({ configured: true, games: [], trending: [] });

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('No upcoming games')).toBeInTheDocument();
	});

	it('renders the next game per team with broadcast info', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
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
					league: 'nfl',
					league_label: 'NFL',
					team: 'Dallas Cowboys',
				},
			],
			trending: [],
		});

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('Dallas Cowboys @ New York Giants')).toBeInTheDocument();
		expect(screen.getByText('NFL')).toBeInTheDocument();
		expect(screen.getByText('NBC')).toBeInTheDocument();
	});

	it('shows a live badge with the status detail for in-progress games', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
			games: [
				{
					id: '2',
					date: '2026-09-14T00:20Z',
					state: 'in',
					completed: false,
					status_detail: 'Q3 4:12',
					home_team: 'New York Giants',
					home_abbreviation: 'NYG',
					away_team: 'Dallas Cowboys',
					away_abbreviation: 'DAL',
					home_score: '10',
					away_score: '14',
					broadcasts: [],
					broadcast_links: [],
					venue: null,
					is_home: false,
					opponent: 'New York Giants',
					league: 'nfl',
					league_label: 'NFL',
					team: 'Dallas Cowboys',
				},
			],
			trending: [],
		});

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('Live — Q3 4:12')).toBeInTheDocument();
	});

	it('renders trending games below followed teams with a section label for each', async () => {
		widgetSummary.mockResolvedValue({
			configured: true,
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
					broadcasts: [],
					broadcast_links: [],
					venue: null,
					is_home: false,
					opponent: 'New York Giants',
					league: 'nfl',
					league_label: 'NFL',
					team: 'Dallas Cowboys',
				},
			],
			trending: [
				{
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
				},
			],
		});

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('Your Teams')).toBeInTheDocument();
		expect(screen.getByText('Top Games Today')).toBeInTheDocument();
		expect(screen.getByText('#1 Ohio State Buckeyes @ #3 Texas Longhorns')).toBeInTheDocument();
	});

	it('renders trending games even when no teams are configured', async () => {
		widgetSummary.mockResolvedValue({
			configured: false,
			games: [],
			trending: [
				{
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
				},
			],
		});

		render(SportsTile, { props: { widgetId: 'sports' } });

		expect(await screen.findByText('#1 Ohio State Buckeyes @ #3 Texas Longhorns')).toBeInTheDocument();
		expect(screen.queryByText('No teams configured')).not.toBeInTheDocument();
		// No "Your Teams" section renders when there are no followed teams, and with
		// only one section present the redundant "Top Games Today" label is skipped too.
		expect(screen.queryByText('Your Teams')).not.toBeInTheDocument();
		expect(screen.queryByText('Top Games Today')).not.toBeInTheDocument();
	});
});
