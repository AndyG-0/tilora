import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail, movieProviders } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
	movieProviders: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail, movieProviders } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'movies' } } }));

import MovieDetail from './MovieDetail.svelte';

const movie = {
	id: 1,
	title: 'A Movie',
	release_date: '2024-01-01',
	rating: 8.456,
	poster_url: 'https://example.com/a.jpg',
	overview: 'An overview.',
	where_to_watch: [
		{ name: 'Netflix', logo_url: null, url: 'https://www.netflix.com' },
		{ name: 'Hulu', logo_url: null, url: 'https://www.hulu.com' },
	],
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

const baseData = {
	popular_movies: [],
	popular_tv_shows: [],
	trending_movies: [],
	trending_tv_shows: [],
	on_streaming_movies: [],
	on_streaming_tv_shows: [],
	region: 'US',
	categories: ['popular_movies', 'popular_tv', 'trending_movies', 'trending_tv', 'on_streaming'],
	providers: [],
};

describe('MovieDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		movieProviders.mockResolvedValue([
			{ id: 8, name: 'Netflix', logo_url: 'https://example.com/netflix.png' },
			{ id: 337, name: 'Disney Plus', logo_url: null },
		]);
	});

	it('only renders sections that have entries', () => {
		render(MovieDetail, { props: { data: { ...baseData, popular_movies: [movie] } } });

		expect(screen.getByText('Popular Movies')).toBeInTheDocument();
		expect(screen.queryByText('Popular Shows')).not.toBeInTheDocument();
		expect(screen.queryByText('Trending Movies')).not.toBeInTheDocument();
		expect(screen.queryByText('On Streaming: Movies')).not.toBeInTheDocument();
	});

	it('renders a movie with its rating, release date, and streaming providers', () => {
		render(MovieDetail, { props: { data: { ...baseData, popular_movies: [movie] } } });

		expect(screen.getByText('A Movie')).toBeInTheDocument();
		expect(screen.getByAltText('A Movie')).toBeInTheDocument();
		expect(screen.getByText(/2024-01-01/)).toBeInTheDocument();
		expect(screen.getByText(/8\.5★/)).toBeInTheDocument();
		expect(screen.getByText('Streaming in US on:')).toBeInTheDocument();
		const netflixLink = screen.getByRole('link', { name: /Netflix/ });
		expect(netflixLink).toHaveAttribute('href', 'https://www.netflix.com');
		const huluLink = screen.getByRole('link', { name: /Hulu/ });
		expect(huluLink).toHaveAttribute('href', 'https://www.hulu.com');
	});

	it('falls back to placeholders when release date/rating are missing and shows a not-streaming hint', () => {
		render(MovieDetail, { props: { data: { ...baseData, popular_tv_shows: [noProvidersMovie] } } });

		expect(screen.getByText(/Unknown release date/)).toBeInTheDocument();
		expect(screen.getByText('Not currently streaming in US')).toBeInTheDocument();
		expect(screen.queryByAltText('No Providers')).not.toBeInTheDocument();
	});

	it('renders the on-streaming sections distinctly from popular/trending', () => {
		render(MovieDetail, {
			props: { data: { ...baseData, on_streaming_movies: [movie], trending_tv_shows: [noProvidersMovie] } },
		});

		expect(screen.getByText('On Streaming: Movies')).toBeInTheDocument();
		expect(screen.getByText('Trending Shows')).toBeInTheDocument();
	});

	it('preselects the widget’s currently configured categories and providers when opening the editor', async () => {
		render(MovieDetail, {
			props: { data: { ...baseData, categories: ['popular_movies', 'on_streaming'], providers: [8] } },
		});

		await fireEvent.click(screen.getByText('Edit settings'));

		expect(await screen.findByLabelText('Popular Movies')).toBeChecked();
		expect(screen.getByLabelText('Popular Shows')).not.toBeChecked();
		expect(screen.getByLabelText('On Streaming (Movies & Shows)')).toBeChecked();
		expect(await screen.findByText('Netflix')).toBeInTheDocument();
	});

	it('lets the user toggle a category and save', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, categories: ['popular_tv'] });

		render(MovieDetail, { props: { data: { ...baseData, categories: ['popular_movies'] } } });

		await fireEvent.click(screen.getByText('Edit settings'));
		const popularShows = await screen.findByLabelText('Popular Shows');
		await fireEvent.click(popularShows);
		const popularMovies = screen.getByLabelText('Popular Movies');
		await fireEvent.click(popularMovies);

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('movies', { categories: ['popular_tv'], providers: [] });
		expect(widgetDetail).toHaveBeenCalledWith('movies');
	});

	it('lets the user pick a streaming provider chip and save', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({ ...baseData, providers: [8] });

		render(MovieDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		const netflixChip = await screen.findByText('Netflix');
		await fireEvent.click(netflixChip);

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('movies', {
			categories: baseData.categories,
			providers: [8],
		});
	});

	it('shows an error message if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(MovieDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit settings'));
		await screen.findByText('Netflix');
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update settings.')).toBeInTheDocument();
	});

	it('shows not configured state when configured is false and no items', () => {
		render(MovieDetail, { props: { data: { ...baseData, configured: false } } });

		expect(screen.getByText('Not configured')).toBeInTheDocument();
	});

	it('shows no data yet state when configured is true and no items', () => {
		render(MovieDetail, { props: { data: { ...baseData, configured: true } } });

		expect(screen.getByText(/No data yet/)).toBeInTheDocument();
	});
});
