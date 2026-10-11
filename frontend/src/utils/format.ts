const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2, minimumFractionDigits: 0 });

/** Currency that never renders null/undefined/NaN. */
export function formatINR(value: number | null | undefined, fallback = "Not assigned"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return fallback;
  return inr.format(value);
}

/** Royalty amounts default to ₹0 rather than "not assigned". */
export const formatRoyalty = (value: number | null | undefined): string => formatINR(value ?? 0);

const dateFmt = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("en-IN", {
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

function parse(value: string | null | undefined): Date | null {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined, fallback = "—"): string {
  const d = parse(value);
  return d ? dateFmt.format(d) : fallback;
}

export function formatDateTime(value: string | null | undefined, fallback = "—"): string {
  const d = parse(value);
  return d ? dateTimeFmt.format(d) : fallback;
}

export function timeAgo(value: string | null | undefined, now: Date = new Date()): string {
  const d = parse(value);
  if (!d) return "—";
  const seconds = Math.max(0, Math.round((now.getTime() - d.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return days < 30 ? `${days}d ago` : formatDate(value);
}

export const formatPercent = (value: number | null | undefined): string =>
  value === null || value === undefined || Number.isNaN(value) ? "—" : `${Math.round(value * 100)}%`;

export const orText = (value: string | null | undefined, fallback: string): string =>
  value && value.trim() ? value : fallback;

export const humanize = (value: string): string =>
  value
    .toLowerCase()
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

/** Word-overlap ratio (Jaccard) used to decide whether a sent reply is still "AI-assisted". */
export function textSimilarity(a: string, b: string): number {
  const words = (s: string) => new Set(s.toLowerCase().match(/[a-z0-9₹]+/g) ?? []);
  const wa = words(a);
  const wb = words(b);
  if (wa.size === 0 || wb.size === 0) return 0;
  let shared = 0;
  wa.forEach((w) => wb.has(w) && shared++);
  return shared / (wa.size + wb.size - shared);
}
