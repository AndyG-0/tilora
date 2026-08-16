<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { api } from '$lib/api';
	import { _, locale } from 'svelte-i18n';
	import TileCard from '$lib/components/TileCard.svelte';

	interface CalendarEvent {
		id: string;
		title: string;
		start: string;
		all_day: boolean;
		location: string | null;
		color?: string | null;
	}

	interface CalendarSummary {
		connected: boolean;
		events: CalendarEvent[];
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	let summary = $state<CalendarSummary | null>(null);

	async function refresh() {
		try {
			summary = await api.widgetSummary<CalendarSummary>(widgetId);
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	function formatEventTime(event: CalendarEvent): string {
		const date = new Date(event.start);
		return event.all_day
			? new Intl.DateTimeFormat($locale ?? undefined, { weekday: 'short', month: 'short', day: 'numeric' }).format(date)
			: new Intl.DateTimeFormat($locale ?? undefined, {
					weekday: 'short',
					hour: 'numeric',
					minute: '2-digit',
				}).format(date);
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);
</script>

<TileCard {widgetId}>
	<div class="title">Calendar</div>
	{#if !summary}
		<div class="empty">{$_('calendar.tile.loading')}</div>
	{:else if !summary.connected}
		<div class="empty">{$_('common.not_connected')}</div>
	{:else if summary.events.length}
		<ul class="events">
			{#each summary.events as event (event.id)}
				<li>
					<span class="dot" style:background={event.color ?? 'transparent'}></span>
					<span class="time">{formatEventTime(event)}</span>
					<span class="event-title">{event.title}</span>
				</li>
			{/each}
		</ul>
	{:else}
		<div class="empty">{$_('calendar.tile.no_events')}</div>
	{/if}
</TileCard>

<style>
	.title {
		font-size: 1rem;
		font-weight: 600;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
	}

	.events {
		margin: 0;
		padding: 0;
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		overflow: hidden;
	}

	.events li {
		display: flex;
		align-items: center;
		gap: 0.4rem;
		font-size: 0.95rem;
		line-height: 1.3;
		overflow: hidden;
	}

	.dot {
		flex: none;
		width: 0.5rem;
		height: 0.5rem;
		border-radius: 50%;
	}

	.time {
		flex: none;
		font-size: 0.8rem;
		color: var(--color-text-muted);
	}

	.event-title {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.empty {
		color: var(--color-text-muted);
	}
</style>
