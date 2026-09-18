<script lang="ts">
	import { untrack } from 'svelte';
	import { locale, _ } from 'svelte-i18n';
	import { getCursor, setCursor } from '$lib/stores/screensaverProgress';
	import ScreenIndicator from './ScreenIndicator.svelte';

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

	// Conservative estimate of one event card's rendered height (title +
	// meta line + padding + the .list gap) -- not pixel-perfect, just enough
	// to size how many cards fit before the shrink-effect below corrects it.
	const ROW_HEIGHT_PX = 130;

	let { id, data, pauseSeconds = 8 }: { id: string; data: CalendarScreensaverData; pauseSeconds?: number } = $props();

	const showCalendarLabel = $derived(new Set(data.events.map((e) => e.calendar)).size > 1);

	let index = $state(getCursor(id));
	let listHeight = $state(0);
	let itemsWrapperHeight = $state(0);
	let rowsToShow = $state(1);

	// Optimistic starting guess for each new tick's content -- a fresh
	// estimate rather than something that has to grow back after the
	// shrink-effect below trimmed it for the previous (possibly taller) tick.
	$effect(() => {
		void index;
		rowsToShow = Math.max(1, Math.floor(listHeight / ROW_HEIGHT_PX));
	});

	// A long title/location can wrap onto extra visual lines, which the
	// estimate above can't account for. Shrink the row count until the
	// actually-rendered cards fit within the list, rather than clipping
	// whatever doesn't fit. `rowsToShow` itself is read/written untracked so
	// this only reruns on a genuinely new measurement (a real resize-observer
	// tick) instead of retriggering itself synchronously on every decrement.
	$effect(() => {
		if (itemsWrapperHeight > listHeight) {
			untrack(() => {
				if (rowsToShow > 1) rowsToShow -= 1;
			});
		}
	});

	// Capped at `data.events.length` -- when there's less content than fits
	// the screen (rowsToShow > events.length), show each event once instead
	// of wrapping the modulo back around to pad out the remaining rows with
	// repeats of content already on screen.
	const visibleEvents = $derived(
		Array.from(
			{ length: Math.min(rowsToShow, data.events.length) },
			(_, r) => (data.events.length ? data.events[(index + r) % data.events.length] : undefined)!,
		),
	);

	const totalPages = $derived(Math.max(1, Math.ceil(data.events.length / rowsToShow)));
	const currentPage = $derived(Math.floor(index / rowsToShow) % totalPages);

	function goToPage(page: number) {
		index = (page * rowsToShow) % data.events.length;
	}

	$effect(() => {
		if (totalPages <= 1) return;
		const interval = setInterval(() => (index = (index + rowsToShow) % data.events.length), pauseSeconds * 1000);
		return () => clearInterval(interval);
	});

	$effect(() => {
		setCursor(id, index);
	});
</script>

<div class="stage">
	<h1>Calendar</h1>
	{#if !data.connected}
		<p class="hint">{$_('calendar.screensaver.not_connected')}</p>
	{:else if data.events.length === 0}
		<p class="hint">{$_('calendar.detail.no_events')}</p>
	{:else}
		<div class="list" bind:clientHeight={listHeight}>
			{#key index}
				<div class="items" bind:clientHeight={itemsWrapperHeight}>
					{#each visibleEvents as event (event.id + event.start)}
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
			{/key}
		</div>
		<ScreenIndicator current={currentPage} total={totalPages} onselect={goToPage} />
	{/if}
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		flex-direction: column;
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
		flex: 1;
		min-height: 0;
		display: flex;
		flex-direction: column;
		justify-content: center;
	}

	.items {
		display: flex;
		flex-direction: column;
		gap: 1.25rem;
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
