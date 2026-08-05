<script lang="ts">
	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const formatted = $derived(
		new Intl.DateTimeFormat(undefined, {
			timeZone: timezone,
			hour: 'numeric',
			minute: '2-digit',
			second: '2-digit',
			hourCycle: 'h23',
		}).format(now),
	);

	// A fixed set of "falling code" columns, each a long run of random
	// glyphs duplicated back-to-back and scrolled via a CSS keyframe
	// (0% -> -50% translateY, looping) — a seamless rain effect with no JS
	// animation loop or canvas, so it's cheap to leave running on an
	// always-on kiosk display. Generated once at component creation, not
	// regenerated on every tick (`now` updates every second via $derived
	// elsewhere, but this plain `const` only runs when the component mounts).
	const GLYPHS = '0123456789アイウエオカキクケコサシスセソタチツテト';
	const COLUMN_COUNT = 16;
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

<div class="matrix" class:large={size === 'detail'}>
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
	<div class="time">{formatted}</div>
</div>

<style>
	.matrix {
		position: relative;
		width: 100%;
		height: 100%;
		min-height: 6rem;
		background: #050805;
		border-radius: 0.5rem;
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
		font-size: 0.75rem;
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

	.time {
		position: relative;
		font-family: 'Courier New', monospace;
		font-weight: 700;
		font-size: 1.8rem;
		font-variant-numeric: tabular-nums;
		color: #4dff8f;
		text-shadow:
			0 0 6px #22ff66,
			0 0 16px #0f9c3f;
		background: rgba(2, 8, 3, 0.55);
		padding: 0.3rem 0.75rem;
		border-radius: 0.3rem;
	}

	.matrix.large .time {
		font-size: 3.5rem;
		padding: 0.5rem 1.25rem;
	}

	.matrix.large .column {
		font-size: 1.1rem;
	}
</style>
