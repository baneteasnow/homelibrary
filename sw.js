// Home Library Service Worker
// Network First + Offline Support

const CACHE_NAME = "homelibrary-v2"
const OLD_CACHE_NAME = "pwabuilder-offline"
const HOME_PAGE = "/browse/"

const PRECACHE = [HOME_PAGE, "/assets/css/main.css"]

// INSTALL
self.addEventListener("install", (event) => {
	event.waitUntil(
		(async () => {
			const cache = await caches.open(CACHE_NAME)

			// Cache the book collection page.
			await cache.add(HOME_PAGE)

			// Cache additional resources when available.
			await Promise.allSettled(PRECACHE.slice(1).map((url) => cache.add(url)))

			await self.skipWaiting()
		})(),
	)
})

// ACTIVATE
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

// FETCH
self.addEventListener("fetch", (event) => {
	const request = event.request

	if (request.method !== "GET") return

	const url = new URL(request.url)

	if (url.origin !== self.location.origin) return
	if (url.pathname === "/sw.js") return

	event.respondWith(
		(async () => {
			const cache = await caches.open(CACHE_NAME)

			try {
				const response = await fetch(request)

				if (response.ok && response.type === "basic") {
					event.waitUntil(cache.put(request, response.clone()).catch(() => {}))
				}

				return response
			} catch (_) {
				const exact = await cache.match(request, {
					ignoreSearch: request.mode === "navigate",
				})

				if (exact) return exact

				if (request.mode === "navigate") {
					const fallback = await cache.match(HOME_PAGE)

					if (fallback) return fallback
				}

				return Response.error()
			}
		})(),
	)
})
