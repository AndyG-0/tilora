import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import Matrix from './Matrix.svelte';
import type { FormattedSegment } from '$lib/discordMarkdown';

const ROW_HEIGHT_PX = 90;
const CHAR_DELAY_MS = 30;
const MATERIALIZE_DURATION_MS = 500;

function line(text: string): FormattedSegment[] {
	return [{ text }];
}

function mockClientHeight(height: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
}

// Mocks .matrix's and .lines's clientHeight independently, so a test can
// simulate content that wraps onto more visual rows than the one-shot
// estimate predicted (i.e. the rendered .lines wrapper measuring taller than
// the .matrix container that's supposed to hold it).
function mockClientHeightByClass(heights: Record<string, number>) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockImplementation(function (this: HTMLElement) {
		for (const [className, height] of Object.entries(heights)) {
			if (this.classList.contains(className)) return height;
		}
		return 0;
	});
}

describe('Matrix', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('shows a single line when the container is too short for more', () => {
		mockClientHeight(40);

		const { container } = render(Matrix, { props: { id: 'test', lines: [line('One'), line('Two'), line('Three')] } });

		expect(container.querySelectorAll('.line')).toHaveLength(1);
	});

	it('shows multiple lines sized to the measured container height', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three'), line('Four'), line('Five')] },
		});

		expect(container.querySelectorAll('.line')).toHaveLength(4);
	});

	it('shows each line once, without repeating, when rowsToShow exceeds the line count', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, { props: { id: 'test', lines: [line('Alpha'), line('Beta')] } });

		const lineTexts = Array.from(container.querySelectorAll('.line')).map((el) => el.textContent?.trim());
		expect(lineTexts).toEqual(['Alpha', 'Beta']);
	});

	it('advances by rowsToShow (not 1) per tick so consecutive ticks show fresh content', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		await vi.advanceTimersByTimeAsync(revealDurationMs + 6000);

		const secondBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));
		expect(secondBatch).not.toEqual(firstBatch);
		expect(secondBatch[0]).toBe('Row D');
	});

	it('does not advance or re-materialize when all content already fits on one page', async () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		// rowsToShow (4) is not a multiple of lines.length (3), so a stray
		// advance would shift the modulo-wrapped window and be visible here --
		// this isn't just coincidentally stable.
		const { container } = render(Matrix, {
			props: { id: 'test', lines: ['One', 'Two', 'Three'].map(line), pauseSeconds: 5 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		await vi.advanceTimersByTimeAsync(60_000);

		const secondBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));
		expect(secondBatch).toEqual(firstBatch);
		expect(localStorage.getItem('screensaver:cursor:test')).toBe('0');
	});

	it('does not reset a pending advance when the lines prop is replaced with a new array reference mid-countdown', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const initialLines = ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line);
		const { container, rerender } = render(Matrix, {
			props: { id: 'test', lines: initialLines, pauseSeconds: 6 },
		});

		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		const totalDelay = revealDurationMs + 6000;

		// Simulate a background data refresh (e.g. Discord re-polling) partway
		// through the countdown: same widget, a brand-new `lines` array
		// reference, and content whose length differs enough to change the
		// derived reveal duration's value -- exactly the scenario that used to
		// cancel and reschedule the pending timeout with a fresh delay.
		await vi.advanceTimersByTimeAsync(totalDelay / 2);
		const refreshedLines = [line('Row A now with a lot more text than before'), ...initialLines.slice(1)];
		await rerender({ id: 'test', lines: refreshedLines, pauseSeconds: 6 });

		await vi.advanceTimersByTimeAsync(totalDelay / 2);

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		expect(normalize(container.querySelector('.line')?.textContent)).toBe('Row D');
	});

	it('holds the full pauseSeconds of static read time after the reveal finishes', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		await vi.advanceTimersByTimeAsync(revealDurationMs + 5999);
		expect(Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent))).toEqual(firstBatch);

		await vi.advanceTimersByTimeAsync(1);
		expect(Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent))).not.toEqual(
			firstBatch,
		);
	});

	it('shrinks rowsToShow when the rendered lines wrap taller than the container, instead of clipping content', () => {
		// The one-shot estimate off matrixHeight alone would show 3 rows, but
		// the actually-rendered .lines wrapper measures taller (simulating
		// wrapped lines) -- the shrink-effect must correct rowsToShow down
		// rather than leaving the overflow silently clipped by `overflow: hidden`.
		mockClientHeightByClass({ matrix: 3 * ROW_HEIGHT_PX, lines: 3 * ROW_HEIGHT_PX + 50 });

		const { container } = render(Matrix, {
			props: { id: 'test', lines: [line('One'), line('Two'), line('Three')] },
		});

		expect(container.querySelectorAll('.line').length).toBeLessThan(3);
		// Never shrinks all the way to zero -- at least the current row stays visible.
		expect(container.querySelectorAll('.line').length).toBeGreaterThanOrEqual(1);
	});

	it('renders formatted segments as per-character classed spans', () => {
		mockClientHeight(ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { id: 'test', lines: [[{ text: 'ab', bold: true }, { text: 'c' }]] },
		});

		const chars = Array.from(container.querySelectorAll('.ch'));
		expect(chars.map((el) => el.textContent)).toEqual(['a', 'b', 'c']);
		expect(chars[0].classList.contains('bold')).toBe(true);
		expect(chars[1].classList.contains('bold')).toBe(true);
		expect(chars[2].classList.contains('bold')).toBe(false);
	});

	it('drives reveal timing off the exploded char count of a spoiler placeholder, matching a same-length plain line', async () => {
		mockClientHeight(2 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: {
				id: 'test',
				lines: [[{ text: 'Row A' }], [{ text: '\u2588\u2588\u2588\u2588\u2588', spoiler: true }]],
				pauseSeconds: 6,
			},
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		// Both lines are 5 characters (redacted spoiler placeholder sized to
		// match), so the reveal duration should be identical to the plain
		// 5-char case -- proving timing comes from the exploded char count,
		// not some other notion of the spoiler's original hidden length.
		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		await vi.advanceTimersByTimeAsync(revealDurationMs + 5999);
		expect(Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent))).toEqual(firstBatch);
	});

	it('jumps to the clicked page instead of advancing sequentially', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(2);

		(dots[1] as HTMLButtonElement).click();
		await tick();

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const texts = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));
		expect(texts[0]).toBe('Row D');
	});
});
