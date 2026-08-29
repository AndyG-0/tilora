import { get, writable } from 'svelte/store';
import { api, describeFetchError, type FetchErrorKind, type WidgetLayout, type WidgetSummaryMeta } from '$lib/api';
import { breakpoint } from './breakpoint';

export const widgets = writable<WidgetSummaryMeta[]>([]);

// Lets the screensaver's fallback UI distinguish "widget list hasn't loaded
// yet" from "it failed to load" instead of both looking like an empty list.
export const widgetsLoadError = writable<FetchErrorKind | null>(null);

export function reloadWidgets() {
	return api
		.listWidgets(get(breakpoint))
		.then((result) => {
			widgets.set(result);
			widgetsLoadError.set(null);
		})
		.catch((error) => {
			// keep whatever was last loaded successfully
			widgetsLoadError.set(describeFetchError(error));
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
	widgets.update((current) => (current.some((w) => w.id === widget.id) ? current : [...current, widget]));
}

export function removeWidgetLocal(id: string) {
	widgets.update((current) => current.filter((widget) => widget.id !== id));
}

// Fires immediately on subscribe (covering the initial load) and again on
// every subsequent breakpoint change (e.g. a tablet rotated, or the browser
// window resized across the 700px threshold), keeping the widget list's
// layout in sync with whichever breakpoint's positions now apply.
breakpoint.subscribe(() => reloadWidgets());
