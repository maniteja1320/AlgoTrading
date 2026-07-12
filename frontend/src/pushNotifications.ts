import { api } from './api';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) {
    output[i] = raw.charCodeAt(i);
  }
  return output;
}

export function isPushSupported(): boolean {
  return 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
}

export async function isPushSubscribedLocally(): Promise<boolean> {
  if (!isPushSupported()) return false;
  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    return subscription !== null;
  } catch {
    return false;
  }
}

export async function subscribePushNotifications(): Promise<void> {
  if (!isPushSupported()) {
    throw new Error('Push notifications are not supported in this browser');
  }

  const config = await api.getPushConfig();
  if (!config.enabled || !config.vapid_public_key) {
    throw new Error('Push notifications are not configured on the server');
  }

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Notification permission was denied');
  }

  const registration = await navigator.serviceWorker.ready;
  const existing = await registration.pushManager.getSubscription();
  if (existing) {
    await api.subscribePush(existing.toJSON() as PushSubscriptionJSON);
    return;
  }

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key),
  });
  await api.subscribePush(subscription.toJSON() as PushSubscriptionJSON);
}

export async function unsubscribePushNotifications(): Promise<void> {
  if (!isPushSupported()) return;

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.getSubscription();
  if (!subscription) return;

  await api.unsubscribePush({ endpoint: subscription.endpoint });
  await subscription.unsubscribe();
}
