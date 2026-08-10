<script lang="ts">
	import { goto } from '$app/navigation';
	import type { Snippet } from 'svelte';

	let { widgetId, href, children }: { widgetId: string; href?: string; children: Snippet } = $props();

	function target() {
		return href ?? `/widget/${widgetId}`;
	}
</script>

<div
	class="tile"
	role="button"
	tabindex="0"
	onclick={() => goto(target())}
	onkeydown={(e) => {
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			goto(target());
		}
	}}
>
	{@render children()}
</div>

<style>
	.tile {
		display: block;
		width: 100%;
		height: 100%;
		text-align: left;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1.25rem;
		cursor: pointer;
		/* Touch-first: no hover-dependent affordance, generous tap target. */
		min-height: 8rem;
		overflow: hidden;
		/* Lets tile content (weather/date/clock) size itself off the actual
		   rendered box via cqw/cqh/cqmin instead of fixed viewport-relative
		   values, since users can drag-resize tiles to very different sizes. */
		container-type: size;
		container-name: tile;
	}

	.tile:active {
		background: var(--color-surface-hover);
	}
</style>
