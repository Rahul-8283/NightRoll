/** Local clock time for a status timestamp, e.g. "10:00 PM". */
export function formatClockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
}
