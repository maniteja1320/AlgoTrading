/** Options expire at 5:30 PM IST on the expiry calendar day. */

const IST_OFFSET_MS = 5.5 * 60 * 60 * 1000;

function parseExpiry(expiry: string): Date {
  const [day, month, year] = expiry.split('-').map(Number);
  // 5:30 PM IST = 12:00 UTC on same calendar date (IST = UTC+5:30)
  return new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
}

function nowIst(): Date {
  return new Date(Date.now() + IST_OFFSET_MS - new Date().getTimezoneOffset() * 60 * 1000);
}

export function sortExpiries(expiries: string[]): string[] {
  return [...expiries].sort((a, b) => parseExpiry(a).getTime() - parseExpiry(b).getTime());
}

export function activeExpiries(expiries: string[], now = nowIst()): string[] {
  return sortExpiries(expiries).filter((e) => parseExpiry(e) > now);
}

export function expirySlotLabels(expiries: string[]): { today?: string; tomorrow?: string } {
  const active = activeExpiries(expiries);
  return {
    today: active[0],
    tomorrow: active[1],
  };
}
