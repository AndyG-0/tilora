import { render } from '@testing-library/svelte';
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

describe('Matrix', () => {
	beforeEach(() => {
		vi.useFakeTimers();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('shows a single line when the container is too short for more', () => {
		mockClientHeight(40);

		const { container } = render(Matrix, { props: { lines: [line('One'), line('Two'), line('Three')] } });

		expect(container.querySelectorAll('.line')).toHaveLength(1);
	});

	it('shows multiple lines sized to the measured container height', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { lines: [line('One'), line('Two'), line('Three'), line('Four'), line('Five')] },
		});

		expect(container.querySelectorAll('.line')).toHaveLength(4);
	});

	it('wraps around the lines array via modulo when rowsToShow exceeds the line count', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, { props: { lines: [line('Alpha'), line('Beta')] } });

		const lineTexts = Array.from(container.querySelectorAll('.line')).map((el) => el.textContent?.trim());
		expect(lineTexts).toEqual([lineTexts[0], lineTexts[1], lineTexts[0], lineTexts[1]]);
	});

	it('advances by rowsToShow (not 1) per tick so consecutive ticks show fresh content', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const normalize = (text: string | null | undefined) => text?.replace(/\u00A0/g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		await vi.advanceTimersByTimeAsync(revealDurationMs + 6000);

		const secondBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));
		expect(secondBatch).not.toEqual(firstBatch);
		expect(secondBatch[0]).toBe('Row D');
	});

	it('holds the full pauseSeconds of static read time after the reveal finishes', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
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

	it('renders formatted segments as per-character classed spans', () => {
		mockClientHeight(ROW_HEIGHT_PX);

		const { container } = render(Matrix, {
			props: { lines: [[{ text: 'ab', bold: true }, { text: 'c' }]] },
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
				lines: [[{ text: 'Row A' }], [{ text: '\u2588\u2588\u2588\u2588\u2588', spoiler: true }]],
				pauseSeconds: 6,
			},
		});

		const normalize = (text: string | null | undefined) => text?.replace(/ /g, ' ').trim();
		const firstBatch = Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent));

		// Both lines are 5 characters (redacted spoiler placeholder sized to
		// match), so the reveal duration should be identical to the plain
		// 5-char case -- proving timing comes from the exploded char count,
		// not some other notion of the spoiler's original hidden length.
		const revealDurationMs = 'Row A'.length * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS;
		await vi.advanceTimersByTimeAsync(revealDurationMs + 5999);
		expect(Array.from(container.querySelectorAll('.line')).map((el) => normalize(el.textContent))).toEqual(firstBatch);
	});
});
