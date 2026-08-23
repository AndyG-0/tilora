// Svelte action: shows a small floating label for an element on hover
// (desktop) or long-press (touch), since Tilora's kiosk touchscreens have no
// hover state and icon-only buttons would otherwise be undiscoverable.
export function tooltip(node: HTMLElement, text: string) {
	let label = text;
	let tipEl: HTMLDivElement | null = null;
	let showTimer: ReturnType<typeof setTimeout> | undefined;
	let longPressTimer: ReturnType<typeof setTimeout> | undefined;
	let autoHideTimer: ReturnType<typeof setTimeout> | undefined;

	function position() {
		if (!tipEl) return;
		const rect = node.getBoundingClientRect();
		const tipRect = tipEl.getBoundingClientRect();
		const left = Math.min(
			Math.max(8, rect.left + rect.width / 2 - tipRect.width / 2),
			window.innerWidth - tipRect.width - 8,
		);
		tipEl.style.left = `${left}px`;
		tipEl.style.top = `${rect.bottom + 8}px`;
	}

	function show() {
		if (tipEl || !label) return;
		tipEl = document.createElement('div');
		tipEl.className = 'tilora-tooltip';
		tipEl.textContent = label;
		tipEl.setAttribute('role', 'tooltip');
		document.body.appendChild(tipEl);
		position();
	}

	function hide() {
		clearTimeout(showTimer);
		clearTimeout(longPressTimer);
		clearTimeout(autoHideTimer);
		tipEl?.remove();
		tipEl = null;
	}

	function onPointerEnter(e: PointerEvent) {
		if (e.pointerType !== 'mouse') return;
		clearTimeout(showTimer);
		showTimer = setTimeout(show, 500);
	}

	function onPointerDown(e: PointerEvent) {
		if (e.pointerType === 'mouse') return;
		clearTimeout(longPressTimer);
		longPressTimer = setTimeout(show, 500);
	}

	function onPointerUp() {
		clearTimeout(longPressTimer);
		if (tipEl) {
			clearTimeout(autoHideTimer);
			autoHideTimer = setTimeout(hide, 1500);
		}
	}

	node.addEventListener('pointerenter', onPointerEnter);
	node.addEventListener('pointerleave', hide);
	node.addEventListener('pointerdown', onPointerDown);
	node.addEventListener('pointerup', onPointerUp);
	node.addEventListener('pointercancel', hide);
	node.addEventListener('focus', show);
	node.addEventListener('blur', hide);

	return {
		update(newText: string) {
			label = newText;
			if (tipEl) tipEl.textContent = label;
		},
		destroy() {
			hide();
			node.removeEventListener('pointerenter', onPointerEnter);
			node.removeEventListener('pointerleave', hide);
			node.removeEventListener('pointerdown', onPointerDown);
			node.removeEventListener('pointerup', onPointerUp);
			node.removeEventListener('pointercancel', hide);
			node.removeEventListener('focus', show);
			node.removeEventListener('blur', hide);
		},
	};
}
