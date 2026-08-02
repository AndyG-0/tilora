import { api } from '$lib/api';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ params }) => {
	const [widgets, detail] = await Promise.all([api.listWidgets(), api.widgetDetail(params.id)]);
	const widget = widgets.find((w) => w.id === params.id);
	return { widgetId: params.id, type: widget?.type, detail };
};
