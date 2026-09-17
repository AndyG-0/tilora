import { render } from '@testing-library/svelte';
import { tick } from 'svelte';
import { describe, expect, it, vi, afterEach, beforeEach } from 'vitest';

import Plain from './Plain.svelte';
import plainSource from './Plain.svelte?raw';
import type { FormattedSegment } from '$lib/discordMarkdown';

const ROW_HEIGHT_PX = 64;

function line(text: string): FormattedSegment[] {
	return [{ text }];
}

function mockClientHeight(height: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(height);
}

describe('Plain', () => {
	beforeEach(() => {
		vi.useFakeTimers();
		localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it('shows the first line initially and advances to the next on a tick', async () => {
		const { container } = render(Plain, {
			props: { id: 'test', lines: [line('One'), line('Two')], pauseSeconds: 5 },
		});
		expect(container.querySelector('.text')?.textContent).toBe('One');

		await vi.advanceTimersByTimeAsync(5000);

		expect(container.querySelector('.text')?.textContent).toBe('Two');
	});

	it('shows multiple rows sized to the measured container height', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Plain, {
			props: { id: 'test', lines: ['One', 'Two', 'Three', 'Four', 'Five'].map(line) },
		});

		expect(container.querySelectorAll('.text')).toHaveLength(4);
	});

	it('shows each line once, without repeating, when rowsToShow exceeds the line count', () => {
		mockClientHeight(4 * ROW_HEIGHT_PX);

		const { container } = render(Plain, { props: { id: 'test', lines: [line('Alpha'), line('Beta')] } });

		const texts = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent?.trim());
		expect(texts).toEqual(['Alpha', 'Beta']);
	});

	it('does not advance when all content already fits on one page', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Plain, {
			props: { id: 'test', lines: ['One', 'Two'].map(line), pauseSeconds: 5 },
		});

		const firstBatch = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent);

		await vi.advanceTimersByTimeAsync(60_000);

		const secondBatch = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent);
		expect(secondBatch).toEqual(firstBatch);
	});

	it('advances by rowsToShow (not 1) per tick so consecutive ticks show fresh content', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Plain, {
			props: {
				id: 'test',
				lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line),
				pauseSeconds: 6,
			},
		});

		const firstBatch = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent);

		await vi.advanceTimersByTimeAsync(6000);

		const secondBatch = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent);
		expect(secondBatch).not.toEqual(firstBatch);
		expect(secondBatch[0]).toBe('Row D');
	});

	it('keeps the configured font on inline code spans instead of forcing monospace', () => {
		const { container } = render(Plain, {
			props: { id: 'test', lines: [[{ text: 'inline ' }, { text: 'code', code: true }]] },
		});

		const codeEl = container.querySelector('.text code');
		expect(codeEl).not.toBeNull();

		// jsdom doesn't inject component <style> blocks into the document, so
		// getComputedStyle can't see the cascade here (it always resolves
		// <code> to jsdom's own baked-in "monospace" UA default regardless of
		// author CSS) -- check the source rule directly instead.
		const codeRule = plainSource.match(/\.text :global\(code\)\s*{[^}]*}/)?.[0] ?? '';
		expect(codeRule).toContain('font-family: inherit');
	});

	it('jumps to the clicked page instead of advancing sequentially', async () => {
		mockClientHeight(3 * ROW_HEIGHT_PX);

		const { container } = render(Plain, {
			props: { id: 'test', lines: ['Row A', 'Row B', 'Row C', 'Row D', 'Row E', 'Row F'].map(line), pauseSeconds: 6 },
		});

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(2);

		(dots[1] as HTMLButtonElement).click();
		await tick();

		const texts = Array.from(container.querySelectorAll('.text')).map((el) => el.textContent);
		expect(texts[0]).toBe('Row D');
	});
});
