<script lang="ts">
	import { goto } from '$app/navigation';
	import { DETAIL_COMPONENTS } from '$lib/widgetComponents';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const Detail = $derived(data.type ? DETAIL_COMPONENTS[data.type] : undefined);
</script>

<div class="detail-page">
	<button class="back" onclick={() => goto('/')}>← Back</button>
	{#if Detail}
		<!-- Shape is only known at runtime via `data.type`; each Detail
		     component declares & validates its own expected shape. -->
		<Detail data={data.detail as never} />
	{:else}
		<p>Unknown widget.</p>
	{/if}
</div>

<style>
	.detail-page {
		padding: 2rem;
		min-height: 100vh;
	}

	.back {
		background: none;
		border: none;
		font-size: 1.1rem;
		color: var(--color-accent);
		margin-bottom: 1.5rem;
		cursor: pointer;
		padding: 0.5rem 0;
	}
</style>
