<script lang="ts">
	import { segmentsToChars, type FormattedSegment } from '$lib/discordMarkdown';

	// Conservative estimate of one .line row's rendered height (its
	// clamp(1.5rem, 4vw, 3rem) font-size at ~1.2 line-height, plus its 1rem
	// top+bottom padding) -- not pixel-perfect, just enough to size how many
	// rows fit.
	const ROW_HEIGHT_PX = 90;

	// Matches the .ch rule's per-character animation-delay step and the
	// .ch keyframes' animation-duration below.
	const CHAR_DELAY_MS = 30;
	const MATERIALIZE_DURATION_MS = 500;

	let { lines, pauseSeconds = 8 }: { lines: FormattedSegment[][]; pauseSeconds?: number } = $props();

	let index = $state(0);
	let matrixHeight = $state(0);

	const rowsToShow = $derived(Math.max(1, Math.floor(matrixHeight / ROW_HEIGHT_PX)));

	const visibleLines = $derived(
		Array.from({ length: rowsToShow }, (_, r) => (lines.length ? lines[(index + r) % lines.length] : []) ?? []),
	);
	const visibleChars = $derived(visibleLines.map(segmentsToChars));

	// All rows materialize in parallel, so the reveal is only as long as the
	// longest visible line takes -- but that's still enough to eat into a
	// fixed-length cycle on tall/wordy panels, so guarantee a full
	// `pauseSeconds` of static read time on top of it rather than folding
	// the reveal time into the cycle. Character count (not raw source
	// length) drives the timing so a redacted spoiler's placeholder length
	// paces the reveal, not the original hidden text's length.
	const revealDurationMs = $derived(
		Math.max(0, ...visibleChars.map((chars) => chars.length)) * CHAR_DELAY_MS + MATERIALIZE_DURATION_MS,
	);

	$effect(() => {
		if (lines.length <= 1) return;
		const timeout = setTimeout(
			() => (index = (index + rowsToShow) % lines.length),
			revealDurationMs + pauseSeconds * 1000,
		);
		return () => clearTimeout(timeout);
	});

	// Same falling-glyph-column technique as ClockFace's MatrixFace: a fixed
	// set of columns, each a long run of random glyphs duplicated back-to-back
	// and scrolled via a CSS keyframe, generated once so it's cheap to leave
	// running on an always-on kiosk display.
	const GLYPHS = '0123456789アイウエオカキクケコサシスセソタチツテト';
	const COLUMN_COUNT = 20;
	const CHARS_PER_COLUMN = 30;

	function randomGlyphs(count: number): string[] {
		return Array.from({ length: count }, () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)]);
	}

	const columns = Array.from({ length: COLUMN_COUNT }, (_, i) => ({
		left: (i / COLUMN_COUNT) * 100,
		duration: 4 + Math.random() * 5,
		delay: -Math.random() * 8,
		glyphs: [...randomGlyphs(CHARS_PER_COLUMN), ...randomGlyphs(CHARS_PER_COLUMN)],
	}));
</script>

<div class="matrix" bind:clientHeight={matrixHeight}>
	<div class="rain">
		{#each columns as column, i (i)}
			<div
				class="column"
				style="left: {column.left}%; animation-duration: {column.duration}s; animation-delay: {column.delay}s;"
			>
				{#each column.glyphs as glyph, j (j)}
					<span>{glyph}</span>
				{/each}
			</div>
		{/each}
	</div>
	<div class="lines">
		{#key index}
			{#each visibleChars as chars, r (r)}
				<div class="line">
					{#each chars as { ch, bold, italic, underline, strike, code, link, spoiler }, i (i)}
						<span
							class="ch"
							class:bold
							class:italic
							class:underline
							class:strike
							class:code
							class:link
							class:spoiler
							style="animation-delay: {i * CHAR_DELAY_MS}ms;">{ch === ' ' ? ' ' : ch}</span
						>
					{/each}
				</div>
			{/each}
		{/key}
	</div>
</div>

<style>
	.matrix {
		position: relative;
		width: 100%;
		height: 100%;
		background: #050805;
		overflow: hidden;
		display: flex;
		align-items: center;
		justify-content: center;
	}

	.rain {
		position: absolute;
		inset: 0;
	}

	.column {
		position: absolute;
		top: 0;
		display: flex;
		flex-direction: column;
		align-items: center;
		font-family: 'Courier New', monospace;
		font-size: 1.1rem;
		line-height: 1.3em;
		color: #1caa3f;
		opacity: 0.7;
		animation-name: fall;
		animation-timing-function: linear;
		animation-iteration-count: infinite;
	}

	.column span:first-child {
		color: #b6ffcf;
	}

	@keyframes fall {
		from {
			transform: translateY(0);
		}
		to {
			transform: translateY(-50%);
		}
	}

	.lines {
		position: relative;
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: 0.5rem;
	}

	.line {
		position: relative;
		max-width: 90%;
		text-align: center;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		font-size: clamp(1.5rem, 4vw, 3rem);
		color: #4dff8f;
		background: rgba(2, 8, 3, 0.6);
		padding: 1rem 2rem;
		border-radius: 0.5rem;
	}

	.ch {
		display: inline-block;
		text-shadow:
			0 0 6px #22ff66,
			0 0 16px #0f9c3f;
		animation-name: materialize;
		animation-duration: 500ms;
		animation-timing-function: ease-out;
		animation-fill-mode: backwards;
	}

	.ch.bold {
		font-weight: 900;
	}

	.ch.italic {
		font-style: italic;
	}

	.ch.underline {
		text-decoration: underline;
	}

	.ch.strike {
		text-decoration: line-through;
	}

	.ch.code {
		opacity: 0.85;
	}

	.ch.link {
		text-decoration: underline dotted;
	}

	.ch.spoiler {
		color: #2a4a32;
		text-shadow: none;
	}

	@keyframes materialize {
		from {
			opacity: 0;
			letter-spacing: 0.4em;
		}
		to {
			opacity: 1;
			letter-spacing: normal;
		}
	}
</style>
