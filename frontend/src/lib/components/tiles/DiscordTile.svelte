<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { fade } from 'svelte/transition';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';
	import { renderDiscordMarkdown, toggleSpoiler, toggleSpoilerKey } from '$lib/discordMarkdown';
	import { _ } from 'svelte-i18n';

	interface DiscordMessage {
		id: string;
		author: string;
		avatar_url: string | null;
		content: string;
		timestamp: string;
	}

	interface DiscordSummary {
		channel_name: string;
		display_mode: 'static' | 'marquee' | 'fade';
		marquee_speed_seconds: number;
		fade_interval_seconds: number;
		messages: DiscordMessage[];
	}

	let { widgetId, refreshIntervalSeconds }: { widgetId: string; refreshIntervalSeconds: number } = $props();

	// A fixed animation-duration paired with a track whose height scales with
	// message count/length makes longer content visibly speed up. Deriving the
	// duration from the measured height of one copy keeps the scroll speed
	// constant regardless of how much is showing. marquee_speed_seconds used
	// to be a flat total-loop duration; it's kept as a relative multiplier on
	// top of the computed rate so existing saved values ("bigger = slower")
	// stay meaningful instead of becoming a fixed duration again.
	const BASE_PX_PER_SECOND = 40;
	const DEFAULT_MARQUEE_SPEED_SECONDS = 40;

	let summary = $state<DiscordSummary | null>(null);
	let fadeIndex = $state(0);
	let copyHeight = $state(0);
	const marqueeDurationSeconds = $derived(
		summary ? (copyHeight / BASE_PX_PER_SECOND) * (summary.marquee_speed_seconds / DEFAULT_MARQUEE_SPEED_SECONDS) : 0,
	);

	async function refresh() {
		try {
			summary = await api.widgetSummary<DiscordSummary>(widgetId);
			fadeIndex = 0;
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, refreshIntervalSeconds * 1000);

	// Cycles the "fade" display mode through one message at a time; a no-op
	// for the other modes since the effect bails out immediately.
	$effect(() => {
		if (summary?.display_mode !== 'fade' || summary.messages.length === 0) return;
		const count = summary.messages.length;
		const timer = setInterval(() => {
			fadeIndex = (fadeIndex + 1) % count;
		}, summary.fade_interval_seconds * 1000);
		return () => clearInterval(timer);
	});
</script>

{#snippet messageCard(message: DiscordMessage)}
	<div class="message">
		<div class="message-header">
			{#if message.avatar_url}
				<img class="avatar" src={message.avatar_url} alt="" />
			{/if}
			<span class="author">{message.author}</span>
		</div>
		<!-- svelte-ignore a11y_no_static_element_interactions -- delegation container for the `.spoiler` spans injected via {@html}; they carry their own role/tabindex. -->
		<div class="content" onclick={toggleSpoiler} onkeydown={toggleSpoilerKey}>
			<!-- eslint-disable-next-line svelte/no-at-html-tags -- renderDiscordMarkdown sanitizes with DOMPurify against an explicit tag/attribute allowlist before this reaches the DOM. -->
			{@html renderDiscordMarkdown(message.content)}
		</div>
	</div>
{/snippet}

<TileCard {widgetId}>
	<div class="widget">
		{#if summary}
			<div class="channel">#{summary.channel_name}</div>
		{/if}
		{#if !summary}
			<div class="empty">{$_('discord.tile.loading')}</div>
		{:else if summary.messages.length === 0}
			<div class="empty">{$_('discord.no_messages')}</div>
		{:else if summary.display_mode === 'marquee'}
			<div class="marquee-viewport">
				<div class="marquee-track" style="animation-duration: {marqueeDurationSeconds}s;">
					<div class="marquee-copy" bind:clientHeight={copyHeight}>
						{#each summary.messages as message (message.id)}
							{@render messageCard(message)}
						{/each}
					</div>
					<div class="marquee-copy" aria-hidden="true">
						{#each summary.messages as message (message.id)}
							{@render messageCard(message)}
						{/each}
					</div>
				</div>
			</div>
		{:else if summary.display_mode === 'fade'}
			<div class="fade-viewport">
				{#key summary.messages[fadeIndex].id}
					<div class="fade-message" transition:fade>
						{@render messageCard(summary.messages[fadeIndex])}
					</div>
				{/key}
			</div>
		{:else}
			<div class="static-list">
				{#each summary.messages as message (message.id)}
					{@render messageCard(message)}
				{/each}
			</div>
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

	.channel {
		font-size: 0.9rem;
		color: var(--color-text-muted);
		margin-bottom: 0.5rem;
		flex-shrink: 0;
	}

	.empty {
		color: var(--color-text-muted);
	}

	.message {
		display: flex;
		flex-direction: column;
		gap: 0.2rem;
		border: 1px solid var(--color-border);
		border-radius: 0.5rem;
		padding: 0.4rem 0.6rem;
		line-height: 1.4;
	}

	.message-header {
		display: flex;
		align-items: center;
		gap: 0.35rem;
	}

	.avatar {
		width: 1.1rem;
		height: 1.1rem;
		border-radius: 50%;
		flex-shrink: 0;
	}

	.author {
		font-weight: 600;
		font-size: 0.85rem;
	}

	.content {
		color: var(--color-text-muted);
		overflow-wrap: break-word;
	}

	.content :global(p) {
		margin: 0.2rem 0;
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
		border-radius: 0.25rem;
		padding: 0.05rem 0.25rem;
		font-size: 0.9em;
	}

	.content :global(pre) {
		background: var(--color-bg);
		border-radius: 0.4rem;
		padding: 0.3rem 0.5rem;
		overflow-x: auto;
	}

	.content :global(pre code) {
		background: none;
		padding: 0;
	}

	.content :global(blockquote) {
		margin: 0.2rem 0;
		padding-left: 0.5rem;
		border-left: 2px solid var(--color-border);
	}

	.content :global(ul),
	.content :global(ol) {
		margin: 0.2rem 0;
		padding-left: 1.2rem;
	}

	.content :global(a) {
		color: var(--color-accent);
	}

	.content :global(.spoiler) {
		background: var(--color-border);
		color: transparent;
		border-radius: 0.2rem;
		cursor: pointer;
	}

	.content :global(.spoiler.revealed) {
		background: var(--color-surface-hover);
		color: inherit;
		cursor: text;
	}

	.static-list,
	.fade-viewport,
	.marquee-viewport {
		flex: 1;
		min-height: 0;
	}

	.static-list {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		overflow-y: auto;
	}

	.fade-viewport {
		overflow-y: auto;
	}

	.marquee-viewport {
		overflow: hidden;
	}

	.marquee-track {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
		animation-name: marquee-scroll;
		animation-timing-function: linear;
		animation-iteration-count: infinite;
	}

	.marquee-copy {
		display: flex;
		flex-direction: column;
		gap: 0.4rem;
	}

	@keyframes marquee-scroll {
		from {
			transform: translateY(0);
		}
		to {
			transform: translateY(-50%);
		}
	}

	.static-list::-webkit-scrollbar,
	.fade-viewport::-webkit-scrollbar {
		width: 4px;
	}

	.static-list::-webkit-scrollbar-thumb,
	.fade-viewport::-webkit-scrollbar-thumb {
		background: var(--color-border);
		border-radius: 2px;
	}
</style>
