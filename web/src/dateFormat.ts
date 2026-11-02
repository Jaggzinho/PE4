// Keep ISO values in transport/state; format calendar dates without timezone conversion.
export function formatDate(value: string | null | undefined, empty = "—"): string {
  if (!value) return empty;
  const match = /^(\d{4})-(\d{2})-(\d{2})(?:$|T| )/.exec(value);
  return match ? `${match[3]}-${match[2]}-${match[1]}` : empty;
}

export function parseDisplayDate(value: string): string | null {
  const match = /^(\d{2})-(\d{2})-(\d{4})$/.exec(value);
  if (!match) return null;
  const [, day, month, year] = match;
  const iso = `${year}-${month}-${day}`;
  const date = new Date(`${iso}T00:00:00Z`);
  return Number(year) > 0 && Number.isFinite(date.getTime()) && date.toISOString().slice(0, 10) === iso ? iso : null;
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const day = formatDate(value);
  const time = /[T ](\d{2}:\d{2}(?::\d{2})?)/.exec(value)?.[1];
  return time && day !== "—" ? `${day} ${time}` : day;
}
