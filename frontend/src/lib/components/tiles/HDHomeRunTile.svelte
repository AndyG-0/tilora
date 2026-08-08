<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { goto } from '$app/navigation';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { _ } from 'svelte-i18n';

	interface NowPlayingEntry {
		channel_number: string;
		channel_name: string;
		title: string;
		episode_title: string | null;
	}

	interface HDHomeRunSummary {
		tuner_connected: boolean;
		dvr_connected: boolean;
		channel_count: number;
		guide_available: boolean;
		now_playing: NowPlayingEntry[];
		active_recordings_count: number;
	}

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<HDHomeRunSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<HDHomeRunSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);
</script>

<TileCard {widgetId}>
	<div class="frame">
		<div class="title">
			HDHomeRun
			{#if summary?.active_recordings_count}
				<span class="recording-badge">{$_('hdhomerun.tile.recording_badge')}</span>
			{/if}
		</div>
		{#if !summary}
			<div class="hint">{$_('common.loading')}</div>
		{:else if !summary.tuner_connected && !summary.dvr_connected}
			<div class="hint">{$_('common.not_connected')}</div>
		{:else}
			{#if summary.tuner_connected}
				<div class="channel-count">
					{$_('hdhomerun.tile.channel_count', { values: { count: summary.channel_count } })}
				</div>
			{/if}
			{#if summary.guide_available}
				<ul class="now-playing">
					{#each summary.now_playing as entry (entry.channel_number)}
						<li>
							<button
								class="entry"
								onclick={(e) => {
									e.stopPropagation();
									goto(`/widget/${widgetId}?watch=${entry.channel_number}`);
								}}
							>
								<span class="channel">{entry.channel_number}</span>
								<span class="entry-text">
									<span class="entry-title">{entry.title}</span>
									{#if entry.channel_name}<span class="entry-sub">{entry.channel_name}</span>{/if}
									{#if entry.episode_title}<span class="entry-sub">{entry.episode_title}</span>{/if}
								</span>
							</button>
						</li>
					{/each}
				</ul>
			{:else if summary.tuner_connected}
				<div class="hint">{$_('hdhomerun.tile.guide_unavailable')}</div>
			{/if}
		{/if}
	</div>
</TileCard>

<style>
	.frame {
		display: flex;
		flex-direction: column;
		width: 100%;
		height: 100%;
		overflow: hidden;
	}

	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin: 0 0 0.35rem;
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.recording-badge {
		color: var(--color-error);
		font-size: 0.8rem;
	}

	.channel-count {
		font-size: 1.1rem;
	}

	.now-playing {
		list-style: none;
		margin: 0.35rem 0 0;
		padding: 0;
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		font-size: 0.9rem;
		flex: 1;
		min-height: 0;
		overflow-y: auto;
	}

	.entry {
		display: flex;
		align-items: baseline;
		gap: 0.35rem;
		width: 100%;
		background: none;
		border: none;
		padding: 0.15rem 0;
		font: inherit;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.now-playing .channel {
		color: var(--color-text-muted);
		flex-shrink: 0;
	}

	.entry-text {
		display: flex;
		flex-direction: column;
		min-width: 0;
	}

	.entry-title {
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.entry-sub {
		font-size: 0.8rem;
		color: var(--color-text-muted);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
