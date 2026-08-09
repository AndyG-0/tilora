import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({
	widgetSummary: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import NASATile from './NASATile.svelte';

describe('NASATile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(NASATile, { props: { widgetId: 'nasa_apod' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders the picture title and date for an image day', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Astronomy Picture of the Day',
			available: true,
			apod_title: 'A Beautiful Nebula',
			date: '2026-08-05',
			media_type: 'image',
			thumbnail_url: 'https://apod.nasa.gov/apod/image/nebula.jpg',
		});

		const { container } = render(NASATile, { props: { widgetId: 'nasa_apod' } });

		expect(await screen.findByText('A Beautiful Nebula')).toBeInTheDocument();
		expect(screen.getByText('2026-08-05')).toBeInTheDocument();
		expect(container.querySelector('img')).toHaveAttribute('src', 'https://apod.nasa.gov/apod/image/nebula.jpg');
		expect(screen.queryByText('Cached')).not.toBeInTheDocument();
	});

	it('shows a stale badge when the summary is a cached fallback', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Astronomy Picture of the Day',
			available: true,
			apod_title: 'A Beautiful Nebula',
			date: '2026-08-05',
			media_type: 'image',
			thumbnail_url: 'https://apod.nasa.gov/apod/image/nebula.jpg',
			stale: true,
			fetched_at: '2026-08-05T12:00:00Z',
		});

		render(NASATile, { props: { widgetId: 'nasa_apod' } });

		expect(await screen.findByText('A Beautiful Nebula')).toBeInTheDocument();
		expect(screen.getByText('Cached')).toBeInTheDocument();
	});

	it('renders the youtube thumbnail for a video day', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Astronomy Picture of the Day',
			available: true,
			apod_title: 'A Cool Video',
			date: '2026-08-06',
			media_type: 'video',
			thumbnail_url: 'https://img.youtube.com/vi/abc123/0.jpg',
		});

		const { container } = render(NASATile, { props: { widgetId: 'nasa_apod' } });

		expect(await screen.findByText('A Cool Video')).toBeInTheDocument();
		expect(container.querySelector('img')).toHaveAttribute('src', 'https://img.youtube.com/vi/abc123/0.jpg');
	});

	it('shows an unavailable state when the plugin could not fetch the picture', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Astronomy Picture of the Day',
			available: false,
		});

		render(NASATile, { props: { widgetId: 'nasa_apod' } });

		expect(await screen.findByText('Picture of the day unavailable')).toBeInTheDocument();
	});
});
