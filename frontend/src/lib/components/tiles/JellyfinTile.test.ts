import { render, screen } from '@testing-library/svelte';
import { fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary, jellyfinImageUrl, jellyfinStreamUrl } = vi.hoisted(() => ({
	widgetSummary: vi.fn(),
	jellyfinImageUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/image`),
	jellyfinStreamUrl: vi.fn((widgetId: string, id: string) => `https://example.com/${widgetId}/${id}/stream`),
}));
vi.mock('$lib/api', () => ({ api: { widgetSummary, jellyfinImageUrl, jellyfinStreamUrl } }));

import JellyfinTile from './JellyfinTile.svelte';

describe('JellyfinTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(JellyfinTile, { props: { widgetId: 'jellyfin' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('shows a not-connected state', async () => {
		widgetSummary.mockResolvedValue({ connected: false, recent_items: [] });

		render(JellyfinTile, { props: { widgetId: 'jellyfin' } });

		expect(await screen.findByText('Not connected')).toBeInTheDocument();
	});

	it('shows an empty state when connected with no recent items', async () => {
		widgetSummary.mockResolvedValue({ connected: true, recent_items: [] });

		render(JellyfinTile, { props: { widgetId: 'jellyfin' } });

		expect(await screen.findByText('No recently added items')).toBeInTheDocument();
	});

	it('renders posters only for items that have one', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			recent_items: [
				{ id: '1', name: 'Movie With Poster', has_poster: true },
				{ id: '2', name: 'Movie Without Poster', has_poster: false },
			],
		});

		render(JellyfinTile, { props: { widgetId: 'jellyfin' } });

		expect(await screen.findByAltText('Movie With Poster')).toBeInTheDocument();
		expect(screen.queryByAltText('Movie Without Poster')).not.toBeInTheDocument();
	});

	it('opens the player when a poster is clicked, and closes it', async () => {
		widgetSummary.mockResolvedValue({
			connected: true,
			recent_items: [{ id: '1', name: 'Movie With Poster', has_poster: true }],
		});

		render(JellyfinTile, { props: { widgetId: 'jellyfin' } });
		const poster = await screen.findByRole('button', { name: 'Play Movie With Poster' });

		await fireEvent.click(poster);

		expect(screen.getByRole('dialog', { name: 'Movie With Poster' })).toBeInTheDocument();

		await fireEvent.click(screen.getByRole('button', { name: 'Close player' }));

		expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
	});
});
