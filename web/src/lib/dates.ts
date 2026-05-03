import { Temporal } from "@js-temporal/polyfill";

// The strict `YYYY` or `YYYY-MM` format is enforced by the backend's
// Pydantic PartialDate validator. We keep it as `string` on the frontend
// so a too-strict TS literal doesn't fight legitimate edits in the form.
type PartialDate = string;

// Three-letter month prefix → 1-indexed month number.
const MONTHS: Record<string, number> = {
  jan: 1,
  feb: 2,
  mar: 3,
  apr: 4,
  may: 5,
  jun: 6,
  jul: 7,
  aug: 8,
  sep: 9,
  oct: 10,
  nov: 11,
  dec: 12,
};

/**
 * Best-effort coerce a free-form date string into our strict
 * `YYYY[-MM]` PartialDate format. Returns "" if no plausible year can
 * be extracted.
 *
 * Real-world parser inputs we have to handle:
 *   "2021-01"   "2021-1-15"   "1/2021"   "Jan 2021"   "2021"
 *
 * Validation goes through `Temporal.PlainYearMonth.from` so a parser
 * bug producing month=13 gets caught here rather than rejected by the
 * backend's stricter PartialDate regex.
 */
export function coerceDate(raw: string | null | undefined): PartialDate {
  if (!raw) return "";
  const s = raw.trim();

  // YYYY-MM(-DD): year and month explicit and ISO-ordered.
  let m = s.match(/(\d{4})-(\d{1,2})/);
  if (m) return formatYearMonth(parseInt(m[1], 10), parseInt(m[2], 10));

  // M/YYYY (US-style)
  m = s.match(/(\d{1,2})\/(\d{4})/);
  if (m) return formatYearMonth(parseInt(m[2], 10), parseInt(m[1], 10));

  // "Jan 2021" / "Jan. 2021" / "January 2021"
  m = s.match(/([A-Za-z]+)[a-z]*\.?\s+(\d{4})/);
  if (m) {
    const monthNum = MONTHS[m[1].slice(0, 3).toLowerCase()];
    if (monthNum) return formatYearMonth(parseInt(m[2], 10), monthNum);
  }

  // Year only — last resort.
  m = s.match(/(\d{4})/);
  if (m) {
    const year = parseInt(m[1], 10);
    if (isPlausibleYear(year)) return m[1];
  }

  return "";
}

/**
 * The default "start" date for a new experience entry — the current
 * year as a PartialDate.
 */
export function currentYearString(): PartialDate {
  return Temporal.Now.plainDateISO().year.toString();
}

// --- Internals -----------------------------------------------------------

function formatYearMonth(year: number, month: number): PartialDate {
  if (!isPlausibleYear(year)) return "";
  try {
    return Temporal.PlainYearMonth.from({ year, month }).toString() as PartialDate;
  } catch {
    // Invalid month (0, 13+). Year alone still useful.
    return year.toString();
  }
}

function isPlausibleYear(year: number): boolean {
  return year >= 1900 && year <= 2100;
}
