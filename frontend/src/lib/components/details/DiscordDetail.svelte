<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';

	interface DiscordMessage {
		id: string;
		author: string;
		avatar_url: string | null;
		content: string;
		timestamp: string;
	}

	type DisplayMode = 'static' | 'marquee' | 'fade';

	interface DiscordDetailData {
		channel_name: string;
		display_mode: DisplayMode;
		message_limit: number;
		time_window_minutes: number | null;
		marquee_speed_seconds: number;
		fade_interval_seconds: number;
		messages: DiscordMessage[];
	}

	let { data: initialData }: { data: DiscordDetailData } = $props();

	// svelte-ignore state_referenced_locally -- seed local state from the
	// initial load once; subsequent updates come from saveSettings's refetch.
	let discord = $state(initialData);

	let editingSettings = $state(false);
	let displayMode = $state<DisplayMode>('static');
	let messageLimitInput = $state('20');
	let timeWindowInput = $state('');
	let marqueeSpeedInput = $state('40');
	let fadeIntervalInput = $state('6');
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		displayMode = discord.display_mode;
		messageLimitInput = String(discord.message_limit);
		timeWindowInput = discord.time_window_minutes ? String(discord.time_window_minutes) : '';
		marqueeSpeedInput = String(discord.marquee_speed_seconds);
		fadeIntervalInput = String(discord.fade_interval_seconds);
		editingSettings = true;
	}

	async function saveSettings() {
		saving = true;
		error = null;
		try {
			const settings: Record<string, unknown> = {
				display_mode: displayMode,
				marquee_speed_seconds: Number(marqueeSpeedInput) || 40,
				fade_interval_seconds: Number(fadeIntervalInput) || 6,
			};
			const messageLimit = Number(messageLimitInput);
			if (messageLimit > 0) settings.message_limit = messageLimit;
			const timeWindow = timeWindowInput.trim();
			settings.time_window_minutes = timeWindow ? Number(timeWindow) : null;

			await api.updateWidgetSettings(page.params.id!, settings);
			discord = await api.widgetDetail<DiscordDetailData>(page.params.id!);
			editingSettings = false;
		} catch {
			error = 'Could not update the settings.';
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>#{discord.channel_name}</h1>
	<button class="edit-settings" onclick={() => (editingSettings ? (editingSettings = false) : openEditor())}>
		{editingSettings ? 'Cancel' : 'Edit settings'}
	</button>
</div>

{#if editingSettings}
	<div class="settings-form">
		<label>
			Display mode
			<select bind:value={displayMode}>
				<option value="static">Static (scrollable list)</option>
				<option value="marquee">Marquee (continuous scroll)</option>
				<option value="fade">Fade (one message at a time)</option>
			</select>
		</label>

		<label>
			Message count
			<input type="number" min="1" max="100" bind:value={messageLimitInput} />
		</label>

		<label>
			Time window (minutes, blank = no limit)
			<input type="number" min="1" bind:value={timeWindowInput} placeholder="No limit" />
		</label>

		{#if displayMode === 'marquee'}
			<label>
				Scroll duration (seconds)
				<input type="number" min="1" bind:value={marqueeSpeedInput} />
			</label>
		{:else if displayMode === 'fade'}
			<label>
				Seconds per message
				<input type="number" min="1" bind:value={fadeIntervalInput} />
			</label>
		{/if}

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</div>
{/if}

<div class="messages">
	{#each discord.messages as message (message.id)}
		<div class="message">
			{#if message.avatar_url}
				<img class="avatar" src={message.avatar_url} alt="" />
			{/if}
			<div class="body">
				<div class="meta">
					<span class="author">{message.author}</span>
					<span class="timestamp">{new Date(message.timestamp).toLocaleString()}</span>
				</div>
				<div class="content">{message.content}</div>
			</div>
		</div>
	{:else}
		<p class="hint">No recent messages.</p>
	{/each}
</div>

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
		max-width: 20rem;
		margin: 1rem 0 1.5rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 1rem;
	}

	.settings-form label {
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		font-size: 0.9rem;
		color: var(--color-text-muted);
	}

	.settings-form input,
	.settings-form select {
		font: inherit;
		padding: 0.5rem 0.75rem;
		border-radius: 0.5rem;
		border: 1px solid var(--color-border);
		background: var(--color-surface);
		color: var(--color-text);
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
		margin: 0.5rem 0 0;
	}

	.hint.error {
		color: var(--color-error);
	}

	.messages {
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
	}

	.message {
		display: flex;
		gap: 0.6rem;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		padding: 0.75rem 1rem;
	}

	.avatar {
		width: 2rem;
		height: 2rem;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.meta {
		display: flex;
		gap: 0.5rem;
		align-items: baseline;
	}

	.author {
		font-weight: 600;
	}

	.timestamp {
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.content {
		margin-top: 0.15rem;
		white-space: pre-wrap;
		overflow-wrap: break-word;
	}
</style>
