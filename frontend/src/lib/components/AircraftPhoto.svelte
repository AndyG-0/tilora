<script lang="ts">
	import AircraftIcon from '$lib/components/AircraftIcon.svelte';
	import { _ } from 'svelte-i18n';

	let {
		src = null,
		alt = '',
		kind = 'unknown',
		size = 'md',
		photographer = null,
		link = null,
	}: {
		src?: string | null;
		alt?: string;
		kind?: string | null;
		size?: 'sm' | 'md' | 'lg' | 'full';
		photographer?: string | null;
		link?: string | null;
	} = $props();

	let imgError = $state(false);
	let imgLoaded = $state(false);

	$effect(() => {
		// Reset state when src changes
		if (src) {
			imgError = false;
			imgLoaded = false;
		}
	});
</script>

<div class="aircraft-photo size-{size}" class:has-photo={Boolean(src && !imgError)}>
	{#if src && !imgError}
		<img
			{src}
			{alt}
			class="photo"
			class:loaded={imgLoaded}
			loading="lazy"
			onload={() => (imgLoaded = true)}
			onerror={() => (imgError = true)}
		/>
		{#if !imgLoaded}
			<div class="skeleton" aria-hidden="true"></div>
		{/if}
		{#if photographer && size !== 'sm'}
			{#if link}
				<a
					href={link}
					target="_blank"
					rel="noopener noreferrer"
					class="photographer-tag"
					title={$_('flights.detail.photo_by', { values: { name: photographer } })}
					onclick={(e) => e.stopPropagation()}
				>
					&copy; {photographer}
				</a>
			{:else}
				<span class="photographer-tag" title={$_('flights.detail.photo_by', { values: { name: photographer } })}>
					&copy; {photographer}
				</span>
			{/if}
		{/if}
	{:else}
		<div class="placeholder" title={$_('flights.detail.no_photo')}>
			<span class="placeholder-icon">
				<AircraftIcon {kind} label={$_(`flights.aircraft_kind.${kind ?? 'unknown'}`)} />
			</span>
			{#if size === 'lg' || size === 'full'}
				<span class="placeholder-text">{$_('flights.detail.no_photo')}</span>
			{/if}
		</div>
	{/if}
</div>

<style>
	.aircraft-photo {
		position: relative;
		border-radius: 0.5rem;
		overflow: hidden;
		background: var(--color-surface-hover, #1a1a1a);
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		border: 1px solid var(--color-border);
		box-sizing: border-box;
	}

	.size-sm {
		width: 3rem;
		height: 2.25rem;
	}

	.size-md {
		width: 5.5rem;
		height: 3.75rem;
	}

	.size-lg {
		width: 100%;
		height: 8.5rem;
	}

	.size-full {
		width: 100%;
		height: 100%;
		min-height: 7rem;
	}

	.photo {
		width: 100%;
		height: 100%;
		object-fit: cover;
		display: block;
		opacity: 0;
		transition: opacity 0.25s ease;
	}

	.photo.loaded {
		opacity: 1;
	}

	.skeleton {
		position: absolute;
		inset: 0;
		background: linear-gradient(
			90deg,
			rgba(255, 255, 255, 0.03) 25%,
			rgba(255, 255, 255, 0.08) 50%,
			rgba(255, 255, 255, 0.03) 75%
		);
		background-size: 200% 100%;
		animation: shimmer 1.5s infinite;
	}

	@keyframes shimmer {
		0% {
			background-position: 200% 0;
		}
		100% {
			background-position: -200% 0;
		}
	}

	.photographer-tag {
		position: absolute;
		bottom: 0.25rem;
		right: 0.25rem;
		background: rgba(0, 0, 0, 0.65);
		backdrop-filter: blur(4px);
		color: rgba(255, 255, 255, 0.85);
		font-size: 0.65rem;
		padding: 0.1rem 0.35rem;
		border-radius: 0.25rem;
		text-decoration: none;
		max-width: 80%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
		pointer-events: auto;
	}

	.photographer-tag:hover {
		color: #fff;
		background: rgba(0, 0, 0, 0.85);
	}

	.placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: 0.35rem;
		width: 100%;
		height: 100%;
		padding: 0.5rem;
		box-sizing: border-box;
		color: var(--color-text-muted);
		background: linear-gradient(135deg, rgba(255, 138, 0, 0.05) 0%, rgba(0, 0, 0, 0.2) 100%);
	}

	.placeholder-icon {
		width: 1.75rem;
		height: 1.75rem;
		display: flex;
		align-items: center;
		justify-content: center;
		opacity: 0.75;
	}

	.size-sm .placeholder-icon {
		width: 1.25rem;
		height: 1.25rem;
	}

	.placeholder-text {
		font-size: 0.7rem;
		text-transform: uppercase;
		letter-spacing: 0.04em;
		opacity: 0.8;
	}
</style>
