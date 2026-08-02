<script lang="ts">
	import { pollWidget } from '$lib/polling';
	import { fade } from 'svelte/transition';
	import { api } from '$lib/api';
	import TileCard from '$lib/components/TileCard.svelte';

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

	let { widgetId }: { widgetId: string } = $props();

	let summary = $state<DiscordSummary | null>(null);
	let fadeIndex = $state(0);

	async function refresh() {
		try {
			summary = await api.widgetSummary<DiscordSummary>(widgetId);
			fadeIndex = 0;
		} catch {
			// keep showing the last known value on a failed poll
		}
	}

	pollWidget(refresh, 60_000);

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
		<div class="content">{message.content}</div>
	</div>
{/snippet}

<TileCard {widgetId}>
	<div class="widget">
		{#if summary}
			<div class="channel">#{summary.channel_name}</div>
		{/if}
		{#if !summary}
			<div class="empty">Loading messages…</div>
		{:else if summary.messages.length === 0}
			<div class="empty">No recent messages.</div>
		{:else if summary.display_mode === 'marquee'}
			<div class="marquee-viewport">
				<div class="marquee-track" style="animation-duration: {summary.marquee_speed_seconds}s;">
					{#each [...summary.messages, ...summary.messages] as message, i (i)}
						{@render messageCard(message)}
					{/each}
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
		white-space: pre-wrap;
		overflow-wrap: break-word;
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
