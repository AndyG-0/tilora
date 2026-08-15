<script lang="ts">
	import { wallTime, wordPhrase } from '$lib/clockTime';

	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const time = $derived(wallTime(now, timezone));
	const phrase = $derived(wordPhrase(time.hours, time.minutes));
</script>

<div class="word" class:large={size === 'detail'}>{phrase}</div>

<style>
	.word {
		font-size: clamp(1.15rem, min(24cqh, 13cqw), 2.75rem);
		font-weight: 600;
		line-height: 1.25;
		text-align: center;
	}

	.word.large {
		font-size: 3rem;
	}
</style>
