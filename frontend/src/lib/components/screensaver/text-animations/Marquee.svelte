<script lang="ts">
	import { segmentsToHtml, type FormattedSegment } from '$lib/discordMarkdown';

	let { lines }: { lines: FormattedSegment[][] } = $props();

	// A fixed animation-duration paired with a track whose width scales with
	// content length makes longer content visibly speed up to cover more
	// distance in the same time. Deriving the duration from the measured
	// width keeps the crawl speed constant regardless of message length.
	const PX_PER_SECOND = 90;

	const SEPARATOR = '&nbsp;&nbsp;&nbsp;•&nbsp;&nbsp;&nbsp;';
	const joinedHtml = $derived(lines.map((line) => segmentsToHtml(line)).join(SEPARATOR) + SEPARATOR);
	let copyWidth = $state(0);
	const durationSeconds = $derived(copyWidth / PX_PER_SECOND);
</script>

<div class="viewport">
	<div class="track" style="animation-duration: {durationSeconds}s;">
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- segmentsToHtml only emits a hardcoded inline-tag set around escaped text, no raw markup passes through. -->
		<span bind:clientWidth={copyWidth}>{@html joinedHtml}</span>
		<!-- eslint-disable-next-line svelte/no-at-html-tags -- segmentsToHtml only emits a hardcoded inline-tag set around escaped text, no raw markup passes through. -->
		<span aria-hidden="true">{@html joinedHtml}</span>
	</div>
</div>

<style>
	.viewport {
		height: 100%;
		display: flex;
		align-items: center;
		overflow: hidden;
		white-space: nowrap;
	}

	.track {
		display: inline-flex;
		animation-name: marquee-scroll;
		animation-timing-function: linear;
		animation-iteration-count: infinite;
		font-size: clamp(2rem, 5vw, 4rem);
		font-weight: 600;
	}

	.track :global(strong) {
		font-weight: 900;
	}

	.track :global(em) {
		font-style: italic;
	}

	.track :global(u) {
		text-decoration: underline;
	}

	.track :global(s) {
		text-decoration: line-through;
	}

	.track :global(code) {
		font-family: 'Courier New', monospace;
		background: rgba(255, 255, 255, 0.15);
		border-radius: 0.2em;
		padding: 0 0.2em;
	}

	.track :global(.md-link) {
		text-decoration: underline dotted;
	}

	@keyframes marquee-scroll {
		from {
			transform: translateX(0%);
		}
		to {
			transform: translateX(-50%);
		}
	}
</style>
