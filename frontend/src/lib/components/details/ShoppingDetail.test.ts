import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, createShoppingItem, checkShoppingItem, removeShoppingItem } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	createShoppingItem: vi.fn(),
	checkShoppingItem: vi.fn(),
	removeShoppingItem: vi.fn(),
}));
vi.mock('$lib/api', () => ({
	api: { widgetDetail, createShoppingItem, checkShoppingItem, removeShoppingItem },
}));
vi.mock('$app/state', () => ({ page: { params: { id: 'shopping' } } }));

import ShoppingDetail from './ShoppingDetail.svelte';

const item1 = {
	id: 1,
	widget_id: 'shopping',
	text: 'Milk',
	checked: false,
	added_by: 'Alice',
	checked_by: null,
	created_at: '2026-01-01T00:00:00+00:00',
	checked_at: null,
};

describe('ShoppingDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders each item, its attribution, and the widget title', () => {
		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [item1], open_count: 1 } } });

		expect(screen.getByText('Shopping List')).toBeInTheDocument();
		expect(screen.getByText('Milk')).toBeInTheDocument();
		expect(screen.getByText('added by Alice')).toBeInTheDocument();
	});

	it('shows a hint when there are no items', () => {
		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [], open_count: 0 } } });

		expect(screen.getByText('No items yet — add one above.')).toBeInTheDocument();
	});

	it('adds a new item from the form and refetches', async () => {
		createShoppingItem.mockResolvedValue({ ...item1, id: 2, text: 'Bread' });
		widgetDetail.mockResolvedValue({
			title: 'Shopping List',
			items: [{ ...item1, id: 2, text: 'Bread' }],
			open_count: 1,
		});

		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [], open_count: 0 } } });

		await fireEvent.input(screen.getByPlaceholderText('Add an item…'), { target: { value: 'Bread' } });
		await fireEvent.click(screen.getByText('Add'));

		await vi.waitFor(() => expect(createShoppingItem).toHaveBeenCalledWith('Bread'));
		expect(await screen.findByText('Bread')).toBeInTheDocument();
	});

	it('shows an error if adding an item fails', async () => {
		createShoppingItem.mockRejectedValue(new Error('boom'));

		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [], open_count: 0 } } });

		await fireEvent.input(screen.getByPlaceholderText('Add an item…'), { target: { value: 'Oops' } });
		await fireEvent.click(screen.getByText('Add'));

		expect(await screen.findByText('Could not add the item.')).toBeInTheDocument();
	});

	it('checks off an item via its checkbox, showing who checked it, and refetches', async () => {
		checkShoppingItem.mockResolvedValue({ ...item1, checked: true, checked_by: 'Bob' });
		widgetDetail.mockResolvedValue({
			title: 'Shopping List',
			items: [{ ...item1, checked: true, checked_by: 'Bob' }],
			open_count: 0,
		});

		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByRole('checkbox'));

		await vi.waitFor(() => expect(checkShoppingItem).toHaveBeenCalledWith(1));
		expect(await screen.findByText('checked off by Bob')).toBeInTheDocument();
	});

	it('removes an item and refetches', async () => {
		removeShoppingItem.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ title: 'Shopping List', items: [], open_count: 0 });

		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByLabelText('Remove item'));

		await vi.waitFor(() => expect(removeShoppingItem).toHaveBeenCalledWith(1));
		expect(screen.queryByText('Milk')).not.toBeInTheDocument();
	});

	it('shows an error if removing an item fails', async () => {
		removeShoppingItem.mockRejectedValue(new Error('boom'));

		render(ShoppingDetail, { props: { data: { title: 'Shopping List', items: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByLabelText('Remove item'));

		expect(await screen.findByText('Could not remove the item.')).toBeInTheDocument();
	});
});
