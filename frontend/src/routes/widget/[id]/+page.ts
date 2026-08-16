import { get } from 'svelte/store';
import { api } from '$lib/api';
import { breakpoint } from '$lib/stores/breakpoint';
import type { PageLoad } from './$types';

// Auth is via httponly cookies with no hooks.server.ts to forward them, so
// (like every other route) this load must only ever run in the browser —
// a server-side SSR fetch would be cookie-less and 401 out into a 500.
export const ssr = false;

export const load: PageLoad = async ({ params }) => {
	const [widgets, detail] = await Promise.all([api.listWidgets(get(breakpoint)), api.widgetDetail(params.id)]);
	const widget = widgets.find((w) => w.id === params.id);
	return { widgetId: params.id, type: widget?.type, name: widget?.name, detail };
};
