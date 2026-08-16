import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary } = vi.hoisted(() => ({ goto: vi.fn(), widgetSummary: vi.fn() }));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import BookmarksTile from './BookmarksTile.svelte';

describe('BookmarksTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(BookmarksTile, { props: { widgetId: 'bookmarks', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Loading bookmarks…')).toBeInTheDocument();
	});

	it('renders the fetched bookmarks as links under their widget title', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Links',
			bookmarks: [
				{ name: 'GitHub', url: 'https://github.com' },
				{ name: 'Example', url: 'https://example.com' },
			],
		});

		render(BookmarksTile, { props: { widgetId: 'bookmarks', refreshIntervalSeconds: 60 } });

		const link = await screen.findByText('GitHub');
		expect(link.closest('a')).toHaveAttribute('href', 'https://github.com');
		expect(link.closest('a')).toHaveAttribute('target', '_blank');
		expect(screen.getByText('Example')).toBeInTheDocument();
		expect(screen.getByText('Links')).toBeInTheDocument();
	});

	it('falls back to "Bookmarks" when no title is set', async () => {
		widgetSummary.mockResolvedValue({
			bookmarks: [{ name: 'GitHub', url: 'https://github.com' }],
		});

		render(BookmarksTile, { props: { widgetId: 'bookmarks', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Bookmarks')).toBeInTheDocument();
	});

	it('shows an empty state when there are no bookmarks', async () => {
		widgetSummary.mockResolvedValue({ title: 'Links', bookmarks: [] });

		render(BookmarksTile, { props: { widgetId: 'bookmarks', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No bookmarks yet')).toBeInTheDocument();
	});
});
