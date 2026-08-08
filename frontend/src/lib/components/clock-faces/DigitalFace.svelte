<script lang="ts">
	import { locale } from 'svelte-i18n';

	let { now, timezone, size }: { now: Date; timezone: string; size: 'tile' | 'detail' } = $props();

	const formatted = $derived(
		new Intl.DateTimeFormat($locale ?? undefined, {
			timeZone: timezone,
			hour: 'numeric',
			minute: '2-digit',
			second: '2-digit',
		}).format(now),
	);
</script>

<div class="digital" class:large={size === 'detail'}>{formatted}</div>

<style>
	.digital {
		font-size: clamp(1.4rem, 32cqh, 3rem);
		font-weight: 600;
		font-variant-numeric: tabular-nums;
	}

	.digital.large {
		font-size: 5rem;
	}
</style>
