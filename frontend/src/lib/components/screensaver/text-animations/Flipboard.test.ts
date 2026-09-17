import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
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

// Mocks .board's and .rows-wrapper's clientHeight independently, so a test
// can simulate content that wraps onto more visual sub-rows than the
// one-shot estimate predicted (i.e. the rendered rows wrapper measuring
// taller than the .board container that's supposed to hold it).
function mockClientHeightByClass(heights: Record<string, number>) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function (this: HTMLElement) {
		for (const [className, height] of Object.entries(heights)) {
			if (this.classList.contains(className)) return height;
		}
		return 0;
	});
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

	it('shrinks rowsToShow when the rendered rows wrap taller than the container, instead of clipping content', () => {
		// The one-shot estimate off boardHeight alone would show 3 rows, but
		// the actually-rendered rows wrapper measures taller (simulating
		// flap rows that wrapped onto extra sub-rows) -- the shrink-effect must
		// correct rowsToShow down rather than leaving the overflow silently
		// clipped by `.board`'s `overflow: hidden`.
		mockClientHeightByClass({ board: 3 * ROW_HEIGHT_PX, 'rows-wrapper': 3 * ROW_HEIGHT_PX + 50 });

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three')] },
		});

		expect(container.querySelectorAll('.row').length).toBeLessThan(3);
		// Never shrinks all the way to zero -- at least the current row stays visible.
		expect(container.querySelectorAll('.row').length).toBeGreaterThanOrEqual(1);
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

	it('shows each line once, without repeating, when rowsToShow exceeds the line count', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, { props: { id: 'test', lines: [line('Alpha'), line('Beta')] } });

		const rowTexts = Array.from(container.querySelectorAll('.row')).map((row) => row.textContent?.trim());
		expect(rowTexts).toEqual(['Alpha', 'Beta']);
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

	it('jumps to the clicked page instead of advancing sequentially', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(2);

		(dots[1] as HTMLButtonElement).click();
		await tick();

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const texts = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));
		expect(texts[0]).toBe('Row D');
	});

	it('does not advance or re-flap when all content already fits on one page', async () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		// rowsToShow (4) is not a multiple of lines.length (3), so a stray
		// advance would shift the modulo-wrapped window and be visible here --
		// this isn't just coincidentally stable.
		const { container } = render(Flipboard, {
			props: { id: 'test', lines: ['One', 'Two', 'Three'].map(line), pauseSeconds: 5 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));

		await vi.advanceTimersByTimeAsync(60_000);

		const secondBatch = Array.from(container.querySelectorAll('.row')).map((row) => normalize(row.textContent));
		expect(secondBatch).toEqual(firstBatch);
		expect(localStorage.getItem('screensaver:cursor:test')).toBe('0');
	});

	it('does not reset a pending advance when the lines prop is replaced with a new array reference mid-countdown', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const initialLines = ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line);
		const { container, rerender } = render(Flipboard, {
			props: { id: 'test', lines: initialLines, pauseSeconds: 6 },
		});

		const totalDelay = revealDurationMs(['Row A', 'Row B', 'Row C']) + 6000;

		// Simulate a background data refresh (e.g. Discord re-polling) partway
		// through the countdown: same widget, a brand-new `lines` array
		// reference, and content whose length differs enough to change
		// revealDurationMs's computed value -- exactly the scenario that used
		// to cancel and reschedule the pending timeout with a fresh delay.
		await vi.advanceTimersByTimeAsync(totalDelay / 2);
		const refreshedLines = [line('Row A now with a lot more text than before'), ...initialLines.slice(1)];
		await rerender({ id: 'test', lines: refreshedLines, pauseSeconds: 6 });

		await vi.advanceTimersByTimeAsync(totalDelay / 2);

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		expect(normalize(container.querySelector('.row')?.textContent)).toBe('Row D');
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
