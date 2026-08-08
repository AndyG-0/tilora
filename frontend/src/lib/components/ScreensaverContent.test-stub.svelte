<script lang="ts">
	// Test-only stand-in for the real ScreensaverContent.svelte, used by
	// Screensaver.test.ts to keep that suite focused on Screensaver.svelte's
	// own orchestration (id/type selection, rotation timing, stale-id skip)
	// rather than any visual/wordy component's internal markup.
	let { type, data, textAnimationStyle }: { type: string; data: unknown; textAnimationStyle: string } = $props();
</script>

<div data-testid="screensaver-content">type={type} data={JSON.stringify(data)} style={textAnimationStyle}</div>
