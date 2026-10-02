const LIVE2D_CACHE="resonance-live2d-v2";

self.addEventListener("install",event=>event.waitUntil(self.skipWaiting()));
self.addEventListener("activate",event=>event.waitUntil(self.clients.claim()));
self.addEventListener("fetch",event=>{
  const url=new URL(event.request.url);
  if(event.request.method!=="GET"||!url.pathname.startsWith("/live2d-assets/"))return;
  event.respondWith((async()=>{
    const cache=await caches.open(LIVE2D_CACHE);
    const cached=await cache.match(event.request);
    if(cached)return cached;
    const response=await fetch(event.request);
    if(response.ok)cache.put(event.request,response.clone()).catch(()=>{});
    return response;
  })());
});
