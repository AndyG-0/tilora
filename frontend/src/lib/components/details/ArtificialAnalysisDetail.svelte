<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { _ } from 'svelte-i18n';
	import { get } from 'svelte/store';

	type Category = 'coding' | 'intelligence' | 'cost' | 'speed';

	interface ModelRow {
		id: string;
		name: string;
		creator: string | null;
		release_date: string | null;
		intelligence_index: number | null;
		coding_index: number | null;
		agentic_index: number | null;
		price_input_per_1m: number | null;
		price_output_per_1m: number | null;
		blended_price_per_1m: number | null;
		output_tokens_per_second: number | null;
		time_to_first_token_seconds: number | null;
	}

	interface ArtificialAnalysisDetailData {
		configured?: boolean;
		category: Category;
		stale?: boolean;
		fetched_at?: string;
		models: ModelRow[];
	}

	const CATEGORY_TABS: { key: Category; labelKey: string }[] = [
		{ key: 'coding', labelKey: 'artificial_analysis.category.coding' },
		{ key: 'intelligence', labelKey: 'artificial_analysis.category.intelligence' },
		{ key: 'cost', labelKey: 'artificial_analysis.category.cost' },
		{ key: 'speed', labelKey: 'artificial_analysis.category.speed' },
	];

	// [sort field, true = ascending]
	const SORT_KEY: Record<Category, [keyof ModelRow, boolean]> = {
		coding: ['coding_index', false],
		intelligence: ['intelligence_index', false],
		cost: ['blended_price_per_1m', true],
		speed: ['output_tokens_per_second', false],
	};

	let { data: initialData }: { data: ArtificialAnalysisDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let data = $state(initialData);

	// Ephemeral browsing tab, independent of the persisted `category`
	// setting (which only controls what the tile shows).
	let activeCategory = $state<Category>(initialData.category);
	let searchInput = $state('');

	let editingSettings = $state(false);
	let categoryInput = $state<Category>(initialData.category);
	let saving = $state(false);
	let error = $state<string | null>(null);

	const widgetId = $derived(page.params.id!);

	const rankedModels = $derived.by(() => {
		const [sortField, ascending] = SORT_KEY[activeCategory];
		const query = searchInput.trim().toLowerCase();
		return data.models
			.filter((m) => m[sortField] != null)
			.filter((m) => !query || m.name.toLowerCase().includes(query) || (m.creator ?? '').toLowerCase().includes(query))
			.sort((a, b) => {
				const diff = (a[sortField] as number) - (b[sortField] as number);
				return ascending ? diff : -diff;
			});
	});

	function metricLabel(model: ModelRow): string {
		if (activeCategory === 'coding') return model.coding_index != null ? model.coding_index.toFixed(1) : '—';
		if (activeCategory === 'intelligence')
			return model.intelligence_index != null ? model.intelligence_index.toFixed(1) : '—';
		if (activeCategory === 'cost')
			return model.blended_price_per_1m != null ? `$${model.blended_price_per_1m.toFixed(2)}/1M` : '—';
		return model.output_tokens_per_second != null ? `${model.output_tokens_per_second.toFixed(0)} tok/s` : '—';
	}

	function openEditor() {
		categoryInput = data.category;
		editingSettings = true;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(widgetId, { category: categoryInput });
			data = await api.widgetDetail<ArtificialAnalysisDetailData>(widgetId);
			editingSettings = false;
		} catch {
			error = get(_)('artificial_analysis.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{$_('artificial_analysis.detail.title')}</h1>
	<button class="edit-settings" onclick={() => (editingSettings ? (editingSettings = false) : openEditor())}>
		{editingSettings ? $_('common.cancel') : $_('common.edit_settings')}
	</button>
</div>

{#if editingSettings}
	<div class="settings-form">
		<span class="section-label">{$_('artificial_analysis.detail.default_category_label')}</span>
		<div class="tabs">
			{#each CATEGORY_TABS as tab (tab.key)}
				<button
					type="button"
					class="tab"
					class:selected={categoryInput === tab.key}
					onclick={() => (categoryInput = tab.key)}
				>
					{$_(tab.labelKey)}
				</button>
			{/each}
		</div>
		{#if error}
			<p class="hint error">{error}</p>
		{/if}
		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if data.configured === false}
	<p class="hint">{$_('common.not_configured')}</p>
{:else}
	{#if data.stale && data.fetched_at}
		<p class="hint stale">
			{$_('artificial_analysis.detail.stale_data', {
				values: { fetched_at: new Date(data.fetched_at).toLocaleString() },
			})}
		</p>
	{/if}

	<div class="tabs">
		{#each CATEGORY_TABS as tab (tab.key)}
			<button
				type="button"
				class="tab"
				class:selected={activeCategory === tab.key}
				onclick={() => (activeCategory = tab.key)}
			>
				{$_(tab.labelKey)}
			</button>
		{/each}
	</div>

	<input
		class="search"
		type="text"
		placeholder={$_('artificial_analysis.detail.search_placeholder')}
		bind:value={searchInput}
	/>

	{#if rankedModels.length === 0}
		<p class="hint">{$_('common.no_data')}</p>
	{:else}
		<div class="list">
			{#each rankedModels as model, i (model.id)}
				<div class="row">
					<span class="rank">{i + 1}</span>
					<div class="info">
						<span class="name">{model.name}</span>
						{#if model.creator}<span class="creator">{model.creator}</span>{/if}
					</div>
					<span class="metric">{metricLabel(model)}</span>
				</div>
			{/each}
		</div>
	{/if}
{/if}

<style>
	.header {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 1rem;
	}

	.header h1 {
		margin: 0 0 1rem;
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

	.tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		margin: 0.5rem 0 1rem;
	}

	.tab {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		padding: 0.35rem 0.9rem;
		color: var(--color-text);
		font: inherit;
		font-size: 0.9rem;
		cursor: pointer;
	}

	.tab.selected {
		border-color: var(--color-accent);
		color: var(--color-accent);
	}

	.search {
		width: 100%;
		max-width: 24rem;
		margin: 0 0 1rem;
		padding: 0.5rem 0.75rem;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		background: var(--color-surface);
		color: var(--color-text);
		font: inherit;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.75rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.6rem 1rem;
	}

	.rank {
		flex-shrink: 0;
		width: 1.5rem;
		color: var(--color-text-muted);
		text-align: right;
	}

	.info {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
	}

	.name {
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.creator {
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.metric {
		flex-shrink: 0;
		font-variant-numeric: tabular-nums;
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
		margin: 0.5rem 0 1rem;
	}

	.hint.error {
		color: var(--color-error);
	}

	.hint.stale {
		font-size: 0.85rem;
	}
</style>
