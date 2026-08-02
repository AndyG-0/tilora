<script lang="ts">
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();
</script>

<TileCard {widgetId}>
	<div class="title">2048</div>
	<div class="preview">
		<span class="tile">2</span>
		<span class="tile">4</span>
		<span class="tile">8</span>
	</div>
	<div class="hint">Tap to play</div>
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}

	.preview {
		display: flex;
		gap: 0.35rem;
	}

	.tile {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 2.25rem;
		height: 2.25rem;
		border-radius: 0.4rem;
		background: var(--color-accent, var(--color-text-muted));
		color: var(--color-surface);
		font-weight: 600;
		opacity: 0.85;
	}

	.hint {
		margin-top: 0.5rem;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
</style>
