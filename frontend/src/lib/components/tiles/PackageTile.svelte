<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import type { PackagesSummary } from '$lib/api';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<PackagesSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<PackagesSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="widget">
		<div class="header">
			<span class="title">{summary?.title ?? 'Packages'}</span>
			{#if summary && summary.arriving_today_count > 0}
				<span class="badge">{summary.arriving_today_count}</span>
			{/if}
		</div>
		{#if summary}
			{#if summary.arriving_today.length > 0}
				<div class="subheading">{$_('packages.tile.arriving_today')}</div>
				<ul class="items">
					{#each summary.arriving_today as pkg (pkg.id)}
						<li>
							<span class="text">{pkg.label || pkg.tracking_number}</span>
							{#if pkg.carrier}
								<span class="carrier">{pkg.carrier}</span>
							{/if}
						</li>
					{/each}
				</ul>
			{:else if summary.active_count > 0}
				<div class="empty">{$_('packages.tile.in_transit', { values: { count: summary.active_count } })}</div>
			{:else}
				<div class="empty">{$_('packages.tile.nothing_tracked')}</div>
			{/if}
		{:else}
			<div class="empty">{$_('common.loading')}</div>
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

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.badge {
		flex-shrink: 0;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-radius: 999px;
		font-size: 0.75rem;
		line-height: 1;
		padding: 0.25rem 0.5rem;
	}

	.subheading {
		font-size: 0.75rem;
		color: var(--color-text-muted);
		margin-bottom: 0.25rem;
		flex-shrink: 0;
	}

	.items {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.items li {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.text {
		font-size: 0.95rem;
		line-height: 1.3;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.carrier {
		flex-shrink: 0;
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.items::-webkit-scrollbar {
		width: 4px;
	}

	.items::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
