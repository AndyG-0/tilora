/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

declare const self: ServiceWorkerGlobalScope;

import { build, files, version } from '$service-worker';

export const CACHE_NAME = `tilora-cache-${version}`;
export const ASSETS = [...build, ...files];

export async function handleInstall(): Promise<void> {
	const cache = await caches.open(CACHE_NAME);
	await cache.addAll(ASSETS);
	await self.skipWaiting();
}

export async function handleActivate(): Promise<void> {
	const keys = await caches.keys();
	for (const key of keys) {
		if (key !== CACHE_NAME) {
			await caches.delete(key);
		}
	}
	await self.clients.claim();
}

export function handleMessage(event: { data?: { type?: string } }): void {
	if (event.data && event.data.type === 'SKIP_WAITING') {
		self.skipWaiting();
	}
}

if (typeof self !== 'undefined' && typeof self.addEventListener === 'function') {
	self.addEventListener('install', (event) => {
		event.waitUntil(handleInstall());
	});

	self.addEventListener('activate', (event) => {
		event.waitUntil(handleActivate());
	});

	self.addEventListener('fetch', (event) => {
		if (event.request.method !== 'GET') return;

		const url = new URL(event.request.url);

		// Only handle HTTP/HTTPS protocols
		if (!url.protocol.startsWith('http')) return;

		// Never cache API routes or dynamic server endpoints
		if (url.pathname.startsWith('/api/')) return;

		// Never intercept streaming media (.m3u8, .ts) or WebSockets
		if (url.pathname.endsWith('.m3u8') || url.pathname.endsWith('.ts')) return;

		// Cache-first for build and static assets
		const isStaticAsset =
			build.includes(url.pathname) || files.includes(url.pathname) || url.pathname.startsWith('/_app/immutable/');

		async function respond(): Promise<Response> {
			const cache = await caches.open(CACHE_NAME);

			if (isStaticAsset) {
				const cached = await cache.match(event.request);
				if (cached) return cached;

				try {
					const response = await fetch(event.request);
					if (response.status === 200) {
						await cache.put(event.request, response.clone());
					}
					return response;
				} catch {
					return new Response('Not found', { status: 404 });
				}
			}

			if (event.request.mode === 'navigate') {
				try {
					return await fetch(event.request);
				} catch {
					const cached = await cache.match(event.request);
					if (cached) return cached;
					const rootCached = await cache.match('/');
					if (rootCached) return rootCached;
					return new Response('Offline - Tilora is currently unreachable', {
						status: 503,
						statusText: 'Service Unavailable',
						headers: { 'Content-Type': 'text/plain' },
					});
				}
			}

			const cached = await cache.match(event.request);
			const fetchPromise = fetch(event.request)
				.then(async (response) => {
					if (response.status === 200) {
						await cache.put(event.request, response.clone());
					}
					return response;
				})
				.catch(() => {
					if (cached) return cached;
					return new Response('Unavailable', { status: 503 });
				});

			return cached || fetchPromise;
		}

		event.respondWith(respond());
	});

	self.addEventListener('message', (event) => {
		handleMessage(event);
	});
}
