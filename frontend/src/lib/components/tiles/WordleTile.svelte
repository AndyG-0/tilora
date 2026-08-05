<script lang="ts">
	import TileCard from '$lib/components/TileCard.svelte';

	let { widgetId }: { widgetId: string } = $props();
</script>

<TileCard {widgetId}>
	<div class="title">Wordle</div>
	<div class="preview">
		<span class="cell" data-status="correct">W</span>
		<span class="cell" data-status="present">O</span>
		<span class="cell" data-status="absent">R</span>
		<span class="cell" data-status="absent">D</span>
		<span class="cell" data-status="correct">S</span>
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
		gap: 0.3rem;
	}

	.cell {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 1.75rem;
		height: 1.75rem;
		border-radius: 0.3rem;
		font-weight: 700;
		font-size: 0.9rem;
	}

	.cell[data-status='correct'] {
		background: var(--color-success);
		color: var(--color-on-accent);
	}

	.cell[data-status='present'] {
		background: var(--color-warning);
		color: var(--color-on-accent);
	}

	.cell[data-status='absent'] {
		background: var(--color-surface-hover, var(--color-border));
		color: var(--color-text-muted);
	}

	.hint {
		margin-top: 0.5rem;
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}
</style>
