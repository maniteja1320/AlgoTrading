export function formatAmPmTime(hour12: number, minute: number, ampm: 'AM' | 'PM'): string {
  const h = String(hour12).padStart(2, '0');
  const m = String(minute).padStart(2, '0');
  return `${h}:${m} ${ampm}`;
}

export function parseAmPmTime(value: string): { hour: number; minute: number; ampm: 'AM' | 'PM' } {
  const m = value.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
  if (!m) return { hour: 9, minute: 30, ampm: 'AM' };
  return {
    hour: parseInt(m[1], 10),
    minute: parseInt(m[2], 10),
    ampm: m[3].toUpperCase() as 'AM' | 'PM',
  };
}

export const HOURS_12 = Array.from({ length: 12 }, (_, i) => i + 1);
export const MINUTES = Array.from({ length: 60 }, (_, i) => i);
