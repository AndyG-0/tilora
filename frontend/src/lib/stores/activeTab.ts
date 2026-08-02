import { writable } from 'svelte/store';

// Survives client-side navigation to /widget/[id] and back, so the
// dashboard resumes on the same tab instead of resetting to the first one.
export const activeTabIndex = writable(0);
