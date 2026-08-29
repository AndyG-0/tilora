<!-- Placeholder shown while a widget type's tile component is still being
     lazy-loaded (see $lib/lazyWidgetComponent) — fills the cell so the grid
     layout doesn't jump once the real component resolves. -->
<div class="skeleton" aria-hidden="true"></div>

<style>
	.skeleton {
		width: 100%;
		height: 100%;
		border-radius: 0.75rem;
		background: var(--color-border);
		animation: pulse 1.4s ease-in-out infinite;
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 0.4;
		}
		50% {
			opacity: 0.8;
		}
	}
</style>
