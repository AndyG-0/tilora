import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { updateWidgetSettings, widgetDetail, listRSSFeeds, addRSSFeed, updateRSSFeed, deleteRSSFeed } = vi.hoisted(
	() => ({
		updateWidgetSettings: vi.fn(),
		widgetDetail: vi.fn(),
		listRSSFeeds: vi.fn(),
		addRSSFeed: vi.fn(),
		updateRSSFeed: vi.fn(),
		deleteRSSFeed: vi.fn(),
	}),
);
vi.mock('$lib/api', () => ({
	api: { updateWidgetSettings, widgetDetail, listRSSFeeds, addRSSFeed, updateRSSFeed, deleteRSSFeed },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'rss' } } }));

import RSSDetail from './RSSDetail.svelte';

const feedOne = {
	id: 1,
	user_id: 'user-1',
	url: 'https://example.com/feed.xml',
	name: 'Feed One',
	item_limit: 10,
	created_at: '2026-01-01T00:00:00Z',
};

const feedTwo = {
	id: 2,
	user_id: 'user-1',
	url: 'https://example.com/second.xml',
	name: null,
	item_limit: 10,
	created_at: '2026-01-01T00:00:00Z',
};

const baseData = {
	title: 'Headlines',
	feed_ids: [1],
	all_feeds: [feedOne],
	feed_groups: [
		{
			feed_id: 1,
			name: 'Feed One',
			items: [
				{
					title: 'First headline',
					link: 'https://example.com/1',
					published: 'Mon, 01 Jan 2026 12:00:00 GMT',
					summary: 'A short summary.',
					source: 'Feed One',
					image: null,
				},
			],
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

	it('renders title as link to article and renders comments link when available', () => {
		render(RSSDetail, {
			props: {
				data: {
					...baseData,
					feed_groups: [
						{
							...baseData.feed_groups[0],
							items: [
								{
									...baseData.feed_groups[0].items[0],
									comments: 'https://news.ycombinator.com/item?id=123456',
								},
							],
						},
					],
				},
			},
		});

		const titleLink = screen.getByRole('link', { name: 'First headline' });
		expect(titleLink).toHaveAttribute('href', 'https://example.com/1');
		expect(titleLink).toHaveAttribute('target', '_blank');

		const commentsLink = screen.getByRole('link', { name: 'Comments' });
		expect(commentsLink).toHaveAttribute('href', 'https://news.ycombinator.com/item?id=123456');
		expect(commentsLink).toHaveAttribute('target', '_blank');
	});

	it('does not render comments link when comments is missing', () => {
		render(RSSDetail, { props: { data: baseData } });

		expect(screen.queryByRole('link', { name: 'Comments' })).not.toBeInTheDocument();
	});

	it('does not show a group heading when only one feed has items', () => {
		render(RSSDetail, { props: { data: baseData } });

		expect(screen.queryByRole('heading', { level: 2, name: 'Feed One' })).not.toBeInTheDocument();
	});

	it('shows a heading per group when multiple feeds have items', () => {
		render(RSSDetail, {
			props: {
				data: {
					...baseData,
					all_feeds: [feedOne, feedTwo],
					feed_ids: [1, 2],
					feed_groups: [
						...baseData.feed_groups,
						{
							feed_id: 2,
							name: 'https://example.com/second.xml',
							items: [
								{
									title: 'Second headline',
									link: 'https://example.com/2',
									published: null,
									summary: '',
									source: 'https://example.com/second.xml',
									image: null,
								},
							],
						},
					],
				},
			},
		});

		expect(screen.getByRole('heading', { level: 2, name: 'Feed One' })).toBeInTheDocument();
		expect(screen.getByRole('heading', { level: 2, name: 'https://example.com/second.xml' })).toBeInTheDocument();
	});

	it('renders a thumbnail when an item has an image', () => {
		const { container } = render(RSSDetail, {
			props: {
				data: {
					...baseData,
					feed_groups: [
						{
							...baseData.feed_groups[0],
							items: [{ ...baseData.feed_groups[0].items[0], image: 'https://example.com/pic.jpg' }],
						},
					],
				},
			},
		});

		expect(container.querySelector('img.thumb')).toHaveAttribute('src', 'https://example.com/pic.jpg');
	});

	it('shows a hint when there are no items but feeds are selected', () => {
		render(RSSDetail, { props: { data: { ...baseData, feed_groups: [] } } });

		expect(screen.getByText('No items yet.')).toBeInTheDocument();
	});

	it('shows a per-feed error instead of dropping a feed that failed to load', () => {
		render(RSSDetail, {
			props: {
				data: {
					...baseData,
					all_feeds: [feedOne, feedTwo],
					feed_ids: [1, 2],
					feed_groups: [
						...baseData.feed_groups,
						{ feed_id: 2, name: 'Feed Two', items: [], error: 'This feed could not be loaded.' },
					],
				},
			},
		});

		expect(screen.getByRole('heading', { level: 2, name: 'Feed Two' })).toBeInTheDocument();
		expect(screen.getByText('This feed could not be loaded.')).toBeInTheDocument();
		expect(screen.getByText('First headline')).toBeInTheDocument();
	});

	it('shows a distinct hint when no feeds are selected', () => {
		render(RSSDetail, { props: { data: { ...baseData, feed_ids: [], feed_groups: [] } } });

		expect(screen.getByText('No feeds selected yet — tap "Edit feeds" to choose one.')).toBeInTheDocument();
	});

	it('opens the editor prefilled with the current title and selected feeds checked', async () => {
		render(RSSDetail, { props: { data: { ...baseData, all_feeds: [feedOne, feedTwo] } } });

		await fireEvent.click(screen.getByText('Edit feeds'));

		expect(screen.getByDisplayValue('Headlines')).toBeInTheDocument();
		const checkboxes = screen.getAllByRole('checkbox');
		expect(checkboxes[0]).toBeChecked();
		expect(checkboxes[1]).not.toBeChecked();
	});

	it('saves the title and toggled feed selection', async () => {
		updateWidgetSettings.mockResolvedValue({});
		widgetDetail.mockResolvedValue(baseData);

		render(RSSDetail, { props: { data: { ...baseData, all_feeds: [feedOne, feedTwo] } } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		const titleInput = screen.getByDisplayValue('Headlines');
		await fireEvent.input(titleInput, { target: { value: 'Tech News' } });
		await fireEvent.click(screen.getAllByRole('checkbox')[1]);
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() => expect(updateWidgetSettings).toHaveBeenCalled());
		expect(updateWidgetSettings).toHaveBeenCalledWith('rss', { title: 'Tech News', feed_ids: [1, 2] });
		expect(widgetDetail).toHaveBeenCalledWith('rss');
	});

	it('shows an error if saving fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('boom'));

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the selected feeds.')).toBeInTheDocument();
	});

	it('adds a feed from the manage panel', async () => {
		addRSSFeed.mockResolvedValue(feedTwo);
		listRSSFeeds.mockResolvedValue([feedOne, feedTwo]);

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('Manage my feeds'));
		await fireEvent.input(screen.getByPlaceholderText('Feed URL'), {
			target: { value: 'https://example.com/second.xml' },
		});
		await fireEvent.click(screen.getByText('+ Add feed'));

		await vi.waitFor(() => expect(addRSSFeed).toHaveBeenCalledWith('https://example.com/second.xml', undefined, 10));
		expect(listRSSFeeds).toHaveBeenCalled();
	});

	it('removes a feed from the manage panel', async () => {
		deleteRSSFeed.mockResolvedValue({ status: 'ok' });
		listRSSFeeds.mockResolvedValue([]);

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('Manage my feeds'));
		await fireEvent.click(screen.getByText('Remove'));

		await vi.waitFor(() => expect(deleteRSSFeed).toHaveBeenCalledWith(1));
		expect(listRSSFeeds).toHaveBeenCalled();
	});

	it('updates a feed name and item limit from the manage panel', async () => {
		updateRSSFeed.mockResolvedValue({ ...feedOne, name: 'Renamed' });
		listRSSFeeds.mockResolvedValue([{ ...feedOne, name: 'Renamed' }]);

		render(RSSDetail, { props: { data: baseData } });

		await fireEvent.click(screen.getByText('Edit feeds'));
		await fireEvent.click(screen.getByText('Manage my feeds'));
		await fireEvent.click(screen.getByText('Edit'));
		const nameInputs = screen.getAllByPlaceholderText('Name (optional)');
		await fireEvent.input(nameInputs[0], { target: { value: 'Renamed' } });
		const saveButtons = screen.getAllByText('Save');
		await fireEvent.click(saveButtons[saveButtons.length - 1]);

		await vi.waitFor(() => expect(updateRSSFeed).toHaveBeenCalledWith(1, 'Renamed', 10));
	});
});
