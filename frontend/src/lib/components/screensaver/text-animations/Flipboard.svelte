<script lang="ts">
	import { segmentsToChars, type FormattedSegment } from '$lib/discordMarkdown';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';

	// Conservative estimate of one flap row's rendered height (the .flap
	// rule's clamp(1.6rem, 3.2vw, 2.6rem) height plus its 0.1rem top+bottom
	// margin) -- not pixel-perfect, just enough to size how many rows fit.
	// A line longer than one row's worth of flaps wraps onto extra rows via
	// `.row`'s flex-wrap rather than being truncated, so this is only used
	// to size how far `index` advances per tick, not a hard content limit.
	const ROW_HEIGHT_PX = 48;

	// Per-character flap delay, and the extra pause between one row finishing
	// its flaps and the next row starting -- together these make the board
	// fill in left-to-right within a row and top-to-bottom across rows,
	// rather than every row flapping in at once.
	const CHAR_DELAY_MS = 25;
	const ROW_GAP_MS = 120;
	// Matches the .flap rule's animation-duration below -- how long the very
	// last flap takes to finish its own flip once its delay elapses.
	const FLAP_DURATION_MS = 400;

	let {
		id,
		lines,
		pauseSeconds = 8,
		pattern = 'top_to_bottom',
	}: {
		id: string;
		lines: FormattedSegment[][];
		pauseSeconds?: number;
		pattern?: 'top_to_bottom' | 'random';
	} = $props();

	let index = $state(getCursor(id));
	let boardHeight = $state(0);

	const rowsToShow = $derived(Math.max(1, Math.floor(boardHeight / ROW_HEIGHT_PX)));

	const visibleLines = $derived(
		Array.from({ length: rowsToShow }, (_, r) => (lines.length ? lines[(index + r) % lines.length] : []) ?? []),
	);
	const visibleChars = $derived(visibleLines.map(segmentsToChars));

	const rowStartDelays = $derived(
		visibleChars.reduce<number[]>((delays, chars, r) => {
			delays.push(r === 0 ? 0 : delays[r - 1] + visibleChars[r - 1].length * CHAR_DELAY_MS + ROW_GAP_MS);
			return delays;
		}, []),
	);

	// Total time for every row to finish flapping in, so the hold below is a
	// real `pauseSeconds` of static read time on top of the reveal -- not
	// `pauseSeconds` minus however long the cascade happened to take, which
	// otherwise shrinks (or vanishes) as more/longer rows are shown.
	const revealDurationMs = $derived(
		visibleChars.length === 0
			? 0
			: rowStartDelays[rowStartDelays.length - 1] +
					visibleChars[visibleChars.length - 1].length * CHAR_DELAY_MS +
					FLAP_DURATION_MS,
	);

	function advanceIndex() {
		if (pattern === 'random' && lines.length > rowsToShow) {
			let next = Math.floor(Math.random() * lines.length);
			if (next === index) next = (next + 1) % lines.length;
			index = next;
		} else {
			index = (index + rowsToShow) % lines.length;
		}
	}

	$effect(() => {
		if (lines.length <= 1) return;
		const timeout = setTimeout(advanceIndex, revealDurationMs + pauseSeconds * 1000);
		return () => clearTimeout(timeout);
	});

	$effect(() => {
		setCursor(id, index);
	});
</script>

<div class="board" bind:clientHeight={boardHeight}>
	{#key index}
		{#each visibleChars as chars, r (r)}
			<div class="row">
				{#each chars as { ch, bold, italic, underline, strike, code, link, spoiler }, i (i)}
					<span
						class="flap"
						class:bold
						class:italic
						class:underline
						class:strike
						class:code
						class:link
						class:spoiler
						style="animation-delay: {rowStartDelays[r] + i * CHAR_DELAY_MS}ms;">{ch === ' ' ? ' ' : ch}</span
					>
				{/each}
			</div>
		{/each}
	{/key}
</div>

<style>
	.board {
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: left;
		justify-content: left;
		background: #111;
		overflow: hidden;
	}

	.row {
		display: flex;
		flex-wrap: wrap;
		justify-content: left;
		max-width: 90%;
	}

	.flap {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		width: clamp(1.1rem, 2.2vw, 1.8rem);
		height: clamp(1.6rem, 3.2vw, 2.6rem);
		margin: 0.1rem;
		background: #222;
		color: #f2f2f2;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		font-size: clamp(1rem, 2vw, 1.6rem);
		border-radius: 0.15rem;
		box-shadow: inset 0 -2px 0 rgba(0, 0, 0, 0.4);
		animation-name: flap-flip;
		animation-duration: 400ms;
		animation-timing-function: ease-in;
		animation-fill-mode: backwards;
		transform-origin: center;
	}

	.flap.bold {
		font-weight: 900;
	}

	.flap.italic {
		font-style: italic;
	}

	.flap.underline {
		text-decoration: underline;
	}

	.flap.strike {
		text-decoration: line-through;
	}

	.flap.code {
		background: #333;
		color: #9fe6a0;
	}

	.flap.link {
		text-decoration: underline dotted;
	}

	.flap.spoiler {
		background: #000;
		color: #000;
	}

	@keyframes flap-flip {
		0% {
			transform: rotateX(90deg);
			opacity: 0;
		}
		60% {
			transform: rotateX(-20deg);
			opacity: 1;
		}
		100% {
			transform: rotateX(0deg);
		}
	}
</style>
