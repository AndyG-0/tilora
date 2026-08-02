<script lang="ts">
	interface DateDetailData {
		timezone: string;
	}

	let { data }: { data: DateDetailData } = $props();

	let now = $state(new Date());

	$effect(() => {
		const interval = setInterval(() => (now = new Date()), 60_000);
		return () => clearInterval(interval);
	});

	const formatted = $derived(
		new Intl.DateTimeFormat(undefined, {
			timeZone: data.timezone,
			weekday: 'long',
			month: 'long',
			day: 'numeric',
			year: 'numeric',
		}).format(now),
	);
</script>

<h1>Date</h1>
<p class="date">{formatted}</p>
<p class="hint">{data.timezone} · change this in Settings</p>

<style>
	h1 {
		margin: 0 0 1rem;
	}

	.date {
		font-size: 2.5rem;
		font-weight: 600;
		margin: 0;
	}

	.hint {
		color: var(--color-text-muted);
	}
</style>
