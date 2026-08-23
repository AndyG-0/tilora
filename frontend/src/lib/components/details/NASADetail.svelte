<script lang="ts">
	import type { NASAApodDetail } from '$lib/api';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

	let { data: apod }: { data: NASAApodDetail } = $props();
</script>

<h1>{apod.title || $_('nasa_apod.detail.default_title')}</h1>

{#if apod.available}
	<article class="apod">
		<h2>{apod.apod_title}</h2>
		{#if apod.date}
			<p class="date">{apod.date}</p>
		{/if}
		{#if apod.stale && apod.fetched_at}
			<p class="stale-note">
				{$_('nasa_apod.detail.stale_notice', {
					values: { date: new Date(apod.fetched_at).toLocaleString(get(locale) ?? undefined) },
				})}
			</p>
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

	.stale-note {
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
