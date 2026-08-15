import { render } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import Flipboard from './Flipboard.svelte';
import type { FormattedSegment } from '$lib/discordMarkdown';

const ROW_HEIGHT_PX = 48;
const CHAR_DELAY_MS = 25;
const ROW_GAP_MS = 120;
const FLAP_DURATION_MS = 400;

function line(text: string): FormattedSegment[] {
	return [{ text }];
}

function revealDurationMs(visibleLines: string[]): number {
	let elapsed = 0;
	for (let r = 0; r < visibleLines.length; r++) {
		if (r > 0) elapsed += visibleLines[r - 1].length * CHAR_DELAY_MS + ROW_GAP_MS;
	}
	return elapsed + visibleLines[visibleLines.length - 1].length * CHAR_DELAY_MS + FLAP_DURATION_MS;
}

function mockClientHeight(height: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
}

describe('Flipboard', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('shows a single row when the container is too short for more', () => {
		mockClientHeight(40);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three')] },
		});

		expect(container.querySelectorAll('.row')).toHaveLength(1);
	});

	it('shows multiple rows sized to the measured container height', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three'), line('Four'), line('Five')] },
		});

		expect(container.querySelectorAll('.row')).toHaveLength(4);
	});

	it('wraps around the lines array via modulo when rowsToShow exceeds the line count', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, { props: { id: 'test', lines: [line('Alpha'), line('Beta')] } });

		const rowTexts = Array.from(container.querySelectorAll('.row')).map((row) => row.textContent?.trim());
		expect(rowTexts).toEqual([rowTexts[0], rowTexts[1], rowTexts[0], rowTexts[1]]);
	});

	it('advances by rowsToShow (not 1) per tick so consecutive ticks show fresh content', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));

		await vi.advanceTimersByTimeAsync(revealDurationMs(['Row A', 'Row B', 'Row C']) + 6000);

		const secondBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));
		expect(secondBatch).not.toEqual(firstBatch);
		expect(secondBatch[0]).toBe('Row D');
	});

	it('holds the full pauseSeconds of static read time after the last row finishes flapping in', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));

		const total = revealDurationMs(['Row A', 'Row B', 'Row C']) + 6000;
		await vi.advanceTimersByTimeAsync(total - 1);
		expect(Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent))).toEqual(firstBatch);

		await vi.advanceTimersByTimeAsync(1);
		expect(Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent))).not.toEqual(
			firstBatch,
		);
	});

	it('wraps a long line onto extra flaps instead of truncating it', () => {
		mockClientHeight(ROW_HEIGHT_PX);

		const longLine = 'This message is much longer than a single row of flaps can hold without wrapping';
		const { container } = render(Flipboard, { props: { id: 'test', lines: [line(longLine)] } });

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		expect(normalize(container.querySelector('.row')?.textContent)).toBe(longLine);
	});

	it('renders formatted segments as per-character classed flaps', () => {
		mockClientHeight(ROW_HEIGHT_PX);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: [[{ text: 'ab', italic: true }, { text: 'c' }]] },
		});

		const flaps = Array.from(container.querySelectorAll('.flap'));
		expect(flaps.map((el) => el.textContent)).toEqual(['a', 'b', 'c']);
		expect(flaps[0].classList.contains('italic')).toBe(true);
		expect(flaps[1].classList.contains('italic')).toBe(true);
		expect(flaps[2].classList.contains('italic')).toBe(false);
	});

	it('advances to a random line instead of the next sequential one when pattern is random', async () => {
		mockClientHeight(ROW_HEIGHT_PX);
		vi.spyOn(Math, 'random').mockReturnValue(0);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C'].map(line), pauseSeconds: 6, pattern: 'random' },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		expect(normalize(container.querySelector('.row')?.textContent)).toBe('Row A');

		await vi.advanceTimersByTimeAsync(revealDurationMs(['Row A']) + 6000);

		// Math.random() === 0 maps to index 0, which is the current line -- the
		// anti-repeat branch should bump it to index 1 instead of holding still.
		expect(normalize(container.querySelector('.row')?.textContent)).toBe('Row B');
	});

	it('falls back to sequential advancing for random pattern when every line is already visible', async () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);
		vi.spyOn(Math, 'random').mockReturnValue(0);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['Row A', 'Row B'].map(line), pauseSeconds: 6, pattern: 'random' },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));

		await vi.advanceTimersByTimeAsync(revealDurationMs(['Row A', 'Row B']) + 6000);

		const secondBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));
		expect(secondBatch).toEqual(firstBatch);
	});

	it('cascades flap delays left-to-right within a row and top-to-bottom across rows', () => {
		mockClientHeight(2 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, { props: { id: 'test', lines: [line('Row A'), line('Row B')] } });

		const getDelay = (flap: Element) => Number(flap.getAttribute('style')?.match(/animation-delay: (\d+)ms/)?.[1]);

		const rows = container.querySelectorAll('.row');
		const firstRowFlaps = Array.from(rows[0].querySelectorAll('.flap'));
		const secondRowFlaps = Array.from(rows[1].querySelectorAll('.flap'));

		const firstRowDelays = firstRowFlaps.map(getDelay);
		for (let i = 1; i < firstRowDelays.length; i++) {
			expect(firstRowDelays[i]).toBeGreaterThan(firstRowDelays[i - 1]);
		}

		expect(getDelay(secondRowFlaps[0])).toBeGreaterThan(getDelay(firstRowFlaps[firstRowFlaps.length - 1]));
	});
});
