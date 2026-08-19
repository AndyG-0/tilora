import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import RSSTile from './RSSTile.svelte';

describe('RSSTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading headlines…')).toBeInTheDocument();
	});

	it('renders the fetched headlines under their widget title', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Tech News',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [
						{ title: 'First headline', link: 'https://example.com/1', source: 'Feed One' },
						{ title: 'Second headline', link: 'https://example.com/2', source: 'Feed One' },
					],
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('First headline')).toBeInTheDocument();
		expect(screen.getByText('Second headline')).toBeInTheDocument();
		expect(screen.getByText('Tech News')).toBeInTheDocument();
	});

	it('falls back to "Headlines" when no title is set', async () => {
		widgetSummary.mockResolvedValue({
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [{ title: 'First headline', link: 'https://example.com/1', source: 'Feed One' }],
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Headlines')).toBeInTheDocument();
	});

	it('labels each group with its feed name when a tile shows multiple feeds', async () => {
		widgetSummary.mockResolvedValue({
			title: 'News',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [{ title: 'From one', link: 'https://example.com/1', source: 'Feed One' }],
				},
				{
					feed_id: 2,
					name: 'Feed Two',
					items: [{ title: 'From two', link: 'https://example.com/2', source: 'Feed Two' }],
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Feed One')).toBeInTheDocument();
		expect(screen.getByText('Feed Two')).toBeInTheDocument();
	});

	it('does not show a group label when the tile has only one feed', async () => {
		widgetSummary.mockResolvedValue({
			title: 'News',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [{ title: 'From one', link: 'https://example.com/1', source: 'Feed One' }],
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		await screen.findByText('From one');
		expect(screen.queryByText('Feed One')).not.toBeInTheDocument();
	});

	it('renders an error notice when a single feed fails to load', async () => {
		widgetSummary.mockResolvedValue({
			title: 'News',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [],
					error: 'This feed could not be loaded.',
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('This feed could not be loaded.')).toBeInTheDocument();
		expect(screen.getByText('News')).toBeInTheDocument();
		// Feed name prefix is omitted for single-feed tiles
		expect(screen.queryByText('Feed One:')).not.toBeInTheDocument();
		expect(screen.queryByText('Loading headlines…')).not.toBeInTheDocument();
	});

	it('shows the error notice at the top with feed label when one feed fails among multiple feeds', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Multi News',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Broken Feed',
					items: [],
					error: 'This feed could not be loaded.',
				},
				{
					feed_id: 2,
					name: 'Working Feed',
					items: [{ title: 'Working headline', link: 'https://example.com/work', source: 'Working Feed' }],
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Broken Feed:')).toBeInTheDocument();
		expect(screen.getByText('This feed could not be loaded.')).toBeInTheDocument();
		expect(screen.getByText('Working headline')).toBeInTheDocument();
		expect(screen.getByText('Working Feed')).toBeInTheDocument();
	});

	it('shows multiple error notices when all configured feeds fail', async () => {
		widgetSummary.mockResolvedValue({
			title: 'All Broken',
			feed_groups: [
				{
					feed_id: 1,
					name: 'Feed One',
					items: [],
					error: 'This feed could not be loaded.',
				},
				{
					feed_id: 2,
					name: 'Feed Two',
					items: [],
					error: 'Connection timed out.',
				},
			],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Feed One:')).toBeInTheDocument();
		expect(screen.getByText('This feed could not be loaded.')).toBeInTheDocument();
		expect(screen.getByText('Feed Two:')).toBeInTheDocument();
		expect(screen.getByText('Connection timed out.')).toBeInTheDocument();
		expect(screen.queryByText('Loading headlines…')).not.toBeInTheDocument();
	});

	it('shows empty hint when no feeds are selected', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Headlines',
			feed_groups: [],
		});

		render(RSSTile, { props: { widgetId: 'rss', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No feeds selected yet — tap "Edit feeds" to choose one.')).toBeInTheDocument();
	});
});
