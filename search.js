/* Home Library PWA — network-first, versioned offline cache */
const CACHE_NAME = "homelibrary-v1"
const OLD_CACHE_NAME = "pwabuilder-offline"
const APP_SHELL = ["/browse/", "/assets/css/main.css"]
const MAX_CACHED_ASSETS = 80

self.addEventListener("install", (event) => {
	event.waitUntil(
		caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)),
	)
	self.skipWaiting()
})

self.addEventListener("activate", (event) => {
	event.waitUntil(
		(async () => {
			const names = await caches.keys()
			await Promise.all(
				names
					.filter(
						(name) =>
							name === OLD_CACHE_NAME ||
							(name.startsWith("homelibrary-") && name !== CACHE_NAME),
					)
					.map((name) => caches.delete(name)),
			)
			await self.clients.claim()
		})(),
	)
})

self.addEventListener("fetch", (event) => {
	const request = event.request
	if (request.method !== "GET") return

	const url = new URL(request.url)
	if (url.origin !== self.location.origin) return
	if (request.cache === "only-if-cached") return

	// Pages (including the embedded book data) always try the network first.
	if (request.mode === "navigate") {
		event.respondWith(
			(async () => {
				try {
					const response = await fetch(request)
					if (response.ok) {
						const cache = await caches.open(CACHE_NAME)
						await cache.put(request, response.clone()).catch(() => {})
					}
					return response
				} catch {
					const cache = await caches.open(CACHE_NAME)
					const saved = await cache.match(request, { ignoreSearch: true })
					if (saved) return saved
					return new Response("This page is unavailable offline.", {
						status: 503,
						headers: { "Content-Type": "text/plain; charset=utf-8" },
					})
				}
			})(),
		)
		return
	}

	// Cache only local CSS, JS and images, not every request.
	if (!/\.(?:css|js|png|jpg|jpeg|webp|svg|ico)$/i.test(url.pathname)) return

	event.respondWith(
		(async () => {
			try {
				const response = await fetch(request)
				if (response.ok) {
					event.waitUntil(
						(async () => {
							const cache = await caches.open(CACHE_NAME)
							await cache.put(request, response.clone())
							const keys = (await cache.keys()).filter((item) =>
								/\.(?:css|js|png|jpg|jpeg|webp|svg|ico)$/i.test(
									new URL(item.url).pathname,
								),
							)
							for (const key of keys.slice(
								0,
								Math.max(0, keys.length - MAX_CACHED_ASSETS),
							)) {
								await cache.delete(key)
							}
						})().catch(() => {}),
					)
				}
				return response
			} catch {
				const cache = await caches.open(CACHE_NAME)
				return (await cache.match(request)) || Response.error()
			}
		})(),
	)
})
