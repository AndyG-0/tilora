import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import MovieTile from './MovieTile.svelte';

describe('MovieTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(MovieTile, { props: { widgetId: 'movies' } });

		expect(screen.getByText('Movies & Shows')).toBeInTheDocument();
		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders only sections that have entries', async () => {
		widgetSummary.mockResolvedValue({
			movies: [{ id: 1, title: 'A Movie', poster_url: 'https://example.com/a.jpg' }],
			tv_shows: [],
			trending_tv_shows: [],
		});

		render(MovieTile, { props: { widgetId: 'movies' } });

		expect(await screen.findByText('Movies')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.queryByText('Shows')).not.toBeInTheDocument();
		expect(screen.queryByText('Trending')).not.toBeInTheDocument();
	});

	it('renders all three sections when populated, skipping entries without a poster', async () => {
		widgetSummary.mockResolvedValue({
			movies: [{ id: 1, title: 'A Movie', poster_url: 'https://example.com/a.jpg' }],
			tv_shows: [{ id: 2, title: 'No Poster Show', poster_url: null }],
			trending_tv_shows: [{ id: 3, title: 'Trending Show', poster_url: 'https://example.com/c.jpg' }],
		});

		render(MovieTile, { props: { widgetId: 'movies' } });

		expect(await screen.findByText('Movies')).toBeInTheDocument();
		expect(screen.getByText('Shows')).toBeInTheDocument();
		expect(screen.getByText('Trending')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.queryByAltText('No Poster Show')).not.toBeInTheDocument();
		expect(screen.getByAltText('Trending Show')).toBeInTheDocument();
	});
});
