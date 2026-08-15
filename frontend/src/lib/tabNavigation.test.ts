import { describe, expect, it } from 'vitest';
import { groupWidgetsByTab, resolveSwipe } from './tabNavigation';
import type { TabMeta, WidgetSummaryMeta } from './api';

const layout = { col: 1, row: 1, colSpan: 1, rowSpan: 1 };

function widget(id: string, tab: string): WidgetSummaryMeta {
	return { id, type: 'stub', name: 'Stub', layout, tab };
}

describe('groupWidgetsByTab', () => {
	const tabs: TabMeta[] = [
		{ id: 'home', name: 'Home' },
		{ id: 'media', name: 'Media' },
	];

	it('groups widgets under their tab, ordered by the tabs list', () => {
		const widgets = [widget('a', 'media'), widget('b', 'home')];

		const result = groupWidgetsByTab(widgets, tabs);

		expect(result.map((t) => t.id)).toEqual(['home', 'media']);
		expect(result[0].widgets.map((w) => w.id)).toEqual(['b']);
		expect(result[1].widgets.map((w) => w.id)).toEqual(['a']);
	});

	it('falls back unknown tab ids to the first tab', () => {
		const widgets = [widget('a', 'nonexistent')];

		const result = groupWidgetsByTab(widgets, tabs);

		expect(result[0].widgets.map((w) => w.id)).toEqual(['a']);
		expect(result[1].widgets).toEqual([]);
	});

	it('returns an empty array when there are no tabs', () => {
		expect(groupWidgetsByTab([widget('a', 'home')], [])).toEqual([]);
	});
});

describe('resolveSwipe', () => {
	it('returns -1 for a rightward swipe past the threshold', () => {
		expect(resolveSwipe(80, 0)).toBe(-1);
	});

	it('returns 1 for a leftward swipe past the threshold', () => {
		expect(resolveSwipe(-80, 0)).toBe(1);
	});

	it('returns 0 when the swipe is under the threshold', () => {
		expect(resolveSwipe(20, 0)).toBe(0);
	});

	it('returns 0 for a mostly-vertical drag', () => {
		expect(resolveSwipe(60, 100)).toBe(0);
	});
});
