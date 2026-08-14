<script lang="ts">
	import { untrack } from 'svelte';
	import { segmentsToHtml, type FormattedSegment } from '$lib/discordMarkdown';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';

	// Conservative estimate of one row's rendered height (the .text rule's
	// clamp(1.5rem, 4vw, 3rem) font-size at ~1.2 line-height, plus the .rows
	// gap between stacked lines) -- not pixel-perfect, just enough to size
	// how many rows fit.
	const ROW_HEIGHT_PX = 64;

	let {
		id,
		lines,
		pauseSeconds = 8,
		color = '#ff8a00',
	}: { id: string; lines: FormattedSegment[][]; pauseSeconds?: number; color?: string } = $props();

	let index = $state(getCursor(id));
	let signHeight = $state(0);
	let rowsWrapperHeight = $state(0);
	let rowsToShow = $state(1);

	// Optimistic starting guess for each new tick's content -- a fresh
	// estimate rather than something that has to grow back after the
	// shrink-effect below trimmed it for the previous (possibly longer) tick.
	$effect(() => {
		void index;
		rowsToShow = Math.max(1, Math.floor(signHeight / ROW_HEIGHT_PX));
	});

	// Long lines wrap onto extra visual rows (see `.text`'s overflow-wrap
	// below), which the estimate above can't account for. Shrink the row
	// count until the actually-rendered rows fit within the sign, rather
	// than truncating/ellipsizing whatever doesn't fit. `rowsToShow` itself
	// is read/written untracked so this only reruns on a genuinely new
	// measurement (a real resize-observer tick) instead of retriggering
	// itself synchronously on every decrement.
	$effect(() => {
		if (rowsWrapperHeight > signHeight) {
			untrack(() => {
				if (rowsToShow > 1) rowsToShow -= 1;
			});
		}
	});

	$effect(() => {
		if (lines.length <= 1) return;
		const interval = setInterval(() => (index = (index + rowsToShow) % lines.length), pauseSeconds * 1000);
		return () => clearInterval(interval);
	});

	$effect(() => {
		setCursor(id, index);
	});

	const visibleLines = $derived(
		Array.from({ length: rowsToShow }, (_, r) => (lines.length ? lines[(index + r) % lines.length] : []) ?? []),
	);
	const visibleHtml = $derived(visibleLines.map((line) => segmentsToHtml(line)));
</script>

<div class="sign" style="--dotmatrix-color: {color}" bind:clientHeight={signHeight}>
	{#key index}
		<div class="rows" bind:clientHeight={rowsWrapperHeight}>
			{#each visibleHtml as html, r (r)}
				<div class="stack">
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- segmentsToHtml only emits a hardcoded inline-tag set around escaped text, no raw markup passes through. -->
					<p class="text glow" aria-hidden="true">{@html html}</p>
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- segmentsToHtml only emits a hardcoded inline-tag set around escaped text, no raw markup passes through. -->
					<p class="text dots">{@html html}</p>
				</div>
			{/each}
		</div>
	{/key}
</div>

<style>
	.sign {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #0a0a0a;
		overflow: hidden;
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.stack {
		position: relative;
		max-width: 90%;
	}

	.text {
		grid-area: 1 / 1;
		text-align: left;
		margin: 0;
		font-family: 'Doto Variable', 'Courier New', monospace;
		font-variation-settings: 'wght' 300;
		font-weight: 100;
		font-size: clamp(1.5rem, 4vw, 3rem);
		letter-spacing: 0.05em;
		overflow-wrap: break-word;

		/* animation: flicker 3s ease-in-out infinite; */
	}

	.stack {
		display: grid;
	}

	/* Blurred solid-color copy behind the dots — the glow's own blur must
	   never touch the dot pattern itself, or it fills the gaps between dots
	   and washes the grid into a solid glow (the original bug here). */

	.glow {
		color: var(--dotmatrix-color);
		filter: blur(0.08em);
		opacity: 0.75;
	}

	.text :global(strong) {
		font-weight: 900;
	}

	.text :global(em) {
		font-style: italic;
	}

	.text :global(u) {
		text-decoration: underline;
	}

	.text :global(s) {
		text-decoration: line-through;
	}

	.text :global(code) {
		font-family: 'Courier New', monospace;
		opacity: 0.85;
	}

	.text :global(.md-link) {
		text-decoration: underline dotted;
	}

	@keyframes flicker {
		0%,
		92%,
		100% {
			opacity: 1;
		}
		94% {
			opacity: 0.85;
		}
	}
</style>
