<script lang="ts">
	import { locale, _ } from 'svelte-i18n';

	interface CalendarEvent {
		id: string;
		title: string;
		start: string;
		all_day: boolean;
		location: string | null;
		calendar?: string;
		color?: string | null;
	}

	interface CalendarScreensaverData {
		connected: boolean;
		provider?: 'google' | 'caldav' | 'microsoft';
		events: CalendarEvent[];
		calendar_ids?: string[];
		calendar_colors?: Record<string, string>;
	}

	let { data }: { data: CalendarScreensaverData } = $props();

	const showCalendarLabel = $derived(new Set(data.events.map((e) => e.calendar)).size > 1);
</script>

<div class="stage">
	<h1>Calendar</h1>
	{#if !data.connected}
		<p class="hint">{$_('calendar.screensaver.not_connected')}</p>
	{:else if data.events.length === 0}
		<p class="hint">{$_('calendar.detail.no_events')}</p>
	{:else}
		<div class="list">
			{#each data.events as event (event.id + event.start)}
				<div class="item">
					<h2><span class="dot" style:background={event.color ?? 'transparent'}></span>{event.title}</h2>
					<p class="meta">
						{event.all_day ? event.start : new Date(event.start).toLocaleString($locale ?? undefined)}
						{event.location ? ` · ${event.location}` : ''}
						{showCalendarLabel && event.calendar ? ` · ${event.calendar}` : ''}
					</p>
				</div>
			{/each}
		</div>
	{/if}
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		flex-direction: column;
		justify-content: center;
		max-width: 60rem;
		margin: 0 auto;
	}

	h1 {
		font-size: clamp(2rem, 5vw, 3rem);
		margin: 0 0 1.5rem;
		text-align: center;
	}

	.hint {
		color: var(--color-text-muted);
		font-size: 1.5rem;
		text-align: center;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
		max-height: 100%;
		overflow-y: auto;
	}

	.item {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1.25rem;
		padding: 1.5rem 2rem;
	}

	.item h2 {
		margin: 0 0 0.5rem;
		font-size: 2rem;
		display: flex;
		align-items: center;
	}

	.dot {
		display: inline-block;
		width: 1rem;
		height: 1rem;
		border-radius: 50%;
		margin-right: 0.75rem;
		flex-shrink: 0;
	}

	.meta {
		color: var(--color-text-muted);
		font-size: 1.1rem;
		margin: 0;
	}
</style>
