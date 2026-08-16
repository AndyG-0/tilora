<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api, type QBittorrentSummary } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<QBittorrentSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<QBittorrentSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	function formatSpeed(bps: number | undefined): string {
		const mbps = ((bps ?? 0) * 8) / 1_000_000;
		return `${mbps.toFixed(1)} Mbps`;
	}
</script>

<TileCard {widgetId}>
	{#if !summary}
		<div class="status">{$_('qbittorrent.tile.loading')}</div>
	{:else if !summary.connected}
		<div class="title">qBittorrent</div>
		<div class="status">{$_('common.not_connected')}</div>
	{:else}
		<div class="header">
			<div class="title">qBittorrent</div>
			<div class="count">{$_('qbittorrent.tile.torrent_count', { values: { count: summary.torrent_count ?? 0 } })}</div>
		</div>
		<div class="speeds">
			<div class="speed down">↓ {formatSpeed(summary.download_speed_bps)}</div>
			<div class="speed up">↑ {formatSpeed(summary.upload_speed_bps)}</div>
		</div>
		<div class="status">
			{$_('qbittorrent.tile.status', {
				values: { downloading: summary.downloading_count ?? 0, seeding: summary.seeding_count ?? 0 },
			})}
		</div>
	{/if}
</TileCard>

<style>
	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
	}

	.count {
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	.speeds {
		display: flex;
		gap: 1rem;
		font-size: 1.5rem;
		font-weight: 600;
		line-height: 1.1;
	}

	.speed.down {
		color: var(--color-accent);
	}

	.speed.up {
		color: var(--color-success);
	}

	.status {
		color: var(--color-text-muted);
	}
</style>
