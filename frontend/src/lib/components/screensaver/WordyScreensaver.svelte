<script lang="ts">
	import type { TextAnimationStyle, FlipboardPattern } from '$lib/screensaverTypes';
	import { parseFormattedLines, replaceDiscordReferences, type FormattedSegment } from '$lib/discordMarkdown';
	import { _ } from 'svelte-i18n';
	import Marquee from './text-animations/Marquee.svelte';
	import Matrix from './text-animations/Matrix.svelte';
	import Flipboard from './text-animations/Flipboard.svelte';
	import LedDots from './text-animations/LedDots.svelte';

	interface RSSItem {
		title: string;
		source: string;
	}

	interface RSSFeedGroup {
		items: RSSItem[];
	}

	interface SportsGame {
		away_abbreviation: string;
		away_score: string | null;
		home_abbreviation: string;
		home_score: string | null;
		state: string;
		status_detail: string;
		date: string | null;
	}

	interface SportsTeamDetail {
		games: SportsGame[];
	}

	interface DiscordMessage {
		author: string;
		content: string;
	}

	let {
		type,
		data,
		animationStyle,
		ledColor,
		textPauseSeconds,
		flipboardPattern,
	}: {
		type: string;
		data: unknown;
		animationStyle: TextAnimationStyle;
		ledColor?: string;
		textPauseSeconds?: number;
		flipboardPattern?: FlipboardPattern;
	} = $props();

	function toLines(text: string): FormattedSegment[][] {
		return parseFormattedLines(text);
	}

	function formatGame(game: SportsGame): string {
		const score = game.state === 'pre' ? '' : ` ${game.away_score ?? '-'}-${game.home_score ?? '-'}`;
		const status =
			game.state === 'in' ? game.status_detail : game.date ? new Date(game.date).toLocaleString() : game.status_detail;
		return `${game.away_abbreviation}${score} @ ${game.home_abbreviation} — ${status}`;
	}

	function resolveFormattedLines(type: string, data: unknown): FormattedSegment[][] {
		if (type === 'rss') {
			const groups = (data as { feed_groups?: RSSFeedGroup[] })?.feed_groups ?? [];
			const items = groups.flatMap((group) => group.items);
			if (items.length === 0) return [[{ text: $_('rss.screensaver.no_headlines') }]];
			return items.flatMap((item) => toLines(item.source ? `${item.title} — ${item.source}` : item.title));
		}
		if (type === 'sports') {
			const teams = (data as { teams?: SportsTeamDetail[] })?.teams ?? [];
			const trending = (data as { trending?: SportsGame[] })?.trending ?? [];
			const games = [...teams.flatMap((t) => t.games), ...trending];
			if (games.length === 0) return [[{ text: $_('sports.screensaver.no_games') }]];
			return games.slice(0, 20).flatMap((game) => toLines(formatGame(game)));
		}
		if (type === 'ai') {
			const text = (data as { text?: string })?.text ?? '';
			const sentences = text.split(/(?<=[.!?])\s+/).filter(Boolean);
			return sentences.length > 0
				? sentences.flatMap(toLines)
				: [[{ text: $_('ai_insights.screensaver.no_briefing') }]];
		}
		if (type === 'discord') {
			const messages = (data as { messages?: DiscordMessage[] })?.messages ?? [];
			if (messages.length === 0) return [[{ text: $_('discord.no_messages') }]];
			return messages.flatMap((m) => {
				const contentLines = toLines(replaceDiscordReferences(m.content));
				if (contentLines.length === 0) return [[{ text: `${m.author}:` }]];
				return contentLines.map((line, i) => (i === 0 ? [{ text: `${m.author}: ` }, ...line] : line));
			});
		}
		if (type === 'message') {
			const text = (data as { text?: string })?.text ?? '';
			const lines = toLines(text);
			return lines.length > 0 ? lines : [[{ text: $_('message.empty_placeholder') }]];
		}
		return [];
	}

	const lines = $derived(resolveFormattedLines(type, data));
</script>

{#if animationStyle === 'matrix'}
	<Matrix {lines} pauseSeconds={textPauseSeconds} />
{:else if animationStyle === 'flipboard'}
	<Flipboard {lines} pauseSeconds={textPauseSeconds} pattern={flipboardPattern} />
{:else if animationStyle === 'led_dots'}
	<LedDots {lines} color={ledColor} pauseSeconds={textPauseSeconds} />
{:else}
	<Marquee {lines} />
{/if}
