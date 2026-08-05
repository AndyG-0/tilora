import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import BinaryFace from './BinaryFace.svelte';

describe('BinaryFace', () => {
	it('lights the dots matching the BCD digits of each time component', () => {
		// 10:30:15 UTC -> H:1,0 M:3,0 S:1,5
		const now = new Date('2024-03-15T10:30:15Z');

		render(BinaryFace, { props: { now, timezone: 'UTC', size: 'tile' } });

		const face = screen.getByRole('img', { name: 'Binary clock face' });
		const columns = face.querySelectorAll('.column');
		expect(columns).toHaveLength(6);

		// Column 0 = hours tens digit = 1 -> bits [8,4,2,1] = [0,0,0,1]
		const litStates = (colIndex: number) =>
			Array.from(columns[colIndex].querySelectorAll('.dot')).map((dot) => dot.classList.contains('lit'));

		expect(litStates(0)).toEqual([false, false, false, true]); // H tens: 1
		expect(litStates(1)).toEqual([false, false, false, false]); // H ones: 0
		expect(litStates(2)).toEqual([false, false, true, true]); // M tens: 3
		expect(litStates(3)).toEqual([false, false, false, false]); // M ones: 0
		expect(litStates(4)).toEqual([false, false, false, true]); // S tens: 1
		expect(litStates(5)).toEqual([false, true, false, true]); // S ones: 5
	});
});
