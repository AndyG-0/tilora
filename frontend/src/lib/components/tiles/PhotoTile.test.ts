import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

vi.mock('$env/dynamic/public', () => ({ env: { PUBLIC_API_BASE_URL: 'http://api.test' } }));

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import PhotoTile from './PhotoTile.svelte';

describe('PhotoTile', () => {
	it('renders the current photo and count', async () => {
		widgetSummary.mockResolvedValue({
			count: 3,
			current: { filename: 'a.jpg', url: '/api/photos/photos/a.jpg' },
		});

		render(PhotoTile, { props: { widgetId: 'photos' } });

		const img = await screen.findByAltText('');
		expect(img).toHaveAttribute('src', 'http://api.test/api/photos/photos/a.jpg');
		expect(screen.getByText('3 photos')).toBeInTheDocument();
	});

	it('shows a no-photos-found hint when there is no current photo', async () => {
		widgetSummary.mockResolvedValue({ count: 0, current: null });

		render(PhotoTile, { props: { widgetId: 'photos' } });

		expect(await screen.findByText('No photos found')).toBeInTheDocument();
	});

	it('shows an indexing hint while the first scan is still running', async () => {
		widgetSummary.mockResolvedValue({ count: 0, current: null, indexing: true });

		render(PhotoTile, { props: { widgetId: 'photos' } });

		expect(await screen.findByText('Indexing…')).toBeInTheDocument();
	});

	it('shows the index error when the last scan failed', async () => {
		widgetSummary.mockResolvedValue({
			count: 0,
			current: null,
			index_error: 'could not reach the source',
		});

		render(PhotoTile, { props: { widgetId: 'photos' } });

		expect(await screen.findByText('could not reach the source')).toBeInTheDocument();
	});
});
