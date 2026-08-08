<script lang="ts">
	import { _ } from 'svelte-i18n';

	interface Props {
		src: string;
		title: string;
		onClose: () => void;
	}

	let { src, title, onClose }: Props = $props();

	// The dashboard grid's tab-swipe track has a `transform`, which makes it
	// both a new stacking context and the containing block for `position:
	// fixed` descendants — trapping this overlay's z-index below the page's
	// top-bar buttons no matter how high it's set. Move the DOM node to
	// <body> so it stacks at the root instead.
	function portal(node: HTMLElement) {
		document.body.appendChild(node);
		return {
			destroy() {
				node.remove();
			},
		};
	}
</script>

<div class="overlay" role="dialog" aria-label={title} use:portal>
	<div class="header">
		<h2>{title}</h2>
		<button class="close" onclick={onClose} aria-label={$_('player.close')}>✕</button>
	</div>
	<!-- svelte-ignore a11y_media_has_caption -->
	<video controls autoplay playsinline class="video" {src}></video>
</div>

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 100;
		background: #000;
		display: flex;
		flex-direction: column;
	}

	.header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 1rem;
		padding: 0.75rem 1rem;
		background: rgba(0, 0, 0, 0.6);
	}

	.header h2 {
		margin: 0;
		color: #fff;
		font-size: 1rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.close {
		flex-shrink: 0;
		background: none;
		border: 1px solid rgba(255, 255, 255, 0.4);
		border-radius: 50%;
		width: 2rem;
		height: 2rem;
		color: #fff;
		cursor: pointer;
	}

	.video {
		flex: 1;
		width: 100%;
		min-height: 0;
		object-fit: contain;
		background: #000;
	}
</style>
