<script lang="ts">
	let { text, color = '#ff8a00', weight = 500 }: { text: string; color?: string; weight?: number } = $props();
</script>

<div class="stack" style="--dotmatrix-color: {color}; --dotmatrix-weight: {weight}">
	<span class="text glow" aria-hidden="true">{text}</span>
	<span class="text dots">{text}</span>
</div>

<style>
	.stack {
		position: relative;
		display: grid;
	}

	.text {
		grid-area: 1 / 1;
		margin: 0;
		white-space: pre;
		font-family: 'Doto Variable', 'Courier New', monospace;
		font-variation-settings: 'wght' var(--dotmatrix-weight);
		font-weight: var(--dotmatrix-weight);
		font-size: inherit;
		letter-spacing: 0.03em;
	}

	/* Blurred solid-color copy behind the dots -- the glow's own blur must
	   never touch the dot pattern itself, or it fills the gaps between dots
	   and washes the grid into a solid glow. */
	.glow {
		color: var(--dotmatrix-color);
		filter: blur(0.08em);
		opacity: 0.75;
	}

	.dots {
		color: var(--dotmatrix-color);
	}
</style>
