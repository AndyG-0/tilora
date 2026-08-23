<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	interface ModelRow {
		id: string;
		name: string;
		creator: string | null;
		coding_index: number | null;
		intelligence_index: number | null;
		blended_price_per_1m: number | null;
		output_tokens_per_second: number | null;
	}

	interface ArtificialAnalysisSummary {
		configured?: boolean;
		category: 'coding' | 'intelligence' | 'cost' | 'speed';
		stale?: boolean;
		fetched_at?: string;
		models: ModelRow[];
	}

	const METRIC_FIELD: Record<ArtificialAnalysisSummary['category'], keyof ModelRow> = {
		coding: 'coding_index',
		intelligence: 'intelligence_index',
		cost: 'blended_price_per_1m',
		speed: 'output_tokens_per_second',
	};

	function metricLabel(category: ArtificialAnalysisSummary['category'], value: number | null): string {
		if (value == null) return '—';
		if (category === 'cost') return `$${value.toFixed(2)}/1M`;
		if (category === 'speed') return `${value.toFixed(0)} tok/s`;
		return value.toFixed(1);
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<ArtificialAnalysisSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<ArtificialAnalysisSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="title">{$_('artificial_analysis.tile.title')}</div>
		{#if summary?.models?.length}
			<div class="list">
				{#each summary.models as model, i (model.id)}
					<div class="row">
						<span class="rank">{i + 1}</span>
						<span class="name" title={model.name}>{model.name}</span>
						<span class="metric"
							>{metricLabel(summary.category, model[METRIC_FIELD[summary.category]] as number | null)}</span
						>
					</div>
				{/each}
			</div>
			{#if summary.stale}
				<div class="stale-badge">{$_('artificial_analysis.tile.stale_badge')}</div>
			{/if}
		{:else if summary?.configured === false}
			<div class="condition">{$_('common.not_configured')}</div>
		{:else if summary}
			<div class="condition">{$_('common.no_data')}</div>
		{:else}
			<div class="condition">{$_('common.loading')}</div>
		{/if}
	</div>
</TileCard>

<style>
	.widget {
		display: flex;
		flex-direction: column;
		height: 100%;
		min-height: 0;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.5rem;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		min-height: 0;
		overflow-y: auto;
	}

	.row {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
	}

	.rank {
		flex-shrink: 0;
		width: 1.25rem;
		color: var(--color-text-muted);
	}

	.name {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.metric {
		flex-shrink: 0;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}

	.stale-badge {
		margin-top: 0.35rem;
		font-size: 0.7rem;
		color: var(--color-text-muted);
	}

	.condition {
		color: var(--color-text-muted);
	}
</style>
