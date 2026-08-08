import { render } from '@testing-library/svelte';
import { describe, expect, it, vi, afterEach } from 'vitest';

import Marquee from './Marquee.svelte';
import type { FormattedSegment } from '$lib/discordMarkdown';

const PX_PER_SECOND = 90;

function line(text: string, format: Omit<FormattedSegment, 'text'> = {}): FormattedSegment[] {
	return [{ text, ...format }];
}

function mockClientWidth(width: number) {
	return vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(width);
}

describe('Marquee', () => {
	afterEach(() => {
		vi.restoreAllMocks();
	});

	it('derives animation-duration from the measured width of one copy, not a fixed value', () => {
		mockClientWidth(450);

		const { container } = render(Marquee, { props: { lines: [line('Short')] } });

		const track = container.querySelector('.track') as HTMLElement;
		expect(track.style.animationDuration).toBe(`${450 / PX_PER_SECOND}s`);
	});

	it('produces a longer duration for wider (longer) content at the same px/sec rate', () => {
		mockClientWidth(1800);

		const { container } = render(Marquee, {
			props: { lines: [line('A much longer line of text that would render much wider on screen')] },
		});

		const track = container.querySelector('.track') as HTMLElement;
		expect(track.style.animationDuration).toBe(`${1800 / PX_PER_SECOND}s`);
	});

	it('renders two copies of the joined lines for a seamless loop', () => {
		mockClientWidth(300);

		const { container } = render(Marquee, { props: { lines: [line('One'), line('Two')] } });

		const spans = container.querySelectorAll('.track > span');
		expect(spans).toHaveLength(2);
		expect(spans[0].textContent).toContain('One');
		expect(spans[0].textContent).toContain('Two');
		expect(spans[1].textContent).toEqual(spans[0].textContent);
	});

	it('renders formatted segments as their corresponding inline elements', () => {
		mockClientWidth(300);

		const { container } = render(Marquee, {
			props: { lines: [[{ text: 'bold', bold: true }, { text: ' plain' }]] },
		});

		const track = container.querySelector('.track') as HTMLElement;
		expect(track.querySelector('strong')?.textContent).toBe('bold');
	});
});
