import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi, beforeEach } from 'vitest';

const { widgetDetail, createChore, completeChore, removeChore } = vi.hoisted(() => ({
	widgetDetail: vi.fn(),
	createChore: vi.fn(),
	completeChore: vi.fn(),
	removeChore: vi.fn(),
}));
vi.mock('$lib/api', () => ({ api: { widgetDetail, createChore, completeChore, removeChore } }));
vi.mock('$app/state', () => ({ page: { params: { id: 'chores' } } }));

import ChoresDetail from './ChoresDetail.svelte';

const item1 = {
	id: 1,
	widget_id: 'chores',
	user_id: 'user-1',
	text: 'Take out trash',
	completed: false,
	created_at: '2026-01-01T00:00:00+00:00',
	completed_at: null,
};

describe('ChoresDetail', () => {
	beforeEach(() => {
		vi.clearAllMocks();
	});

	it('renders each item and the widget title', () => {
		render(ChoresDetail, { props: { data: { title: 'Chores', chores: [item1], open_count: 1 } } });

		expect(screen.getByText('Chores')).toBeInTheDocument();
		expect(screen.getByText('Take out trash')).toBeInTheDocument();
	});

	it('shows a hint when there are no items', () => {
		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [], open_count: 0 } } });

		expect(screen.getByText('No items yet — add one above.')).toBeInTheDocument();
	});

	it('adds a new item from the form and refetches', async () => {
		createChore.mockResolvedValue({ ...item1, id: 2, text: 'New item' });
		widgetDetail.mockResolvedValue({ title: 'To-Do', chores: [{ ...item1, id: 2, text: 'New item' }], open_count: 1 });

		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [], open_count: 0 } } });

		await fireEvent.input(screen.getByPlaceholderText('Add an item…'), { target: { value: 'New item' } });
		await fireEvent.click(screen.getByText('Add'));

		await vi.waitFor(() => expect(createChore).toHaveBeenCalledWith('New item'));
		expect(await screen.findByText('New item')).toBeInTheDocument();
	});

	it('shows an error if adding an item fails', async () => {
		createChore.mockRejectedValue(new Error('boom'));

		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [], open_count: 0 } } });

		await fireEvent.input(screen.getByPlaceholderText('Add an item…'), { target: { value: 'Oops' } });
		await fireEvent.click(screen.getByText('Add'));

		expect(await screen.findByText('Could not add the item.')).toBeInTheDocument();
	});

	it('completes an item via its checkbox and refetches', async () => {
		completeChore.mockResolvedValue({ ...item1, completed: true });
		widgetDetail.mockResolvedValue({ title: 'To-Do', chores: [{ ...item1, completed: true }], open_count: 0 });

		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByRole('checkbox'));

		await vi.waitFor(() => expect(completeChore).toHaveBeenCalledWith(1));
		await vi.waitFor(() => expect(widgetDetail).toHaveBeenCalled());
	});

	it('removes an item and refetches', async () => {
		removeChore.mockResolvedValue({ status: 'ok' });
		widgetDetail.mockResolvedValue({ title: 'To-Do', chores: [], open_count: 0 });

		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByLabelText('Remove item'));

		await vi.waitFor(() => expect(removeChore).toHaveBeenCalledWith(1));
		expect(screen.queryByText('Take out trash')).not.toBeInTheDocument();
	});

	it('shows an error if removing an item fails', async () => {
		removeChore.mockRejectedValue(new Error('boom'));

		render(ChoresDetail, { props: { data: { title: 'To-Do', chores: [item1], open_count: 1 } } });

		await fireEvent.click(screen.getByLabelText('Remove item'));

		expect(await screen.findByText('Could not remove the item.')).toBeInTheDocument();
	});
});
