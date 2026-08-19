<script lang="ts">
	import { page } from '$app/state';
	import { api } from '$lib/api';
	import { renderDiscordMarkdown, toggleSpoiler, toggleSpoilerKey } from '$lib/discordMarkdown';
	import { _, locale } from 'svelte-i18n';
	import { get } from 'svelte/store';

	interface DiscordMessage {
		id: string;
		author: string;
		avatar_url: string | null;
		content: string;
		timestamp: string;
	}

	type DisplayMode = 'static' | 'marquee' | 'fade';

	interface DiscordDetailData {
		configured?: boolean;
		channel_id?: string;
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
	let channelIdInput = $state('');
	let displayMode = $state<DisplayMode>('static');
	let messageLimitInput = $state('20');
	let timeWindowInput = $state('');
	let marqueeSpeedInput = $state('40');
	let fadeIntervalInput = $state('6');
	let saving = $state(false);
	let error = $state<string | null>(null);

	function openEditor() {
		channelIdInput = discord.channel_id ?? '';
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
				channel_id: channelIdInput.trim(),
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
			error = get(_)('discord.detail.save_error');
		} finally {
			saving = false;
		}
	}
</script>

<div class="header">
	<h1>{discord.channel_name ? `#${discord.channel_name}` : 'Discord'}</h1>
	<button class="edit-settings" onclick={() => (editingSettings ? (editingSettings = false) : openEditor())}>
		{editingSettings ? $_('common.cancel') : $_('common.edit_settings')}
	</button>
</div>

{#if editingSettings}
	<div class="settings-form">
		<label>
			Channel ID
			<input type="text" bind:value={channelIdInput} placeholder="123456789012345678" />
		</label>

		<label>
			{$_('discord.detail.display_mode_label')}
			<select bind:value={displayMode}>
				<option value="static">{$_('discord.detail.mode_static')}</option>
				<option value="marquee">{$_('discord.detail.mode_marquee')}</option>
				<option value="fade">{$_('discord.detail.mode_fade')}</option>
			</select>
		</label>

		<label>
			{$_('discord.detail.message_count_label')}
			<input type="number" min="1" max="100" bind:value={messageLimitInput} />
		</label>

		<label>
			{$_('discord.detail.time_window_label')}
			<input
				type="number"
				min="1"
				bind:value={timeWindowInput}
				placeholder={$_('discord.detail.no_limit_placeholder')}
			/>
		</label>

		{#if displayMode === 'marquee'}
			<label>
				{$_('discord.detail.scroll_speed_label')}
				<input type="number" min="1" bind:value={marqueeSpeedInput} />
			</label>
		{:else if displayMode === 'fade'}
			<label>
				{$_('discord.detail.seconds_per_message_label')}
				<input type="number" min="1" bind:value={fadeIntervalInput} />
			</label>
		{/if}

		{#if error}
			<p class="hint error">{error}</p>
		{/if}

		<button class="save" disabled={saving} onclick={saveSettings}>
			{saving ? $_('common.saving') : $_('common.save')}
		</button>
	</div>
{:else if error}
	<p class="hint error">{error}</p>
{:else if discord.configured === false || !discord.channel_name}
	<p class="hint">{$_('common.not_configured')}</p>
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
					<span class="timestamp">{new Date(message.timestamp).toLocaleString(get(locale) ?? undefined)}</span>
				</div>
				<!-- svelte-ignore a11y_no_static_element_interactions -- delegation container for the `.spoiler` spans injected via {@html}; they carry their own role/tabindex. -->
				<div class="content" onclick={toggleSpoiler} onkeydown={toggleSpoilerKey}>
					<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderDiscordMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
					{@html renderDiscordMarkdown(message.content)}
				</div>
			</div>
		</div>
	{:else}
		<p class="hint">{$_('discord.no_messages')}</p>
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
		overflow-wrap: break-word;
	}

	.content :global(p) {
		margin: 0.3rem 0;
	}

	.content :global(p:first-child) {
		margin-top: 0;
	}

	.content :global(p:last-child) {
		margin-bottom: 0;
	}

	.content :global(strong) {
		font-weight: 700;
	}

	.content :global(code) {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 0.25rem;
		padding: 0.1rem 0.3rem;
		font-size: 0.9em;
	}

	.content :global(pre) {
		background: var(--color-bg);
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.5rem 0.75rem;
		overflow-x: auto;
	}

	.content :global(pre code) {
		background: none;
		border: none;
		padding: 0;
	}

	.content :global(blockquote) {
		margin: 0.3rem 0;
		padding-left: 0.75rem;
		border-left: 3px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.content :global(ul),
	.content :global(ol) {
		margin: 0.3rem 0;
		padding-left: 1.5rem;
	}

	.content :global(a) {
		color: var(--color-accent);
	}

	.content :global(h1),
	.content :global(h2),
	.content :global(h3) {
		margin: 0.4rem 0;
		font-size: 1.05em;
	}

	.content :global(.spoiler) {
		background: var(--color-border);
		color: transparent;
		border-radius: 0.25rem;
		cursor: pointer;
	}

	.content :global(.spoiler.revealed) {
		background: var(--color-surface-hover);
		color: inherit;
		cursor: text;
	}
</style>
