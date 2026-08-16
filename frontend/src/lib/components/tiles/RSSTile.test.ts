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
});
