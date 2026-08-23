import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, updateWidgetSettings } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	updateWidgetSettings: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, updateWidgetSettings } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'goodreads' } } }));

import GoodreadsDetail from './GoodreadsDetail.svelte';

const notConfigured = {
	configured: false,
	shelf: 'currently-reading',
	user_id: '',
	books: [],
};

const withBooks = {
	configured: true,
	shelf: 'currently-reading',
	user_id: '12345',
	books: [
		{
			title: 'Project Hail Mary',
			link: 'https://www.goodreads.com/review/show/1',
			book_image_url: 'https://images.gr.example/hail-mary.jpg',
			author_name: 'Andy Weir',
			isbn: '0593135202',
			average_rating: '4.51',
			user_rating: '0',
			user_date_added: 'Wed, 01 Jan 2026 12:00:00 -0800',
			user_read_at: '',
		},
		{
			title: 'Dune',
			link: 'https://www.goodreads.com/review/show/2',
			book_image_url: 'https://images.gr.example/dune.jpg',
			author_name: 'Frank Herbert',
			isbn: '0441013597',
			average_rating: '4.24',
			user_rating: '5',
			user_date_added: 'Mon, 01 Dec 2025 12:00:00 -0800',
			user_read_at: 'Sun, 15 Feb 2026 12:00:00 -0800',
		},
	],
};

describe('GoodreadsDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('shows a not-configured hint', () => {
		render(GoodreadsDetail, { props: { data: notConfigured } });

		expect(
			screen.getByText('No shelf configured yet — tap "Edit shelf" to add your Goodreads user id.'),
		).toBeInTheDocument();
	});

	it('renders books with average rating when unrated by the user', () => {
		render(GoodreadsDetail, { props: { data: withBooks } });

		expect(screen.getByText('Project Hail Mary')).toBeInTheDocument();
		expect(screen.getByText('Andy Weir')).toBeInTheDocument();
		expect(screen.getByText('Average rating: 4.51')).toBeInTheDocument();
	});

	it('renders the user rating instead of the average when the user rated it', () => {
		render(GoodreadsDetail, { props: { data: withBooks } });

		expect(screen.getByText('Your rating: 5/5')).toBeInTheDocument();
	});

	it('opens the settings editor with the current shelf values', async () => {
		render(GoodreadsDetail, { props: { data: withBooks } });

		await fireEvent.click(screen.getByText('Edit shelf'));

		expect(screen.getByPlaceholderText('12345678')).toHaveValue('12345');
		expect(screen.getByPlaceholderText('currently-reading')).toHaveValue('currently-reading');
	});

	it('saves settings and refetches', async () => {
		updateWidgetSettings.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ ...withBooks, shelf: 'read' });

		render(GoodreadsDetail, { props: { data: withBooks } });

		await fireEvent.click(screen.getByText('Edit shelf'));
		await fireEvent.input(screen.getByPlaceholderText('currently-reading'), {
			target: { value: 'read' },
		});
		await fireEvent.click(screen.getByText('Save'));

		await vi.waitFor(() =>
			expect(updateWidgetSettings).toHaveBeenCalledWith('goodreads', {
				user_id: '12345',
				shelf: 'read',
			}),
		);
		expect(widgetDetail).toHaveBeenCalledWith('goodreads');
	});

	it('shows an error if saving settings fails', async () => {
		updateWidgetSettings.mockRejectedValue(new Error('Could not update the shelf settings.'));

		render(GoodreadsDetail, { props: { data: withBooks } });

		await fireEvent.click(screen.getByText('Edit shelf'));
		await fireEvent.click(screen.getByText('Save'));

		expect(await screen.findByText('Could not update the shelf settings.')).toBeInTheDocument();
	});
});
