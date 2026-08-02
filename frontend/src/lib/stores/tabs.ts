import { readable } from 'svelte/store';
import { api, type TabMeta } from '$lib/api';

const DEFAULT_TABS: TabMeta[] = [{ id: 'default', name: 'Dashboard' }];

export const tabs = readable<TabMeta[]>(DEFAULT_TABS, (set) => {
	api
		.tabs()
		.then(set)
		.catch(() => {
			// keep the seeded single-tab default
		});
});
