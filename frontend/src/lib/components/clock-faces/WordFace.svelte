<script lang="ts">
	import { wallTime, wordPhrase } from '$lib/clockTime';

	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const time = $derived(wallTime(now, timezone));
	const phrase = $derived(wordPhrase(time.hours, time.minutes));
</script>

<div class="word" class:large={size === 'detail'}>{phrase}</div>

<style>
	.word {
		font-size: clamp(1.1rem, 20cqh, 1.8rem);
		font-weight: 600;
		line-height: 1.2;
	}

	.word.large {
		font-size: 3rem;
	}
</style>
