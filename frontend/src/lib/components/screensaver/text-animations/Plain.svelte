<script lang="ts">
	import { untrack } from 'svelte';
	import { segmentsToHtml, type FormattedSegment } from '$lib/discordMarkdown';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';
	import ScreenIndicator from '../ScreenIndicator.svelte';

	// Conservative estimate of one row's rendered height (the .text rule's
	// clamp(1.5rem, 4vw, 3rem) font-size at ~1.2 line-height, plus the .rows
	// gap between stacked lines) -- not pixel-perfect, just enough to size
	// how many rows fit.
	const ROW_HEIGHT_PX = 64;

	let {
		id,
		lines,
		pauseSeconds = 8,
		fontFamily,
		fontScale = 1,
	}: {
		id: string;
		lines: FormattedSegment[][];
		pauseSeconds?: number;
		fontFamily?: string;
		fontScale?: number;
	} = $props();

	let index = $state(getCursor(id));
	let panelHeight = $state(0);
	let rowsWrapperHeight = $state(0);
	let rowsToShow = $state(1);

	// Optimistic starting guess for each new tick's content -- a fresh
	// estimate rather than something that has to grow back after the
	// shrink-effect below trimmed it for the previous (possibly longer) tick.
	$effect(() => {
		void index;
		rowsToShow = Math.max(1, Math.floor(panelHeight / ROW_HEIGHT_PX));
	});

	// Long lines wrap onto extra visual rows (see `.text`'s overflow-wrap
	// below), which the estimate above can't account for. Shrink the row
	// count until the actually-rendered rows fit within the panel, rather
	// than truncating/clipping whatever doesn't fit. `rowsToShow` itself is
	// read/written untracked so this only reruns on a genuinely new
	// measurement (a real resize-observer tick) instead of retriggering
	// itself synchronously on every decrement.
	$effect(() => {
		if (rowsWrapperHeight > panelHeight) {
			untrack(() => {
				if (rowsToShow > 1) rowsToShow -= 1;
			});
		}
	});

	$effect(() => {
		if (totalPages <= 1) return;
		const interval = setInterval(() => (index = (index + rowsToShow) % lines.length), pauseSeconds * 1000);
		return () => clearInterval(interval);
	});

	$effect(() => {
		setCursor(id, index);
	});

	// Capped at `lines.length` -- when there's less content than fits the
	// screen (rowsToShow > lines.length), show each line once instead of
	// wrapping the modulo back around to pad out the remaining rows with
	// repeats of content already on screen.
	const visibleLines = $derived(
		Array.from(
			{ length: Math.min(rowsToShow, lines.length) },
			(_, r) => (lines.length ? lines[(index + r) % lines.length] : []) ?? [],
		),
	);
	const visibleHtml = $derived(visibleLines.map((line) => segmentsToHtml(line)));

	const totalPages = $derived(Math.max(1, Math.ceil(lines.length / rowsToShow)));
	const currentPage = $derived(Math.floor(index / rowsToShow) % totalPages);

	function goToPage(page: number) {
		index = (page * rowsToShow) % lines.length;
	}
</script>

<div
	class="panel"
	bind:clientHeight={panelHeight}
	style:--screensaver-font-family={fontFamily}
	style:--screensaver-font-scale={fontScale}
>
	{#key index}
		<div class="rows" bind:clientHeight={rowsWrapperHeight}>
			{#each visibleHtml as html, r (r)}
				<!-- eslint-disable-next-line svelte/no-at-html-tags -- segmentsToHtml only emits a hardcoded inline-tag set around escaped text, no raw markup passes through. -->
				<p class="text">{@html html}</p>
			{/each}
		</div>
	{/key}
	<ScreenIndicator current={currentPage} total={totalPages} onselect={goToPage} />
</div>

<style>
	.panel {
		position: relative;
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		background: #111;
		overflow: hidden;
	}

	.rows {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
		animation: fade-in 0.6s ease-out;
	}

	.text {
		max-width: 90%;
		margin: 0;
		text-align: left;
		color: #f2f2f2;
		font-family: var(--screensaver-font-family, system-ui, sans-serif);
		font-size: calc(clamp(1.5rem, 4vw, 3rem) * var(--screensaver-font-scale, 1));
		overflow-wrap: break-word;
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
		font-family: inherit;
		opacity: 0.85;
	}

	.text :global(.md-link) {
		text-decoration: underline dotted;
	}

	@keyframes fade-in {
		from {
			opacity: 0;
		}
		to {
			opacity: 1;
		}
	}
</style>
