<script lang="ts">
	import ClockFace, { type ClockStyle } from '$lib/components/clock-faces/ClockFace.svelte';

	interface ClockScreensaverData {
		timezone: string;
		style: ClockStyle;
	}

	let { data }: { data: ClockScreensaverData } = $props();

	let now = $state(new Date());
	let stageEl = $state<HTMLDivElement | undefined>(undefined);
	let innerEl = $state<HTMLDivElement | undefined>(undefined);
	let scale = $state(1);

	$effect(() => {
		const interval = setInterval(() => (now = new Date()), 1000);
		return () => clearInterval(interval);
	});

	// The 5 clock faces (analog/digital/word/binary/matrix) have very
	// different natural sizes and aspect ratios at size="detail", so a single
	// fixed scale() factor either leaves some faces tiny or lets others
	// overflow the viewport horizontally. Measuring the rendered face and
	// scaling it to fill most of the stage works uniformly across all of them
	// without touching the face components themselves.
	function updateScale() {
		if (!stageEl || !innerEl) return;
		const naturalWidth = innerEl.scrollWidth;
		const naturalHeight = innerEl.scrollHeight;
		if (naturalWidth === 0 || naturalHeight === 0) return;
		const budget = 0.8;
		const next = Math.min(
			(stageEl.clientWidth * budget) / naturalWidth,
			(stageEl.clientHeight * budget) / naturalHeight,
		);
		if (Number.isFinite(next) && next > 0) scale = next;
	}

	$effect(() => {
		void data.style;
		requestAnimationFrame(updateScale);
		window.addEventListener('resize', updateScale);
		return () => window.removeEventListener('resize', updateScale);
	});
</script>

<div class="stage" bind:this={stageEl}>
	<div class="scaled" bind:this={innerEl} style={`transform: scale(${scale});`}>
		<ClockFace style={data.style} {now} timezone={data.timezone} size="detail" />
	</div>
</div>

<style>
	.stage {
		height: 100%;
		display: flex;
		align-items: center;
		justify-content: center;
		overflow: hidden;
	}
</style>
