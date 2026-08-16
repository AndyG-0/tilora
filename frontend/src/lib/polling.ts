import { onMount } from 'svelte';

// Floor on the poll interval regardless of what a caller passes in — guards
// against a misconfigured or missing refresh_interval_seconds (e.g. 0 from
// an absent backend value) hammering the backend with a near-zero interval.
const MIN_INTERVAL_MS = 5000;

// Every tile fetches its summary once on mount, then again on a fixed
// interval until it unmounts — this was duplicated verbatim (refresh() +
// setInterval + clearInterval cleanup) across ~20 tile components.
export function pollWidget(refresh: () => void, intervalMs: number): void {
	onMount(() => {
		refresh();
		const interval = setInterval(refresh, Math.max(intervalMs, MIN_INTERVAL_MS));
		return () => clearInterval(interval);
	});
}
