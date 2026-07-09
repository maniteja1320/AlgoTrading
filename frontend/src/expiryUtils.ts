/** Options expire at 5:30 PM IST on the expiry calendar day. */

function parseExpiry(expiry: string): Date {
  const [day, month, year] = expiry.split('-').map(Number);
  // 5:30 PM IST on expiry day = 12:00 UTC on the same calendar date
  return new Date(Date.UTC(year, month - 1, day, 12, 0, 0));
}

export function sortExpiries(expiries: string[]): string[] {
  return [...expiries].sort((a, b) => parseExpiry(a).getTime() - parseExpiry(b).getTime());
}

/** Expiries not yet settled (cutoff 5:30 PM IST on expiry day). */
export function activeExpiries(expiries: string[], nowMs = Date.now()): string[] {
  return sortExpiries(expiries).filter((e) => parseExpiry(e).getTime() > nowMs);
}

export interface ExpirySlotOption {
  value: string;
  label: string;
}

export function expirySlotValue(index: number): string {
  if (index === 0) return 'today';
  if (index === 1) return 'tomorrow';
  return `slot_${index}`;
}

export function expirySlotOptions(expiries: string[]): ExpirySlotOption[] {
  const active = activeExpiries(expiries);
  return active.map((date, i) => {
    const value = expirySlotValue(i);
    if (i === 0) return { value, label: `Today (${date})` };
    if (i === 1) return { value, label: `Tomorrow (${date})` };
    return { value, label: date };
  });
}

export function expirySlotLabel(slot: string, expiries: string[]): string {
  const match = expirySlotOptions(expiries).find((o) => o.value === slot);
  return match?.label ?? slot;
}

export function expirySlotLabels(expiries: string[]): { today?: string; tomorrow?: string } {
  const active = activeExpiries(expiries);
  return {
    today: active[0],
    tomorrow: active[1],
  };
}
