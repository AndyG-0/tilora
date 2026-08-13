<script lang="ts">
	import { _ } from 'svelte-i18n';
	import type {
		HDHomeRunChannel,
		HDHomeRunFullGuideChannel,
		HDHomeRunGuideEntry,
		HDHomeRunRecordingRule,
	} from '$lib/api';
	import HDHomeRunGuideCellMenu from './HDHomeRunGuideCellMenu.svelte';

	interface Props {
		channels: HDHomeRunChannel[];
		fullGuide: HDHomeRunFullGuideChannel[] | null;
		recordingRules: HDHomeRunRecordingRule[];
		favoriteChannels: Set<string>;
		savingFavorite: boolean;
		recordingLoading: string | null;
		onWatch: (channel: HDHomeRunChannel) => void;
		onRecordEpisode: (seriesId: string | null | undefined, channelNumber: string, start: number | null) => void;
		onRecordSeries: (seriesId: string, channelNumber: string) => void;
		onCancelRule: (ruleId: string) => void;
		onToggleFavorite: (channelNumber: string) => void;
	}

	let {
		channels,
		fullGuide,
		recordingRules,
		favoriteChannels,
		savingFavorite,
		recordingLoading,
		onWatch,
		onRecordEpisode,
		onRecordSeries,
		onCancelRule,
		onToggleFavorite,
	}: Props = $props();

	const PX_PER_SEC = 4 / 60; // 4px per minute — a 30-minute slot is 120px wide.
	const MIN_CELL_WIDTH = 90;
	const HOUR_SECONDS = 3600;

	let scrollEl = $state<HTMLDivElement | null>(null);
	let nowSeconds = $state(Math.floor(Date.now() / 1000));
	let hasAutoScrolled = false;

	$effect(() => {
		const interval = setInterval(() => {
			nowSeconds = Math.floor(Date.now() / 1000);
		}, 30_000);
		return () => clearInterval(interval);
	});

	const guideByChannel = $derived.by(() => {
		const map = new Map<string, HDHomeRunFullGuideChannel>();
		for (const entry of fullGuide ?? []) map.set(entry.channel_number, entry);
		return map;
	});

	// Favorited channels first (their original relative order preserved),
	// then everything else — surfaces favorites without a duplicate section.
	const orderedChannels = $derived.by(() => {
		const favorites = channels.filter((c) => favoriteChannels.has(c.channel_number));
		const rest = channels.filter((c) => !favoriteChannels.has(c.channel_number));
		return [...favorites, ...rest];
	});

	const windowBounds = $derived.by(() => {
		let minStart = nowSeconds - 30 * 60;
		let maxEnd = nowSeconds + 4 * HOUR_SECONDS;
		const earliestAllowed = nowSeconds - HOUR_SECONDS;
		for (const entry of fullGuide ?? []) {
			for (const airing of entry.airings) {
				if (airing.start != null) minStart = Math.min(minStart, airing.start);
				if (airing.end != null) maxEnd = Math.max(maxEnd, airing.end);
			}
		}
		minStart = Math.max(minStart, earliestAllowed);
		// Align to the half hour for a cleaner ruler.
		const start = Math.floor(minStart / 1800) * 1800;
		return { start, end: maxEnd };
	});

	const hourMarks = $derived.by(() => {
		const { start, end } = windowBounds;
		const marks: { seconds: number; label: string }[] = [];
		let t = Math.ceil(start / HOUR_SECONDS) * HOUR_SECONDS;
		for (; t < end; t += HOUR_SECONDS) {
			marks.push({ seconds: t, label: new Date(t * 1000).toLocaleTimeString([], { hour: 'numeric' }) });
		}
		return marks;
	});

	const totalWidth = $derived((windowBounds.end - windowBounds.start) * PX_PER_SEC);
	const nowLeft = $derived((nowSeconds - windowBounds.start) * PX_PER_SEC);

	interface CellLayout {
		airing: HDHomeRunGuideEntry;
		left: number;
		width: number;
	}

	function computeCellLayout(airings: HDHomeRunGuideEntry[], windowStart: number, windowEnd: number): CellLayout[] {
		const layouts: CellLayout[] = [];
		for (const airing of airings) {
			if (airing.start == null || airing.end == null) continue;
			const start = Math.max(airing.start, windowStart);
			const end = Math.min(airing.end, windowEnd);
			if (end <= start) continue;
			layouts.push({
				airing,
				left: (start - windowStart) * PX_PER_SEC,
				width: Math.max((end - start) * PX_PER_SEC, MIN_CELL_WIDTH),
			});
		}
		return layouts;
	}

	function isLive(airing: HDHomeRunGuideEntry): boolean {
		return airing.start != null && airing.end != null && airing.start <= nowSeconds && nowSeconds < airing.end;
	}

	function findExistingRule(airing: HDHomeRunGuideEntry, channel: HDHomeRunChannel): HDHomeRunRecordingRule | null {
		return (
			recordingRules.find((r) => {
				const channelMatches = !r.ChannelOnly || r.ChannelOnly.split('|').includes(channel.channel_number);
				if (!channelMatches) return false;
				if (r.DateTimeOnly != null) {
					return airing.start != null && Math.abs(r.DateTimeOnly - airing.start) < 60;
				}
				return !!(r.SeriesID && airing.series_id && r.SeriesID === airing.series_id);
			}) ?? null
		);
	}

	function isLoadingFor(
		airing: HDHomeRunGuideEntry,
		channel: HDHomeRunChannel,
		existingRule: HDHomeRunRecordingRule | null,
	) {
		if (existingRule) return recordingLoading === existingRule.RecordingRuleID;
		const targetId = airing.series_id || channel.channel_number;
		return recordingLoading === targetId;
	}

	// Auto-scroll the timeline so "now" starts a little after the left edge,
	// once, the first time real guide data is available.
	$effect(() => {
		if (hasAutoScrolled || !scrollEl || !fullGuide) return;
		hasAutoScrolled = true;
		scrollEl.scrollLeft = Math.max(nowLeft - 60, 0);
	});

	let menuState = $state<{ airing: HDHomeRunGuideEntry; channel: HDHomeRunChannel; x: number; y: number } | null>(null);

	function openContextMenu(airing: HDHomeRunGuideEntry, channel: HDHomeRunChannel, x: number, y: number) {
		menuState = { airing, channel, x, y };
	}

	function closeContextMenu() {
		menuState = null;
	}

	let pressTimer: ReturnType<typeof setTimeout> | null = null;
	let longPressFired = false;
	let pointerStart: { x: number; y: number } | null = null;
	const LONG_PRESS_MS = 500;
	const MOVE_CANCEL_PX = 10;

	function cancelPress() {
		if (pressTimer) clearTimeout(pressTimer);
		pressTimer = null;
		pointerStart = null;
	}

	function onCellPointerDown(e: PointerEvent, airing: HDHomeRunGuideEntry, channel: HDHomeRunChannel) {
		if (e.button !== undefined && e.button !== 0) return;
		pointerStart = { x: e.clientX, y: e.clientY };
		longPressFired = false;
		pressTimer = setTimeout(() => {
			longPressFired = true;
			openContextMenu(airing, channel, e.clientX, e.clientY);
		}, LONG_PRESS_MS);
	}

	function onCellPointerMove(e: PointerEvent) {
		if (!pointerStart || !pressTimer) return;
		if (
			Math.abs(e.clientX - pointerStart.x) > MOVE_CANCEL_PX ||
			Math.abs(e.clientY - pointerStart.y) > MOVE_CANCEL_PX
		) {
			cancelPress();
		}
	}

	function onCellClick(e: MouseEvent, airing: HDHomeRunGuideEntry, channel: HDHomeRunChannel) {
		if (longPressFired) {
			longPressFired = false;
			e.preventDefault();
			return;
		}
		if (isLive(airing)) {
			onWatch(channel);
		} else {
			openContextMenu(airing, channel, e.clientX, e.clientY);
		}
	}

	function onCellKeydown(e: KeyboardEvent, airing: HDHomeRunGuideEntry, channel: HDHomeRunChannel) {
		if (e.key !== 'Enter' && e.key !== ' ') return;
		e.preventDefault();
		const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
		if (isLive(airing)) {
			onWatch(channel);
		} else {
			openContextMenu(airing, channel, rect.left, rect.bottom);
		}
	}

	function formatCellTime(seconds: number | null): string {
		if (seconds === null) return '';
		return new Date(seconds * 1000).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
	}
</script>

<div class="guide-grid" bind:this={scrollEl} onscroll={cancelPress}>
	<div class="grid-inner" style={`width: ${totalWidth + 160}px;`}>
		<div class="corner-cell"></div>
		<div class="time-ruler" style={`width: ${totalWidth}px;`}>
			{#each hourMarks as mark (mark.seconds)}
				<span class="hour-mark" style={`left: ${(mark.seconds - windowBounds.start) * PX_PER_SEC}px;`}>
					{mark.label}
				</span>
			{/each}
			<div class="now-line" style={`left: ${nowLeft}px;`}></div>
		</div>

		{#each orderedChannels as channel (channel.channel_number)}
			{@const guideEntry = guideByChannel.get(channel.channel_number)}
			{@const cells = computeCellLayout(guideEntry?.airings ?? [], windowBounds.start, windowBounds.end)}
			<div class="channel-col">
				<button
					class="favorite-toggle"
					class:active={favoriteChannels.has(channel.channel_number)}
					disabled={savingFavorite}
					onclick={() => onToggleFavorite(channel.channel_number)}
					aria-label={favoriteChannels.has(channel.channel_number)
						? $_('hdhomerun.detail.remove_favorite')
						: $_('hdhomerun.detail.add_favorite')}
				>
					{favoriteChannels.has(channel.channel_number) ? '★' : '☆'}
				</button>
				<span class="channel-number">{channel.channel_number}</span>
				<span class="channel-name">{channel.name}</span>
				{#if channel.is_hd}<span class="badge">HD</span>{/if}
			</div>
			<div class="channel-track" style={`width: ${totalWidth}px;`}>
				<div class="now-line"></div>
				{#each cells as cell (cell.airing.start ?? cell.airing.title)}
					<div
						class="airing-cell"
						class:live={isLive(cell.airing)}
						style={`left: ${cell.left}px; width: ${cell.width}px;`}
						role="button"
						tabindex="0"
						onpointerdown={(e) => onCellPointerDown(e, cell.airing, channel)}
						onpointermove={onCellPointerMove}
						onpointerup={cancelPress}
						onpointercancel={cancelPress}
						onpointerleave={cancelPress}
						onclick={(e) => onCellClick(e, cell.airing, channel)}
						onkeydown={(e) => onCellKeydown(e, cell.airing, channel)}
						oncontextmenu={(e) => e.preventDefault()}
					>
						<span class="cell-time">{formatCellTime(cell.airing.start)}</span>
						<span class="cell-title">{cell.airing.title}</span>
						{#if findExistingRule(cell.airing, channel)}<span class="cell-live-badge"
								>{$_('hdhomerun.tile.recording_badge')}</span
							>{/if}
					</div>
				{/each}
			</div>
		{/each}
	</div>
</div>

{#if menuState}
	<HDHomeRunGuideCellMenu
		airing={menuState.airing}
		channelName={menuState.channel.name}
		x={menuState.x}
		y={menuState.y}
		existingRule={findExistingRule(menuState.airing, menuState.channel)}
		loading={isLoadingFor(menuState.airing, menuState.channel, findExistingRule(menuState.airing, menuState.channel))}
		onRecordEpisode={() => {
			if (!menuState) return;
			onRecordEpisode(menuState.airing.series_id, menuState.channel.channel_number, menuState.airing.start);
			closeContextMenu();
		}}
		onRecordSeries={() => {
			if (!menuState || !menuState.airing.series_id) return;
			onRecordSeries(menuState.airing.series_id, menuState.channel.channel_number);
			closeContextMenu();
		}}
		onCancelRule={(ruleId) => {
			onCancelRule(ruleId);
			closeContextMenu();
		}}
		onClose={closeContextMenu}
	/>
{/if}

<style>
	.guide-grid {
		overflow: auto;
		overscroll-behavior-x: contain;
		border: 1px solid var(--color-border);
		border-radius: 0.75rem;
		margin: 0.5rem 0;
		max-height: 70vh;
	}

	.grid-inner {
		display: grid;
		grid-template-columns: 10rem 1fr;
		position: relative;
	}

	.corner-cell {
		position: sticky;
		top: 0;
		left: 0;
		z-index: 4;
		background: var(--color-surface);
		border-right: 1px solid var(--color-border);
		border-bottom: 1px solid var(--color-border);
	}

	.time-ruler {
		position: sticky;
		top: 0;
		z-index: 3;
		height: 2rem;
		background: var(--color-surface);
		border-bottom: 1px solid var(--color-border);
	}

	.hour-mark {
		position: absolute;
		top: 0.4rem;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		white-space: nowrap;
		padding-left: 0.25rem;
		border-left: 1px solid var(--color-border);
	}

	.channel-col {
		position: sticky;
		left: 0;
		z-index: 2;
		background: var(--color-surface);
		border-right: 1px solid var(--color-border);
		border-bottom: 1px solid var(--color-border);
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 0.35rem;
		padding: 0.5rem;
		min-height: 4rem;
	}

	.favorite-toggle {
		background: none;
		border: none;
		padding: 0;
		font-size: 1rem;
		line-height: 1;
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.favorite-toggle.active {
		color: var(--color-accent);
	}

	.favorite-toggle:disabled {
		opacity: 0.6;
		cursor: default;
	}

	.channel-number {
		color: var(--color-text-muted);
		font-size: 0.85rem;
	}

	.channel-name {
		font-weight: 600;
		font-size: 0.9rem;
		width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.badge {
		font-size: 0.7rem;
		border: 1px solid var(--color-accent);
		color: var(--color-accent);
		border-radius: 0.3rem;
		padding: 0.05rem 0.3rem;
	}

	.channel-track {
		position: relative;
		min-height: 4rem;
		border-bottom: 1px solid var(--color-border);
	}

	.now-line {
		position: absolute;
		top: 0;
		bottom: 0;
		width: 2px;
		background: var(--color-accent);
		z-index: 1;
		pointer-events: none;
	}

	.time-ruler .now-line {
		top: 0;
		bottom: -0.5rem;
	}

	.airing-cell {
		position: absolute;
		top: 0.35rem;
		bottom: 0.35rem;
		left: 0;
		display: flex;
		flex-direction: column;
		justify-content: center;
		gap: 0.1rem;
		overflow: hidden;
		background: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: 0.4rem;
		padding: 0.25rem 0.5rem;
		cursor: pointer;
		user-select: none;
		touch-action: pan-y;
	}

	.airing-cell.live {
		border-color: var(--color-accent);
		background: color-mix(in srgb, var(--color-accent) 12%, var(--color-surface));
	}

	.cell-time {
		font-size: 0.7rem;
		color: var(--color-text-muted);
	}

	.cell-title {
		font-size: 0.8rem;
		font-weight: 600;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.cell-live-badge {
		font-size: 0.65rem;
		color: var(--color-error, #e05a5a);
		font-weight: 600;
	}
</style>
