import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary, checkShoppingItem } = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetSummary: vi.fn(),
	checkShoppingItem: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary, checkShoppingItem } }));

import ShoppingTile from './ShoppingTile.svelte';

const OPEN_ITEM = {
	id: 1,
	widget_id: 'shopping',
	text: 'Milk',
	checked: false,
	added_by: 'Alice',
	checked_by: null,
	created_at: '2026-01-01T00:00:00+00:00',
	checked_at: null,
};

describe('ShoppingTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(ShoppingTile, { props: { widgetId: 'shopping' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders open items with a count badge', async () => {
		widgetSummary.mockResolvedValue({ title: 'Shopping List', items: [OPEN_ITEM], open_count: 1 });

		render(ShoppingTile, { props: { widgetId: 'shopping' } });

		expect(await screen.findByText('Milk')).toBeInTheDocument();
		expect(screen.getByText('Shopping List')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
	});

	it('excludes checked items from the list', async () => {
		widgetSummary.mockResolvedValue({
			title: 'Shopping List',
			items: [OPEN_ITEM, { ...OPEN_ITEM, id: 2, text: 'Eggs', checked: true, checked_by: 'Bob' }],
			open_count: 1,
		});

		render(ShoppingTile, { props: { widgetId: 'shopping' } });

		await screen.findByText('Milk');
		expect(screen.queryByText('Eggs')).not.toBeInTheDocument();
	});

	it('shows an empty state when there are no open items', async () => {
		widgetSummary.mockResolvedValue({ title: 'Shopping List', items: [], open_count: 0 });

		render(ShoppingTile, { props: { widgetId: 'shopping' } });

		expect(await screen.findByText('All done!')).toBeInTheDocument();
	});

	it('checks off an item from the tile without navigating to the detail page', async () => {
		checkShoppingItem.mockResolvedValue({ ...OPEN_ITEM, checked: true, checked_by: 'Alice' });
		widgetSummary
			.mockResolvedValueOnce({ title: 'Shopping List', items: [OPEN_ITEM], open_count: 1 })
			.mockResolvedValueOnce({ title: 'Shopping List', items: [], open_count: 0 });

		render(ShoppingTile, { props: { widgetId: 'shopping' } });

		await screen.findByText('Milk');
		await fireEvent.click(screen.getByRole('checkbox'));

		await vi.waitFor(() => expect(checkShoppingItem).toHaveBeenCalledWith(1));
		expect(await screen.findByText('All done!')).toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();
	});
});
