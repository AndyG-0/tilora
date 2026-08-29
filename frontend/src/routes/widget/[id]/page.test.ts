import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { renameWidget, goto } = vi.hoisted(() => ({
	renameWidget: vi.fn(),
	goto: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { renameWidget } }));
vi.mock('$app/navigation', () => ({ goto }));

import Page from './+page.svelte';

vi.mock('$lib/widgetComponents', () => ({
	DETAIL_COMPONENTS: { stub: () => import('./widget-detail.test-stub.svelte') },
}));

const baseData = {
	widgetId: 'weather-b',
	type: 'weather',
	name: 'Weather (Chicago, IL) (2)',
	detail: {},
};

describe('widget detail page — rename control', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('displays the current display name', () => {
		render(Page, { props: { data: baseData } });

		expect(screen.getByText('Weather (Chicago, IL) (2)')).toBeInTheDocument();
	});

	it('lets the user edit and save a new name', async () => {
		renameWidget.mockResolvedValue({ id: 'weather-b', name: 'Kitchen Weather' });
		render(Page, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Rename'));
		const input = await screen.findByLabelText('Tile name');
		expect(input).toHaveValue('Weather (Chicago, IL) (2)');

		await fireEvent.input(input, { target: { value: 'Kitchen Weather' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(renameWidget).toHaveBeenCalledWith('weather-b', 'Kitchen Weather'));
		expect(await screen.findByText('Kitchen Weather')).toBeInTheDocument();
	});

	it('cancels editing without saving', async () => {
		render(Page, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Rename'));
		const input = await screen.findByLabelText('Tile name');
		await fireEvent.input(input, { target: { value: 'Something else' } });

		await fireEvent.click(screen.getByText('Cancel'));

		expect(renameWidget).not.toHaveBeenCalled();
		expect(screen.getByText('Weather (Chicago, IL) (2)')).toBeInTheDocument();
	});

	it('clears the override and reverts to the auto-computed name on empty submission', async () => {
		renameWidget.mockResolvedValue({ id: 'weather-b', name: 'Weather (Chicago, IL) (2)' });
		render(Page, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Rename'));
		const input = await screen.findByLabelText('Tile name');
		await fireEvent.input(input, { target: { value: '' } });
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(renameWidget).toHaveBeenCalledWith('weather-b', ''));
		expect(await screen.findByText('Weather (Chicago, IL) (2)')).toBeInTheDocument();
	});

	it('shows an error and keeps editing open if the save fails', async () => {
		renameWidget.mockRejectedValue(new Error('boom'));
		render(Page, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Rename'));
		const input = await screen.findByLabelText('Tile name');
		await fireEvent.input(input, { target: { value: 'Kitchen Weather' } });
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Name must be 60 characters or fewer.')).toBeInTheDocument();
		expect(screen.getByLabelText('Tile name')).toBeInTheDocument();
	});
});

describe('widget detail page — remounting the Detail component on navigation', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows the new widget’s data instead of the previous widget’s stale state', async () => {
		// Regression test: SvelteKit reuses this route's component instance
		// across navigations between two widget detail pages (only `load()`
		// re-runs) — a Detail component that seeds local state once,
		// non-reactively, from its initial `data` prop (like PhotoDetail.svelte)
		// would otherwise keep showing the previously-viewed widget's data.
		const tileA = { widgetId: 'photos-a', type: 'stub', name: 'Tile A', detail: { label: 'Tile A photos' } };
		const tileB = { widgetId: 'photos-b', type: 'stub', name: 'Tile B', detail: { label: 'Tile B photos' } };

		const { rerender } = render(Page, { props: { data: tileA } });
		expect(await screen.findByTestId('detail-label')).toHaveTextContent('Tile A photos');

		await rerender({ data: tileB });

		expect(await screen.findByTestId('detail-label')).toHaveTextContent('Tile B photos');
	});
});
