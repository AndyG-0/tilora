<script lang="ts">
	import { locale } from 'svelte-i18n';

	interface DateScreensaverData {
		timezone: string;
	}

	let { data }: { data: DateScreensaverData } = $props();

	let now = $state(new Date());

	$effect(() => {
		const interval = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(interval);
	});

	const weekday = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, { timeZone: data.timezone, weekday: 'long' }).format(now),
	);
	const monthDay = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, { timeZone: data.timezone, month: 'long', day: 'numeric' }).format(
			now,
		),
	);
	const year = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, { timeZone: data.timezone, year: 'numeric' }).format(now),
	);
</script>

<div class="stage">
	<p class="weekday">{weekday}</p>
	<p class="date">{monthDay}</p>
	<p class="year">{year}</p>
	<p class="hint">{data.timezone}</p>
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		gap: 0.5rem;
	}

	.weekday {
		font-size: clamp(2rem, 6vw, 4rem);
		font-weight: 600;
		margin: 0;
	}

	.date {
		font-size: clamp(3rem, 10vw, 7rem);
		font-weight: 700;
		margin: 0;
		line-height: 1;
	}

	.year {
		font-size: clamp(1.5rem, 4vw, 2.5rem);
		color: var(--color-text-muted);
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
		margin-top: 1rem;
	}
</style>
