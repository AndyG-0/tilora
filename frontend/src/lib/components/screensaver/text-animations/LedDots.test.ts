import { render } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import LedDots from './LedDots.svelte';
import type { FormattedSegment } from '$lib/discordMarkdown';

const ROW_HEIGHT_PX = 64;

function line(text: string): FormattedSegment[] {
	return [{ text }];
}

function mockClientHeight(height: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
}

function mockClientHeights({ sign, rows }: { sign: number; rows: number }) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function (this: HTMLElement) {
		if (this.classList.contains('rows')) return rows;
		if (this.classList.contains('sign')) return sign;
		return 0;
	});
}

describe('LedDots', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('defaults to the amber color when none is given', () => {
		const { container } = render(LedDots, { props: { id: 'test', lines: [line('Hello')] } });
		const sign = container.querySelector('.sign');
		expect(sign).toHaveStyle('--dotmatrix-color: #ff8a00');
	});

	it('applies a custom color via the color prop', () => {
		const { container } = render(LedDots, { props: { id: 'test', lines: [line('Hello')], color: '#00ff00' } });
		const sign = container.querySelector('.sign');
		expect(sign).toHaveStyle('--dotmatrix-color: #00ff00');
	});

	it('shows the first line initially and advances to the next on a tick', async () => {
		const { container } = render(LedDots, {
			props: { id: 'test', lines: [line('One'), line('Two')], pauseSeconds: 5 },
		});
		expect(container.querySelector('.dots')?.textContent).toBe('One');

		await vi.advanceTimersByTimeAsync(5000);

		expect(container.querySelector('.dots')?.textContent).toBe('Two');
	});

	it('shows a single row when the container is too short for more', () => {
		mockClientHeight(40);

		const { container } = render(LedDots, { props: { id: 'test', lines: [line('One'), line('Two'), line('Three')] } });

		expect(container.querySelectorAll('.stack')).toHaveLength(1);
	});

	it('shows multiple rows sized to the measured container height', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(LedDots, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three'), line('Four'), line('Five')] },
		});

		expect(container.querySelectorAll('.stack')).toHaveLength(4);
	});

	it('advances by rowsToShow (not 1) per tick so consecutive ticks show fresh content', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(LedDots, {
			props: {
				id: 'test',
				lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line),
				pauseSeconds: 6,
			},
		});

		const firstBatch = Array.from(container.querySelectorAll('.dots')).map((el) => el.textContent);

		await vi.advanceTimersByTimeAsync(6000);

		const secondBatch = Array.from(container.querySelectorAll('.dots')).map((el) => el.textContent);
		expect(secondBatch).not.toEqual(firstBatch);
		expect(secondBatch[0]).toBe('Row D');
	});

	it('does not shrink rowsToShow when the measured rows already fit the sign', () => {
		mockClientHeights({ sign: 3 * ROW_HEIGHT_PX, rows: 3 * ROW_HEIGHT_PX });

		const { container } = render(LedDots, {
			props: { id: 'test', lines: ['One', 'Two', 'Three', 'Four'].map(line) },
		});

		expect(container.querySelectorAll('.stack')).toHaveLength(3);
	});

	it('shrinks rowsToShow when a wrapped long line makes the rows overflow the sign', () => {
		mockClientHeights({ sign: 3 * ROW_HEIGHT_PX, rows: 4 * ROW_HEIGHT_PX });

		const longLine = 'This message is much longer than a single row of dots can hold without wrapping onto extra lines';
		const { container } = render(LedDots, {
			props: { id: 'test', lines: [line(longLine), line('Two'), line('Three'), line('Four')] },
		});

		expect(container.querySelectorAll('.stack').length).toBeLessThan(3);
	});

	it('wraps a long line onto extra visual lines instead of truncating it', () => {
		mockClientHeight(ROW_HEIGHT_PX);

		const longLine = 'This message is much longer than a single row of dots can hold without wrapping';
		const { container } = render(LedDots, { props: { id: 'test', lines: [line(longLine)] } });

		expect(container.querySelector('.dots')?.textContent).toBe(longLine);
	});

	it('renders formatted segments as their corresponding inline elements', () => {
		const { container } = render(LedDots, {
			props: { id: 'test', lines: [[{ text: 'bold', bold: true }, { text: ' plain' }]] },
		});

		expect(container.querySelector('.dots strong')?.textContent).toBe('bold');
	});
});
