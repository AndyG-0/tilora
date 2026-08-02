import { writable } from 'svelte/store';
import { api, type WidgetLayout, type WidgetSummaryMeta } from '$lib/api';

export const widgets = writable<WidgetSummaryMeta[]>([]);

export function reloadWidgets() {
	return api
		.listWidgets()
		.then(widgets.set)
		.catch(() => {
			// keep whatever was last loaded successfully
		});
}

// The caller of a layout/add/remove mutation already knows exactly what
// changed (it built the new layout, or the server handed back the new
// widget), so patching the store locally avoids a full-list refetch after
// every drag/resize/add/remove.
export function applyLayoutUpdates(updates: { id: string; layout: WidgetLayout }[]) {
	widgets.update((current) =>
		current.map((widget) => {
			const update = updates.find((u) => u.id === widget.id);
			return update ? { ...widget, layout: update.layout } : widget;
		}),
	);
}

export function addWidgetLocal(widget: WidgetSummaryMeta) {
	widgets.update((current) => [...current, widget]);
}

export function removeWidgetLocal(id: string) {
	widgets.update((current) => current.filter((widget) => widget.id !== id));
}

reloadWidgets();
