import { render, screen, fireEvent } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

const { goto, widgetSummary, completeChore } = vi.hoisted(() => ({
	goto: vi.fn(),
	widgetSummary: vi.fn(),
	completeChore: vi.fn(),
}));
vi.mock('$app/navigation', () => ({ goto }));
vi.mock('$lib/api', () => ({ api: { widgetSummary, completeChore } }));

import ChoresTile from './ChoresTile.svelte';

const OPEN_ITEM = {
	id: 1,
	widget_id: 'chores',
	user_id: 'user-1',
	text: 'Take out trash',
	completed: false,
	created_at: '2026-01-01T00:00:00+00:00',
	completed_at: null,
};

describe('ChoresTile', () => {
	it('shows a loading state before the summary resolves', () => {
		widgetSummary.mockReturnValue(new Promise(() => {})); // never resolves

		render(ChoresTile, { props: { widgetId: 'chores' } });

		expect(screen.getByText('Loading…')).toBeInTheDocument();
	});

	it('renders open items with a count badge', async () => {
		widgetSummary.mockResolvedValue({ title: 'To-Do', chores: [OPEN_ITEM], open_count: 1 });

		render(ChoresTile, { props: { widgetId: 'chores' } });

		expect(await screen.findByText('Take out trash')).toBeInTheDocument();
		expect(screen.getByText('To-Do')).toBeInTheDocument();
		expect(screen.getByText('1')).toBeInTheDocument();
	});

	it('excludes completed items from the list', async () => {
		widgetSummary.mockResolvedValue({
			title: 'To-Do',
			chores: [OPEN_ITEM, { ...OPEN_ITEM, id: 2, text: 'Done already', completed: true }],
			open_count: 1,
		});

		render(ChoresTile, { props: { widgetId: 'chores' } });

		await screen.findByText('Take out trash');
		expect(screen.queryByText('Done already')).not.toBeInTheDocument();
	});

	it('shows an empty state when there are no open items', async () => {
		widgetSummary.mockResolvedValue({ title: 'To-Do', chores: [], open_count: 0 });

		render(ChoresTile, { props: { widgetId: 'chores' } });

		expect(await screen.findByText('All done!')).toBeInTheDocument();
	});

	it('completes an item from the tile without navigating to the detail page', async () => {
		completeChore.mockResolvedValue({ ...OPEN_ITEM, completed: true });
		widgetSummary
			.mockResolvedValueOnce({ title: 'To-Do', chores: [OPEN_ITEM], open_count: 1 })
			.mockResolvedValueOnce({ title: 'To-Do', chores: [], open_count: 0 });

		render(ChoresTile, { props: { widgetId: 'chores' } });

		await screen.findByText('Take out trash');
		await fireEvent.click(screen.getByRole('checkbox'));

		await vi.waitFor(() => expect(completeChore).toHaveBeenCalledWith(1));
		expect(await screen.findByText('All done!')).toBeInTheDocument();
		expect(goto).not.toHaveBeenCalled();
	});
});
