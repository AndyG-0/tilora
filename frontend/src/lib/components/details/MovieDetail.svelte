<script lang="ts">
	import { page } from '$app/state';
	import { api, type MovieProvider } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface Movie {
		id: number;
		title: string;
		release_date: string | null;
		rating: number | null;
		poster_url: string | null;
		overview: string;
		where_to_watch: { name: string; logo_url: string | null; url: string | null }[];
	}

	interface MoviesDetailData {
		popular_movies?: Movie[];
		popular_tv_shows?: Movie[];
		trending_movies?: Movie[];
		trending_tv_shows?: Movie[];
		on_streaming_movies?: Movie[];
		on_streaming_tv_shows?: Movie[];
		region: string;
		categories: string[];
		providers: number[];
	}

	type MediaListKey =
		| 'popular_movies'
		| 'trending_movies'
		| 'popular_tv_shows'
		| 'trending_tv_shows'
		| 'on_streaming_movies'
		| 'on_streaming_tv_shows';

	const SECTIONS: { key: MediaListKey; titleKey: string }[] = [
		{ key: 'popular_movies', titleKey: 'movies.section.popular_movies' },
		{ key: 'trending_movies', titleKey: 'movies.section.trending_movies' },
		{ key: 'popular_tv_shows', titleKey: 'movies.section.popular_tv_shows' },
		{ key: 'trending_tv_shows', titleKey: 'movies.section.trending_tv_shows' },
		{ key: 'on_streaming_movies', titleKey: 'movies.section.on_streaming_movies' },
		{ key: 'on_streaming_tv_shows', titleKey: 'movies.section.on_streaming_tv_shows' },
	];

	const CATEGORY_OPTIONS = [
		{ key: 'popular_movies', labelKey: 'movies.section.popular_movies' },
		{ key: 'popular_tv', labelKey: 'movies.section.popular_tv_shows' },
		{ key: 'trending_movies', labelKey: 'movies.section.trending_movies' },
		{ key: 'trending_tv', labelKey: 'movies.section.trending_tv_shows' },
		{ key: 'on_streaming', labelKey: 'movies.category.on_streaming' },
	];

	let { data: initialData }: { data: MoviesDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let data = $state(initialData);

	let editingSettings = $state(false);
	let categoriesInput = $state<string[]>([]);
	let providersInput = $state<number[]>([]);
	let providerCatalog = $state<MovieProvider[]>([]);
	let loadingProviders = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);

	async function openEditor() {
		categoriesInput = [...data.categories];
		providersInput = [...data.providers];
		editingSettings = true;
		loadingProviders = true;
		try {
			providerCatalog = await api.movieProviders(data.region);
		} catch {
			providerCatalog = [];
		} finally {
			loadingProviders = false;
		}
	}

	function toggleCategory(key: string) {
		categoriesInput = categoriesInput.includes(key)
			? categoriesInput.filter((c) => c !== key)
			: [...categoriesInput, key];
	}

	function toggleProvider(id: number) {
		providersInput = providersInput.includes(id) ? providersInput.filter((p) => p !== id) : [...providersInput, id];
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, { categories: categoriesInput, providers: providersInput });
			data = await api.widgetDetail<MoviesDetailData>(page.params.id!);
			editingSettings = false;
		} catch {
			error = get(_)('movies.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

{#snippet mediaList(items: Movie[])}
	<div class="list">
		{#each items as item (item.id)}
			<div class="movie">
				{#if item.poster_url}
					<img class="poster" src={item.poster_url} alt={item.title} />
				{/if}
				<div class="info">
					<h2>{item.title}</h2>
					<p class="meta">
						{item.release_date ?? $_('movies.detail.unknown_release_date')}
						{#if item.rating}· {item.rating.toFixed(1)}★{/if}
					</p>
					<p class="overview">{item.overview}</p>
					{#if item.where_to_watch.length > 0}
						<p class="providers-label">{$_('movies.detail.streaming_in', { values: { region: data.region } })}</p>
						<div class="provider-chips">
							{#each item.where_to_watch as provider (provider.name)}
								{#if provider.url}
									<a class="chip" href={provider.url} target="_blank" rel="noreferrer">
										{#if provider.logo_url}
											<img src={provider.logo_url} alt="" />
										{/if}
										{provider.name}
									</a>
								{:else}
									<span class="chip">
										{#if provider.logo_url}
											<img src={provider.logo_url} alt="" />
										{/if}
										{provider.name}
									</span>
								{/if}
							{/each}
						</div>
					{:else}
						<p class="providers muted">{$_('movies.detail.not_streaming_in', { values: { region: data.region } })}</p>
					{/if}
				</div>
			</div>
		{/each}
	</div>
{/snippet}

<div class="header">
	<h1>Movies & Shows</h1>
	<button class="edit-settings" onclick={() => (editingSettings ? (editingSettings = false) : openEditor())}>
		{editingSettings ? $_('common.cancel') : $_('common.edit_settings')}
	</button>
</div>

{#if editingSettings}
	<div class="settings-form">
		<div class="categories">
			<span class="section-label">{$_('movies.detail.sections_label')}</span>
			<div class="categories-list">
				{#each CATEGORY_OPTIONS as option (option.key)}
					<label class="category">
						<input
							type="checkbox"
							checked={categoriesInput.includes(option.key)}
							onchange={() => toggleCategory(option.key)}
						/>
						{$_(option.labelKey)}
					</label>
				{/each}
			</div>
		</div>

		<div class="providers-picker">
			<span class="section-label">{$_('movies.detail.streaming_services_label')}</span>
			<p class="hint">{$_('movies.detail.providers_hint')}</p>
			{#if loadingProviders}
				<p class="hint">{$_('movies.detail.loading_providers')}</p>
			{:else}
				<div class="provider-chips">
					{#each providerCatalog as provider (provider.id)}
						<button
							type="button"
							class="chip"
							class:selected={providersInput.includes(provider.id)}
							onclick={() => toggleProvider(provider.id)}
						>
							{#if provider.logo_url}
								<img src={provider.logo_url} alt="" />
							{/if}
							{provider.name}
						</button>
					{/each}
				</div>
			{/if}
		</div>

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{/if}

{#each SECTIONS as section (section.key)}
	{@const items = data[section.key]}
	{#if items?.length}
		<h1>{$_(section.titleKey)}</h1>
		{@render mediaList(items)}
	{/if}
{/each}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0;
	}

	.edit-settings {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.settings-form {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		max-width: 34rem;
		margin: 1rem 0 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.section-label {
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form .hint {
		font-size: 0.8rem;
		margin: 0.15rem 0 0.5rem;
	}

	.categories-list {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem 1rem;
		margin-top: 0.25rem;
	}

	.category {
		display: flex;
		flex-direction: row;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.9rem;
	}

	.provider-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	.chip {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.3rem 0.75rem;
		color: var(--color-text);
		font: inherit;
		font-size: 0.85rem;
		cursor: pointer;
		text-decoration: none;
	}

	.chip img {
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 0.25rem;
		object-fit: cover;
	}

	.chip.selected {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.save {
		align-self: flex-start;
		background: var(--color-accent);
		color: var(--color-surface);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.hint {
		color: var(--color-text-muted);
		margin: 0.5rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}

	h1 {
		margin: 0 0 1rem;
	}

	h1:not(:first-child) {
		margin-top: 2rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1.5rem;
	}

	.movie {
		display: flex;
		gap: 1rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
	}

	.poster {
		width: 6rem;
		height: 9rem;
		object-fit: cover;
		border-radius: 0.5rem;
		flex-shrink: 0;
	}

	.info h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
	}

	.meta {
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}

	.overview {
		margin: 0 0 0.5rem;
	}

	.providers {
		font-size: 0.9rem;
		margin: 0;
	}

	.providers.muted {
		color: var(--color-text-muted);
	}

	.providers-label {
		font-size: 0.9rem;
		margin: 0 0 0.4rem;
	}
</style>
