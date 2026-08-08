import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import NASADetail from './NASADetail.svelte';

const imageDay = {
	title: 'Astronomy Picture of the Day',
	available: true,
	apod_title: 'A Beautiful Nebula',
	explanation: 'Some nebula.',
	url: 'https://apod.nasa.gov/apod/image/nebula.jpg',
	hdurl: 'https://apod.nasa.gov/apod/image/nebula_hd.jpg',
	thumbnail_url: null,
	media_type: 'image',
	date: '2026-08-05',
	copyright: 'Jane Astronomer',
};

const videoDay = {
	title: 'Astronomy Picture of the Day',
	available: true,
	apod_title: 'A Cool Video',
	explanation: 'Some video.',
	url: 'https://www.youtube.com/embed/abc123',
	hdurl: null,
	thumbnail_url: 'https://img.youtube.com/vi/abc123/0.jpg',
	media_type: 'video',
	date: '2026-08-06',
	copyright: null,
};

const unavailable = {
	title: 'Astronomy Picture of the Day',
	available: false,
};

describe('NASADetail', () => {
	it('renders the image, explanation, and copyright for an image day', () => {
		render(NASADetail, { props: { data: imageDay } });

		expect(screen.getByText('A Beautiful Nebula')).toBeInTheDocument();
		expect(screen.getByText('Some nebula.')).toBeInTheDocument();
		expect(screen.getByText('© Jane Astronomer')).toBeInTheDocument();
		expect(screen.getByRole('img')).toHaveAttribute('src', 'https://apod.nasa.gov/apod/image/nebula_hd.jpg');
	});

	it('renders an iframe embed for a video day', () => {
		render(NASADetail, { props: { data: videoDay } });

		expect(screen.getByText('A Cool Video')).toBeInTheDocument();
		expect(screen.getByTitle('A Cool Video')).toHaveAttribute('src', 'https://www.youtube.com/embed/abc123');
		expect(screen.queryByRole('img')).not.toBeInTheDocument();
	});

	it('shows an unavailable hint when the picture could not be fetched', () => {
		render(NASADetail, { props: { data: unavailable } });

		expect(screen.getByText('Picture of the day is unavailable right now.')).toBeInTheDocument();
	});
});
