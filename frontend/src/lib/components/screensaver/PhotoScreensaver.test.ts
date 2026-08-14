import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

import PhotoScreensaver from './PhotoScreensaver.svelte';

function photo(filename: string) {
	return { filename, url: `/api/photos/${filename}` };
}

const baseData = {
	count: 3,
	interval_seconds: 5,
	photos: [photo('a.jpg'), photo('b.jpg'), photo('c.jpg')],
};

describe('PhotoScreensaver', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
	});

	it('starts at photo 0 with no stored cursor', async () => {
		render(PhotoScreensaver, { props: { id: 'photos-1', data: baseData } });

		expect((await screen.findByAltText('a.jpg')) as HTMLImageElement).toHaveAttribute(
			'src',
			'http://api.test/api/photos/a.jpg',
		);
	});

	it('resumes from a previously stored cursor for the same widget id', async () => {
		localStorage.setItem('screensaver:cursor:photos-1', '2');

		render(PhotoScreensaver, { props: { id: 'photos-1', data: baseData } });

		expect(await screen.findByAltText('c.jpg')).toBeInTheDocument();
	});

	it('persists the cursor to localStorage as it auto-advances', async () => {
		render(PhotoScreensaver, { props: { id: 'photos-1', data: baseData } });

		await screen.findByAltText('a.jpg');
		await vi.advanceTimersByTimeAsync(5000);

		expect(await screen.findByAltText('b.jpg')).toBeInTheDocument();
		expect(localStorage.getItem('screensaver:cursor:photos-1')).toBe('1');
	});

	it('clamps an out-of-range stored cursor instead of rendering blank', async () => {
		localStorage.setItem('screensaver:cursor:photos-1', '99');

		render(PhotoScreensaver, { props: { id: 'photos-1', data: baseData } });

		expect(await screen.findByAltText('a.jpg')).toBeInTheDocument();
	});

	it('keys the stored cursor by widget id, not globally', async () => {
		localStorage.setItem('screensaver:cursor:photos-1', '2');

		render(PhotoScreensaver, { props: { id: 'photos-2', data: baseData } });

		expect(await screen.findByAltText('a.jpg')).toBeInTheDocument();
	});
});
