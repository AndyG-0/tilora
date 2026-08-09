<script lang="ts">
	import { aircraftIconKey } from '$lib/aircraftIcons';

	let { kind, label, color }: { kind: string | null | undefined; label: string; color?: string } = $props();

	const icon = $derived(aircraftIconKey(kind));
</script>

<svg
	class="aircraft-icon"
	class:dim={icon === 'unknown'}
	viewBox="0 0 64 64"
	role="img"
	aria-label={label}
	style={color ? `color: ${color}` : undefined}
>
	{#if icon === 'helicopter'}
		<line x1="8" y1="14" x2="56" y2="14" class="stroke" />
		<line x1="32" y1="14" x2="32" y2="20" class="stroke" />
		<rect x="24" y="20" width="16" height="14" rx="6" class="fill" />
		<line x1="40" y1="30" x2="56" y2="34" class="stroke" />
		<line x1="52" y1="30" x2="52" y2="38" class="stroke" />
		<line x1="26" y1="34" x2="24" y2="46" class="stroke" />
		<line x1="38" y1="34" x2="40" y2="46" class="stroke" />
		<line x1="20" y1="46" x2="44" y2="46" class="stroke" />
	{:else if icon === 'jet'}
		<path
			d="M32 6 L36 26 L58 40 L58 45 L36 38 L36 50 L44 56 L44 60 L32 57 L20 60 L20 56 L28 50 L28 38 L6 45 L6 40 L28 26 Z"
			class="fill"
		/>
	{:else if icon === 'prop'}
		<circle cx="32" cy="20" r="4" class="fill" />
		<path d="M32 24 L34 48 L38 58 L34 58 L32 50 L30 58 L26 58 L30 48 Z" class="fill" />
		<path d="M32 30 L10 34 L10 30 L32 24 Z" class="fill" />
		<path d="M32 30 L54 34 L54 30 L32 24 Z" class="fill" />
	{:else if icon === 'other'}
		<path
			d="M32 10 L35 26 L54 36 L54 40 L35 34 L35 46 L42 52 L42 55 L32 52 L22 55 L22 52 L29 46 L29 34 L10 40 L10 36 L29 26 Z"
			class="fill"
		/>
	{:else}
		<path
			d="M32 10 L35 26 L54 36 L54 40 L35 34 L35 46 L42 52 L42 55 L32 52 L22 55 L22 52 L29 46 L29 34 L10 40 L10 36 L29 26 Z"
			class="fill"
		/>
	{/if}
</svg>

<style>
	.aircraft-icon {
		width: 100%;
		height: 100%;
		overflow: visible;
		color: var(--color-accent);
	}

	.aircraft-icon.dim {
		color: var(--color-text-muted);
		opacity: 0.6;
	}

	.fill {
		fill: currentColor;
	}

	.stroke {
		stroke: currentColor;
		stroke-width: 3;
		stroke-linecap: round;
	}
</style>
