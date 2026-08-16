import { render, screen } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { widgetSummary } = vi.hoisted(() => ({ widgetSummary: vi.fn() }));
vi.mock('$lib/api', () => ({ api: { widgetSummary } }));

import GoodreadsTile from './GoodreadsTile.svelte';

describe('GoodreadsTile', () => {
	it('shows an empty state when there are no books', async () => {
		widgetSummary.mockResolvedValue({ shelf: 'currently-reading', books: [] });

		render(GoodreadsTile, { props: { widgetId: 'goodreads', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('No books on this shelf')).toBeInTheDocument();
	});

	it('shows the Goodreads header and the book cover, title, and author', async () => {
		widgetSummary.mockResolvedValue({
			shelf: 'currently-reading',
			books: [
				{
					title: 'Project Hail Mary',
					link: 'https://www.goodreads.com/review/show/1',
					book_image_url: 'https://images.gr.example/hail-mary.jpg',
					author_name: 'Andy Weir',
				},
			],
		});

		render(GoodreadsTile, { props: { widgetId: 'goodreads', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Goodreads')).toBeInTheDocument();
		expect(screen.getByText('Project Hail Mary')).toBeInTheDocument();
		expect(screen.getByText('Andy Weir')).toBeInTheDocument();
		expect(document.querySelector('img.thumb')).toHaveAttribute('src', 'https://images.gr.example/hail-mary.jpg');
	});

	it('lists all books at the same size when there is more than one', async () => {
		widgetSummary.mockResolvedValue({
			shelf: 'currently-reading',
			books: [
				{ title: 'Book One', link: 'https://x/1', book_image_url: '', author_name: 'A' },
				{
					title: 'Book Two',
					link: 'https://x/2',
					book_image_url: 'https://images.gr.example/two.jpg',
					author_name: 'B',
				},
				{
					title: 'Book Three',
					link: 'https://x/3',
					book_image_url: 'https://images.gr.example/three.jpg',
					author_name: 'C',
				},
			],
		});

		render(GoodreadsTile, { props: { widgetId: 'goodreads', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Book One')).toBeInTheDocument();
		expect(screen.getByText('Book Two')).toBeInTheDocument();
		expect(screen.getByText('Book Three')).toBeInTheDocument();

		// Book One has no image, so only Book Two and Book Three render thumbnails,
		// each using the same .thumb size/markup as every other book.
		const thumbs = document.querySelectorAll('img.thumb');
		expect(thumbs).toHaveLength(2);
		expect(thumbs[0]).toHaveAttribute('src', 'https://images.gr.example/two.jpg');
		expect(thumbs[1]).toHaveAttribute('src', 'https://images.gr.example/three.jpg');
	});

	it('renders a single book in the list', async () => {
		widgetSummary.mockResolvedValue({
			shelf: 'currently-reading',
			books: [{ title: 'Solo Book', link: 'https://x/1', book_image_url: '', author_name: 'A' }],
		});

		render(GoodreadsTile, { props: { widgetId: 'goodreads', refreshIntervalSeconds: 60 } });

		expect(await screen.findByText('Solo Book')).toBeInTheDocument();
		expect(document.querySelector('ul.more-books')).toBeInTheDocument();
	});
});
