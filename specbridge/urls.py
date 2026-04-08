from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

from specbridge.api import api


def retire_service_worker(request):
    response = HttpResponse(
        """
self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.map((key) => caches.delete(key)));
    await self.registration.unregister();
    const clients = await self.clients.matchAll({ type: "window" });
    for (const client of clients) {
      client.navigate(client.url);
    }
  })());
});

self.addEventListener("fetch", () => {});
        """.strip(),
        content_type='application/javascript',
    )
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


urlpatterns = [
    path('admin-qweasd123/', admin.site.urls),
    path('service-worker.js', retire_service_worker),
    path('api/', api.urls),
    path('', include('accounts.urls')),
    path('', include('projects.urls')),
]
