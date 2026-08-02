import type { TabMeta, WidgetSummaryMeta } from '$lib/api';

export interface GroupedTab extends TabMeta {
	widgets: WidgetSummaryMeta[];
}

// Groups widgets by tab, ordered by the `tabs` list. A widget whose `tab`
// doesn't match a known tab id falls back to the first tab — defensive
// against a stale/missing /api/tabs response, shouldn't happen given the
// backend's own default-tab fallback.
export function groupWidgetsByTab(widgets: WidgetSummaryMeta[], tabs: TabMeta[]): GroupedTab[] {
	if (tabs.length === 0) return [];

	const knownIds = new Set(tabs.map((t) => t.id));
	const fallbackId = tabs[0].id;
	const grouped: Record<string, WidgetSummaryMeta[]> = Object.fromEntries(tabs.map((t) => [t.id, []]));

	for (const widget of widgets) {
		const tabId = knownIds.has(widget.tab) ? widget.tab : fallbackId;
		grouped[tabId].push(widget);
	}

	return tabs.map((t) => ({ ...t, widgets: grouped[t.id] }));
}

// Decides a swipe's direction from the raw touch delta, rejecting
// mostly-vertical drags so a widget's own vertical scroll isn't hijacked.
export function resolveSwipe(deltaX: number, deltaY: number, threshold = 50): -1 | 0 | 1 {
	if (Math.abs(deltaX) < threshold) return 0;
	if (Math.abs(deltaX) <= Math.abs(deltaY)) return 0;
	return deltaX < 0 ? 1 : -1;
}
