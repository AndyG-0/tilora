import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail } = vi.hoisted(() => ({
	updateWidgetSettings: vi.fn(),
	widgetDetail: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { updateWidgetSettings, widgetDetail } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'rss' } } }));

import RSSDetail from './RSSDetail.svelte';

const baseData = {
	title: 'Headlines',
	feeds: [{ url: 'https://example.com/feed.xml', name: 'Feed One' }],
	item_limit: 5,
	items: [
		{
			title: 'First headline',
			link: 'https://example.com/1',
			published: 'Mon, 01 Jan 2026 12:00:00 GMT',
			summary: 'A short summary.',
			source: 'Feed One',
		},
	],
};

describe('RSSDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders the title and each item with its source and summary', () => {
		render(RSSDetail, { props: { data: baseData } });

		expect(screen.getByText('Headlines')).toBeInTheDocument();
		expect(screen.getByText('First headline')).toBeInTheDocument();
		expect(screen.getByText('A short summary.')).toBeInTheDocument();
		expect(screen.getByText(/Feed One/)).toBeInTheDocument();
	});

	it('shows a hint when there are no items but feeds are configured', () => {
		render(RSSDetail, { props: { data: { ...baseData, items: [] } } });

		expect(screen.getByText('No items yet.')).toBeInTheDocument();
	});

	it('shows a distinct hint when no feeds are configured', () => {
		render(RSSDetail, { props: { data: { ...baseData, feeds: [], items: [] } } });

		expect(screen.getByText('No feeds configured yet — tap "Edit feeds" to add one.')).toBeInTheDocument();
	});

	it('opens the editor prefilled with the current feeds', async () => {
		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));

		expect(screen.getByPlaceholderText('Feed URL')).toHaveValue('https://example.com/feed.xml');
		expect(screen.getByPlaceholderText('Name (optional)')).toHaveValue('Feed One');
	});

	it('lets the user add a feed row, edit settings, and save', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue({
			...baseData,
			title: 'Tech News',
			feeds: [{ url: 'https://example.com/feed.xml', name: 'Feed One' }, { url: 'https://example.com/second.xml' }],
		});

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('+ Add feed'));

		const urlInputs = screen.getAllByPlaceholderText('Feed URL');
		expect(urlInputs).toHaveLength(2);
		await fireEvent.input(urlInputs[1], { target: { value: 'https://example.com/second.xml' } });

		const titleInput = screen.getByDisplayValue('Headlines');
		await fireEvent.input(titleInput, { target: { value: 'Tech News' } });

		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('rss', {
			title: 'Tech News',
			item_limit: 5,
			feeds: [
				{ url: 'https://example.com/feed.xml', name: 'Feed One' },
				{ url: 'https://example.com/second.xml', name: undefined },
			],
		});
		expect(widgetDetail).toHaveBeenCalledWith('rss');
	});

	it('drops blank feed rows when saving', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('+ Add feed'));
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('rss', {
			title: 'Headlines',
			item_limit: 5,
			feeds: [{ url: 'https://example.com/feed.xml', name: 'Feed One' }],
		});
	});

	it('removes a feed row when its remove button is clicked', async () => {
		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		expect(screen.getAllByPlaceholderText('Feed URL')).toHaveLength(1);

		await fireEvent.click(screen.getByLabelText('Remove feed'));

		expect(screen.queryByPlaceholderText('Feed URL')).not.toBeInTheDocument();
		expect(screen.getByText('No feeds yet — add one below.')).toBeInTheDocument();
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the feeds.')).toBeInTheDocument();
	});
});
