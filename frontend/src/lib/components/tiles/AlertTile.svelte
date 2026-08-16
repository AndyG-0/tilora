<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type Alert } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { playChime } from '$lib/speech';
	import { _ } from 'svelte-i18n';

	interface AlertSummary {
		count: number;
		most_urgent: Alert | null;
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<AlertSummary | null>(null);
	let seenAlertId: number | null = null;
	let firstLoad = true;

	async function refresh() {
		try {
			summary = await api.widgetSummary<AlertSummary>(widgetId);
			const currentId = summary.most_urgent?.id ?? null;
			if (currentId !== null && currentId !== seenAlertId && !firstLoad) {
				playChime();
			}
			seenAlertId = currentId;
			firstLoad = false;
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="title">Alerts</div>
	{#if summary?.most_urgent}
		<div class="alert severity-{summary.most_urgent.severity}">
			{#if summary.count > 1}
				<span class="badge">{summary.count}</span>
			{/if}
			<p class="message">{summary.most_urgent.message}</p>
		</div>
	{:else}
		<div class="empty">{$_('alert.tile.empty')}</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}

	.alert {
		display: flex;
		align-items: baseline;
		gap: 0.5rem;
		border-left: 4px solid var(--alert-color, var(--color-text-muted));
		padding-left: 0.6rem;
	}

	.severity-info {
		--alert-color: var(--color-info);
	}

	.severity-warning {
		--alert-color: var(--color-warning);
	}

	.severity-critical {
		--alert-color: var(--color-error);
	}

	.badge {
		flex-shrink: 0;
		background: var(--alert-color);
		color: var(--color-on-accent);
		border-radius: 999px;
		font-size: 0.75rem;
		line-height: 1;
		padding: 0.25rem 0.5rem;
	}

	.message {
		margin: 0;
		font-size: 0.95rem;
		line-height: 1.3;
		overflow: hidden;
		text-overflow: ellipsis;
		display: -webkit-box;
		-webkit-line-clamp: 3;
		line-clamp: 3;
		-webkit-box-orient: vertical;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
