/// <reference lib="webworker" />
import { clientsClaim } from 'workbox-core';
import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching';

declare let self: ServiceWorkerGlobalScope & {
  __WB_MANIFEST: Array<{ url: string; revision: string | null }>;
};

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
self.skipWaiting();
clientsClaim();

self.addEventListener('push', (event) => {
  let title = 'BTC Algo';
  let body = '';
  try {
    const data = event.data?.json() as { title?: string; body?: string } | undefined;
    title = data?.title ?? title;
    body = data?.body ?? body;
    // OS notification previews usually show a single line — keep P&L visible.
    body = body.replace(/\s*\n+\s*/g, ' · ').trim();
  } catch {
    body = event.data?.text() ?? body;
  }
  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: '/icon.svg',
      badge: '/icon.svg',
    }),
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      if (clientList.length > 0) {
        return clientList[0].focus();
      }
      return self.clients.openWindow('/');
    }),
  );
});

export {};
