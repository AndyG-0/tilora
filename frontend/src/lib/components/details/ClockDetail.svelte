<script lang="ts">
	interface ClockDetailData {
		timezone: string;
	}

	let { data }: { data: ClockDetailData } = $props();

	let now = $state(new Date());

	$effect(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});

	const formatted = $derived(
		new Intl.DateTimeFormat(undefined, {
			timeZone: data.timezone,
			hour: 'numeric',
			minute: '2-digit',
			second: '2-digit',
		}).format(now),
	);
</script>

<h1>Clock</h1>
<p class="time">{formatted}</p>
<p class="hint">{data.timezone} · change this in Settings</p>

<style>
	h1 {
		margin: 0 0 1rem;
	}

	.time {
		font-size: 5rem;
		font-weight: 600;
		font-variant-numeric: tabular-nums;
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
