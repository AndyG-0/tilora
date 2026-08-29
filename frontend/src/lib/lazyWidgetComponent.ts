// Deduped, cross-consumer cache for lazily-loaded widget components. A type
// resolved once (dashboard grid, detail page, or screensaver) is never
// re-fetched or re-triggered elsewhere in the same session — the cache is
// keyed by the loader function's own identity, so widgetComponents.ts's
// per-type thunks double as the cache key.
import type { Component } from 'svelte';

// Props are intentionally untyped here (`any`): each widget type's tile,
// detail, and screensaver component has its own distinct, often-required prop
// shape (e.g. a `data` prop of a specific type), and Svelte component props
// are contravariant — no single non-`any` Props type is a valid stand-in for
// all 34 of them at once (`Record<string, unknown>` fails to typecheck here
// because it doesn't guarantee any particular component's required props
// exist). Callers already know (from `widget.type`) which component they're
// rendering and pass matching props at the call site.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type ComponentLoader = () => Promise<{ default: Component<any> }>;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const resolved = new Map<ComponentLoader, Component<any>>();
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const inFlight = new Map<ComponentLoader, Promise<Component<any>>>();

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function loadComponent(loader: ComponentLoader): Promise<Component<any>> {
	const cached = resolved.get(loader);
	if (cached) return Promise.resolve(cached);

	const pending = inFlight.get(loader);
	if (pending) return pending;

	const promise = loader().then(({ default: component }) => {
		resolved.set(loader, component);
		inFlight.delete(loader);
		return component;
	});
	inFlight.set(loader, promise);
	return promise;
}

export function getResolvedComponent(
	loader: ComponentLoader | undefined,
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
): Component<any> | undefined {
	if (!loader) return undefined;
	return resolved.get(loader);
}
