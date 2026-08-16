import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import MovieTile from './MovieTile.svelte';

describe('MovieTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(MovieTile, { props: { widgetId: 'movies', refreshIntervalSeconds: 60 } });

		expect(screen.getByText('Movies & Shows')).toBeInTheDocument();
		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders only sections that have entries', async () => {
		widgetSummary.mockResolvedValue({
			popular_movies: [{ id: 1, title: 'A Movie', poster_url: 'https://example.com/a.jpg' }],
		});

		render(MovieTile, { props: { widgetId: 'movies', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Popular Movies')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.queryByText('Popular Shows')).not.toBeInTheDocument();
		expect(screen.queryByText('Trending Movies')).not.toBeInTheDocument();
		expect(screen.queryByText('Trending Shows')).not.toBeInTheDocument();
	});

	it('renders all six sections when populated, skipping entries without a poster', async () => {
		widgetSummary.mockResolvedValue({
			popular_movies: [{ id: 1, title: 'A Movie', poster_url: 'https://example.com/a.jpg' }],
			popular_tv_shows: [{ id: 2, title: 'No Poster Show', poster_url: null }],
			trending_movies: [{ id: 3, title: 'Trending Movie', poster_url: 'https://example.com/c.jpg' }],
			trending_tv_shows: [{ id: 4, title: 'Trending Show', poster_url: 'https://example.com/d.jpg' }],
			on_streaming_movies: [{ id: 5, title: 'Streaming Movie', poster_url: 'https://example.com/e.jpg' }],
			on_streaming_tv_shows: [{ id: 6, title: 'Streaming Show', poster_url: 'https://example.com/f.jpg' }],
		});

		render(MovieTile, { props: { widgetId: 'movies', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Popular Movies')).toBeInTheDocument();
		expect(screen.getByText('Popular Shows')).toBeInTheDocument();
		expect(screen.getByText('Trending Movies')).toBeInTheDocument();
		expect(screen.getByText('Trending Shows')).toBeInTheDocument();
		expect(screen.getByText('On Streaming: Movies')).toBeInTheDocument();
		expect(screen.getByText('On Streaming: Shows')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.queryByAltText('No Poster Show')).not.toBeInTheDocument();
		expect(screen.getByAltText('Trending Show')).toBeInTheDocument();
		expect(screen.getByAltText('Streaming Movie')).toBeInTheDocument();
	});
});
