import { render } from '@testing-library/svelte';
import { describe, expect, it, vi } from 'vitest';

import ScreenIndicator from './ScreenIndicator.svelte';

describe('ScreenIndicator', () => {
	it('renders nothing when there is only one page', () => {
		const { container } = render(ScreenIndicator, { props: { current: 0, total: 1 } });
		expect(container.querySelector('.indicator')).toBeNull();
	});

	it('renders nothing when total is zero', () => {
		const { container } = render(ScreenIndicator, { props: { current: 0, total: 0 } });
		expect(container.querySelector('.indicator')).toBeNull();
	});

	it('renders one dot per page, marking the current one active', () => {
		const { container } = render(ScreenIndicator, { props: { current: 1, total: 3 } });

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(3);
		expect(dots[0].classList.contains('active')).toBe(false);
		expect(dots[1].classList.contains('active')).toBe(true);
		expect(dots[2].classList.contains('active')).toBe(false);
	});

	it('renders plain, non-interactive spans when no onselect is given', () => {
		const { container } = render(ScreenIndicator, { props: { current: 0, total: 2 } });
		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(2);
		for (const dot of dots) expect(dot.tagName).toBe('SPAN');
	});

	it('renders clickable buttons when onselect is given, and calls it with the clicked page', () => {
		const onselect = vi.fn();
		const { container } = render(ScreenIndicator, { props: { current: 0, total: 3, onselect } });

		const dots = container.querySelectorAll('.dot');
		expect(dots).toHaveLength(3);
		for (const dot of dots) expect(dot.tagName).toBe('BUTTON');

		(dots[2] as HTMLButtonElement).click();
		expect(onselect).toHaveBeenCalledExactlyOnceWith(2);
	});

	it('stops a dot click from bubbling out to an ancestor listener', () => {
		const onselect = vi.fn();
		const parentClick = vi.fn();
		const { container } = render(ScreenIndicator, { props: { current: 0, total: 2, onselect } });

		container.addEventListener('click', parentClick);
		(container.querySelectorAll('.dot')[1] as HTMLButtonElement).click();

		expect(onselect).toHaveBeenCalledExactlyOnceWith(1);
		expect(parentClick).not.toHaveBeenCalled();
	});
});
