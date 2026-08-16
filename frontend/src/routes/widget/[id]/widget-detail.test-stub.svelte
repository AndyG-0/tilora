<script lang="ts">
	// Test-only stand-in for a real Detail component (e.g. PhotoDetail.svelte),
	// which seeds its local state once, non-reactively, from its initial
	// `data` prop. Used by page.test.ts to prove +page.svelte remounts it
	// (via {#key data.widgetId}) instead of reusing the instance across a
	// navigation between two widget detail pages.
	let { data: initialData }: { data: { label: string } } = $props();
	// svelte-ignore state_referenced_locally
	let label = $state(initialData.label);
</script>

<div data-testid="detail-label">{label}</div>
