import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import RSSTile from './RSSTile.svelte';

describe('RSSTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(RSSTile, { props: { widgetId: 'rss' } });

		expect(screen.getByText('Loading headlines…')).toBeInTheDocument();
	});

	it('renders the fetched headlines under their widget title', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Tech News',
			items: [
				{ title: 'First headline', link: 'https://example.com/1', source: 'Feed One' },
				{ title: 'Second headline', link: 'https://example.com/2', source: 'Feed One' },
			],
		});

		render(RSSTile, { props: { widgetId: 'rss' } });

		expect(await screen.findByText('First headline')).toBeInTheDocument();
		expect(screen.getByText('Second headline')).toBeInTheDocument();
		expect(screen.getByText('Tech News')).toBeInTheDocument();
	});

	it('falls back to "Headlines" when no title is set', async () => {
		widgetSummary.mockResolvedValue({
			items: [{ title: 'First headline', link: 'https://example.com/1', source: 'Feed One' }],
		});

		render(RSSTile, { props: { widgetId: 'rss' } });

		expect(await screen.findByText('Headlines')).toBeInTheDocument();
	});
});
