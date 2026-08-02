import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import MovieDetail from './MovieDetail.svelte';

const movie = {
	id: 1,
	title: 'A Movie',
	release_date: '2024-01-01',
	rating: 8.456,
	poster_url: 'https://example.com/a.jpg',
	overview: 'An overview.',
	where_to_watch: ['Netflix', 'Hulu'],
};

const noProvidersMovie = {
	id: 2,
	title: 'No Providers',
	release_date: null,
	rating: null,
	poster_url: null,
	overview: 'No providers overview.',
	where_to_watch: [],
};

describe('MovieDetail', () => {
	it('renders the three section headings', () => {
		render(MovieDetail, { props: { data: { movies: [], tv_shows: [], trending_tv_shows: [], region: 'US' } } });

		expect(screen.getByText('Movies')).toBeInTheDocument();
		expect(screen.getByText('Shows')).toBeInTheDocument();
		expect(screen.getByText('Trending')).toBeInTheDocument();
	});

	it('renders a movie with its rating, release date, and streaming providers', () => {
		render(MovieDetail, { props: { data: { movies: [movie], tv_shows: [], trending_tv_shows: [], region: 'US' } } });

		expect(screen.getByText('A Movie')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.getByText(/2024-01-01/)).toBeInTheDocument();
		expect(screen.getByText(/8\.5★/)).toBeInTheDocument();
		expect(screen.getByText('Streaming in US on: Netflix, Hulu')).toBeInTheDocument();
	});

	it('falls back to placeholders when release date/rating are missing and shows a not-streaming hint', () => {
		render(MovieDetail, {
			props: { data: { movies: [], tv_shows: [noProvidersMovie], trending_tv_shows: [], region: 'US' } },
		});

		expect(screen.getByText(/Unknown release date/)).toBeInTheDocument();
		expect(screen.getByText('Not currently streaming in US')).toBeInTheDocument();
		expect(screen.queryByAltText('No Providers')).not.toBeInTheDocument();
	});
});
