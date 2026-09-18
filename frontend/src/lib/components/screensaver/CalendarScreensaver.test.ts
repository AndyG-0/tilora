import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import CalendarScreensaver from './CalendarScreensaver.svelte';

const ROW_HEIGHT_PX = 130;

interface CalendarEvent {
	id: string;
	title: string;
	start: string;
	all_day: boolean;
	location: string | null;
	calendar?: string;
	color?: string | null;
}

function event(id: string, title: string): CalendarEvent {
	return { id, title, start: '2026-01-01T10:00:00Z', all_day: true, location: null };
}

function mockClientHeight(height: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
}

function mockClientHeights({ list, items }: { list: number; items: number }) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function (this: HTMLElement) {
		if (this.classList.contains('items')) return items;
		if (this.classList.contains('list')) return list;
		return 0;
	});
}

describe('CalendarScreensaver', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('shows the not-connected hint when the account is not connected', () => {
		const { container } = render(CalendarScreensaver, {
			props: { id: 'cal-1', data: { connected: false, events: [] } },
		});

		expect(container.querySelector('.hint')).toBeInTheDocument();
		expect(container.querySelector('.list')).not.toBeInTheDocument();
	});

	it('shows a single page with no indicator dots when everything fits', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(CalendarScreensaver, {
			props: { id: 'cal-1', data: { connected: true, events: [event('1', 'One'), event('2', 'Two')] } },
		});

		expect(container.querySelectorAll('.item')).toHaveLength(2);
		expect(container.querySelector('button.dot')).not.toBeInTheDocument();
	});

	it('paginates events sized to the measured list height', () => {
		mockClientHeight(2 * ROW_HEIGHT_PX);

		const { container } = render(CalendarScreensaver, {
			props: {
				id: 'cal-1',
				data: {
					connected: true,
					events: [event('1', 'One'), event('2', 'Two'), event('3', 'Three'), event('4', 'Four')],
				},
			},
		});

		expect(container.querySelectorAll('.item')).toHaveLength(2);
		expect(container.querySelectorAll('button.dot')).toHaveLength(2);
	});

	it('advances to the next page after pauseSeconds elapses', async () => {
		mockClientHeight(1 * ROW_HEIGHT_PX);

		const { container } = render(CalendarScreensaver, {
			props: {
				id: 'cal-1',
				data: { connected: true, events: [event('1', 'One'), event('2', 'Two')] },
				pauseSeconds: 5,
			},
		});

		expect(container.querySelector('.item h2')?.textContent).toContain('One');

		await vi.advanceTimersByTimeAsync(5000);

		expect(container.querySelector('.item h2')?.textContent).toContain('Two');
	});

	it('shrinks rowsToShow when a wrapped title makes the items overflow the list', () => {
		mockClientHeights({ list: 3 * ROW_HEIGHT_PX, items: 4 * ROW_HEIGHT_PX });

		const { container } = render(CalendarScreensaver, {
			props: {
				id: 'cal-1',
				data: {
					connected: true,
					events: [event('1', 'One'), event('2', 'Two'), event('3', 'Three'), event('4', 'Four')],
				},
			},
		});

		expect(container.querySelectorAll('.item').length).toBeLessThan(3);
	});

	it('jumps to the clicked page instead of advancing sequentially', async () => {
		mockClientHeight(1 * ROW_HEIGHT_PX);

		const { container } = render(CalendarScreensaver, {
			props: {
				id: 'cal-1',
				data: { connected: true, events: [event('1', 'One'), event('2', 'Two'), event('3', 'Three')] },
				pauseSeconds: 5,
			},
		});

		const dots = container.querySelectorAll('button.dot');
		expect(dots).toHaveLength(3);

		(dots[2] as HTMLButtonElement).click();
		await tick();

		expect(container.querySelector('.item h2')?.textContent).toContain('Three');
	});
});
