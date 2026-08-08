<script lang="ts">
	import type { NASAApodDetail } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let { data: apod }: { data: NASAApodDetail } = $props();
</script>

<h1>{apod.title || 'Astronomy Picture of the Day'}</h1>

{#if apod.available}
	<article class="apod">
		<h2>{apod.apod_title}</h2>
		{#if apod.date}
			<p class="date">{apod.date}</p>
		{/if}

		{#if apod.media_type === 'video' && apod.url}
			<div class="media video">
				<iframe src={apod.url} title={apod.apod_title} allowfullscreen></iframe>
			</div>
		{:else if apod.url}
			<img class="media image" src={apod.hdurl || apod.url} alt={apod.apod_title} loading="lazy" decoding="async" />
		{/if}

		{#if apod.explanation}
			<p class="explanation">{apod.explanation}</p>
		{/if}

		{#if apod.copyright}
			<p class="copyright">© {apod.copyright}</p>
		{/if}
	</article>
{:else}
	<p class="hint">{$_('nasa_apod.detail.unavailable')}</p>
{/if}

<style>
	.apod {
		max-width: 40rem;
	}

	.apod h2 {
		margin: 0 0 0.25rem;
	}

	.date {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0 0 1rem;
	}

	.media {
		width: 100%;
		border-radius: 0.75rem;
		margin-bottom: 1rem;
		display: block;
	}

	.media.image {
		height: auto;
		object-fit: contain;
	}

	.media.video {
		position: relative;
		aspect-ratio: 16 / 9;
		overflow: hidden;
	}

	.media.video iframe {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		border: none;
	}

	.explanation {
		line-height: 1.5;
	}

	.copyright {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
