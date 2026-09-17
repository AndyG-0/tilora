<script lang="ts">
	import { _ } from 'svelte-i18n';

	let { current, total, onselect }: { current: number; total: number; onselect?: (page: number) => void } = $props();

	// The screensaver exits on any bubbled pointerdown/touchstart/keydown/click
	// (see +layout.svelte's window-level activity listeners and Screensaver.svelte's
	// own onclick/onkeydown) -- stopping propagation here is what lets a dot be
	// clicked/tapped to change page without also being treated as the "user is
	// active, dismiss the screensaver" gesture. `pointermove`/`wheel` are left
	// alone so hovering or scrolling elsewhere still dismisses as before.
	//
	// These must be *capture*-phase listeners: Svelte 5 delegates bubble-phase
	// events like onclick/onpointerdown to a single root-level listener, so
	// calling stopPropagation() inside a bubble-phase handler here runs too
	// late to block ancestor listeners (e.g. +layout.svelte's window
	// listeners) that already fired during native bubbling before Svelte's
	// delegated dispatch reaches this handler. Capture-phase listeners are
	// attached directly to the button and run before the event ever bubbles.
	function stopPropagation(event: Event) {
		event.stopPropagation();
	}

	function handleSelect(event: MouseEvent, page: number) {
		event.stopPropagation();
		onselect?.(page);
	}
</script>

{#if total > 1}
	<div class="indicator" role="presentation">
		{#each { length: total }, i (i)}
			{#if onselect}
				<button
					type="button"
					class="dot"
					class:active={i === current}
					aria-label={$_('screensaver.go_to_page', { values: { page: i + 1 } })}
					aria-current={i === current}
					onpointerdowncapture={stopPropagation}
					ontouchstartcapture={stopPropagation}
					onkeydowncapture={stopPropagation}
					onclickcapture={(event) => handleSelect(event, i)}
				></button>
			{:else}
				<span class="dot" class:active={i === current}></span>
			{/if}
		{/each}
	</div>
{/if}

<style>
	.indicator {
		position: absolute;
		bottom: 1rem;
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		gap: 0.5rem;
		padding: 0.4rem 0.7rem;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.35);
		backdrop-filter: blur(2px);
		z-index: 1;
	}

	.dot {
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.4);
		transition: all 0.2s ease;
	}

	button.dot {
		border: none;
		padding: 0;
		cursor: pointer;
	}

	.dot.active {
		background: #fff;
		width: 0.7rem;
		height: 0.7rem;
	}
</style>
