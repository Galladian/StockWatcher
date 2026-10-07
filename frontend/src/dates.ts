// Dates travel to and from the backend as ISO (YYYY-MM-DD) and are shown as DD/MM/YYYY.
const pad = (n: number) => String(n).padStart(2, "0");

export function localTodayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** "2026-10-07" -> "07/10/2026". Anything that isn't an ISO date is returned unchanged. */
export function isoToDmy(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** Keeps only digits and inserts the slashes while typing: "07102026" -> "07/10/2026". */
export function maskDmy(raw: string): string {
  const d = raw.replace(/\D/g, "").slice(0, 8);
  if (d.length > 4) return `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}`;
  if (d.length > 2) return `${d.slice(0, 2)}/${d.slice(2)}`;
  return d;
}

/** "07/10/2026" -> "2026-10-07", or null if it isn't a real date, is before 1990 or is in the future. */
export function parseDmy(text: string): string | null {
  const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(text);
  if (!m) return null;
  const day = +m[1], month = +m[2], year = +m[3];
  const dt = new Date(year, month - 1, day);
  if (dt.getFullYear() !== year || dt.getMonth() !== month - 1 || dt.getDate() !== day) return null;
  if (year < 1990) return null;
  const iso = `${year}-${pad(month)}-${pad(day)}`;
  return iso > localTodayIso() ? null : iso;
}
