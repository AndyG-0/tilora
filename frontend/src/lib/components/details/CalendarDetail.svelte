<script lang="ts">
	import { env } from '$env/dynamic/public';
	import { page } from '$app/state';
	import { api, type CaldavCalendar } from '$lib/api';

	interface CalendarEvent {
		id: string;
		title: string;
		start: string;
		all_day: boolean;
		location: string | null;
		calendar?: string;
		color?: string | null;
	}

	interface CalendarDetailData {
		connected: boolean;
		provider?: 'google' | 'caldav' | 'microsoft';
		events: CalendarEvent[];
		calendar_ids?: string[];
		calendar_colors?: Record<string, string>;
	}

	let { data: initialData }: { data: CalendarDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveCalendars's refetch.
	let calendarData = $state(initialData);

	let managingCalendars = $state(false);
	let availableCalendars = $state<CaldavCalendar[]>([]);
	let selectedIds = $state<Set<string>>(new Set());
	let colors = $state<Record<string, string>>({});
	let loadingCalendars = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);

	let showCalendarLabel = $derived(new Set(calendarData.events.map((e) => e.calendar)).size > 1);

	async function toggleManageCalendars() {
		managingCalendars = !managingCalendars;
		if (!managingCalendars) return;

		error = null;
		loadingCalendars = true;
		selectedIds = new Set(calendarData.calendar_ids ?? []);
		try {
			availableCalendars = await api.listCaldavCalendars();
			colors = Object.fromEntries(
				availableCalendars.map((c) => [c.id, calendarData.calendar_colors?.[c.id] ?? c.color]),
			);
		} catch {
			error = 'Could not load calendars.';
		} finally {
			loadingCalendars = false;
		}
	}

	function toggleCalendar(id: string) {
		const next = new Set(selectedIds);
		if (next.has(id)) {
			next.delete(id);
		} else {
			next.add(id);
		}
		selectedIds = next;
	}

	async function saveCalendars() {
		saving = true;
		error = null;
		try {
			await api.updateWidgetSettings(page.params.id!, {
				calendar_ids: [...selectedIds],
				calendar_colors: colors,
			});
			calendarData = await api.widgetDetail<CalendarDetailData>(page.params.id!);
			managingCalendars = false;
		} catch {
			error = 'Could not update calendars.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>Calendar</h1>
	{#if calendarData.provider === 'caldav' && calendarData.connected}
		<button class="manage-calendars" onclick={toggleManageCalendars}>
			{managingCalendars ? 'Cancel' : 'Manage calendars'}
		</button>
	{/if}
</div>

{#if managingCalendars}
	<div class="calendar-picker">
		{#if loadingCalendars}
			<p class="hint">Loading calendars…</p>
		{:else if error}
			<p class="hint error">{error}</p>
		{:else}
			<ul class="calendars">
				{#each availableCalendars as calendar (calendar.id)}
					<li>
						<label>
							<input
								type="checkbox"
								checked={selectedIds.has(calendar.id)}
								onchange={() => toggleCalendar(calendar.id)}
							/>
							{calendar.name}
						</label>
						<input
							class="color-input"
							type="color"
							aria-label={`${calendar.name} color`}
							value={colors[calendar.id]}
							onchange={(e) => (colors = { ...colors, [calendar.id]: e.currentTarget.value })}
						/>
					</li>
				{/each}
			</ul>
			<button class="save-calendars" disabled={saving} onclick={saveCalendars}>
				{saving ? 'Saving…' : 'Save'}
			</button>
		{/if}
	</div>
{/if}

{#if !calendarData.connected}
	<div class="connect">
		{#if calendarData.provider === 'caldav'}
			<p class="hint">Add your CalDAV server URL, username, and password in Settings to see upcoming events here.</p>
			<a class="connect-button" href="/settings">Open settings</a>
		{:else if calendarData.provider === 'microsoft'}
			<p class="hint">Connect your Outlook / Microsoft 365 calendar to see upcoming events here.</p>
			<a class="connect-button" href={`${env.PUBLIC_API_BASE_URL}/api/calendar/auth/microsoft/start`}>
				Connect Outlook Calendar
			</a>
		{:else}
			<p class="hint">Connect your Google Calendar to see upcoming events here.</p>
			<a class="connect-button" href={`${env.PUBLIC_API_BASE_URL}/api/calendar/auth/start`}>
				Connect Google Calendar
			</a>
		{/if}
	</div>
{:else}
	<div class="list">
		{#each calendarData.events as event (event.id)}
			<div class="item">
				<h2><span class="dot" style:background={event.color ?? 'transparent'}></span>{event.title}</h2>
				<p class="meta">
					{event.all_day ? event.start : new Date(event.start).toLocaleString()}
					{event.location ? ` · ${event.location}` : ''}
					{showCalendarLabel && event.calendar ? ` · ${event.calendar}` : ''}
				</p>
			</div>
		{:else}
			<p class="hint">No upcoming events.</p>
		{/each}
	</div>
{/if}

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

	.manage-calendars {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.75rem;
		color: var(--color-accent);
		cursor: pointer;
	}

	.calendar-picker {
		margin: 1rem 0;
	}

	.calendars {
		list-style: none;
		margin: 0;
		padding: 0;
		max-width: 20rem;
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	.calendars li {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.5rem;
	}

	.calendars label {
		display: flex;
		align-items: center;
		gap: 0.5rem;
	}

	.color-input {
		width: 1.75rem;
		height: 1.75rem;
		padding: 0;
		border: none;
		background: none;
		cursor: pointer;
	}

	.dot {
		display: inline-block;
		width: 0.6rem;
		height: 0.6rem;
		border-radius: 50%;
		margin-right: 0.4rem;
	}

	.save-calendars {
		margin-top: 0.75rem;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border: none;
		border-radius: 0.5rem;
		padding: 0.5rem 1rem;
		cursor: pointer;
	}

	.save-calendars:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.hint.error {
		color: var(--color-error);
	}

	.connect {
		display: flex;
		flex-direction: column;
		align-items: flex-start;
		gap: 0.75rem;
	}

	.connect-button {
		display: inline-block;
		background: var(--color-accent);
		color: var(--color-on-accent);
		border-radius: 0.5rem;
		padding: 0.6rem 1rem;
		text-decoration: none;
	}

	.list {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.item {
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 1rem;
		padding: 1rem;
	}

	.item h2 {
		margin: 0 0 0.25rem;
		font-size: 1.1rem;
	}

	.meta {
		color: var(--color-text-muted);
		font-size: 0.85rem;
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
