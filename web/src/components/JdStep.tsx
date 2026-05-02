import type { JobDescription } from "../types";

const SECTION = "rounded-lg border border-slate-200 bg-white p-4";
const INPUT =
  "w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-accent focus:ring-1 focus:ring-accent";

interface Props {
  value: JobDescription;
  onChange: (next: JobDescription) => void;
}

export function JdStep({ value, onChange }: Props) {
  return (
    <section className={SECTION}>
      <h2 className="text-sm font-semibold text-slate-900 mb-1">Job description</h2>
      <p className="text-xs text-slate-500 mb-3">
        Paste the JD. The tailor uses it to rank your bullets and shape the
        profile paragraph. Detected archetype is shown after you click Tailor on
        the next tab.
      </p>
      <textarea
        className={`${INPUT} min-h-[300px] font-mono text-xs leading-relaxed`}
        placeholder="Paste the job description here…"
        value={value.text}
        onChange={(e) => onChange({ ...value, text: e.target.value })}
      />
      <div className="mt-2 text-xs text-slate-500">
        {value.text.length} characters{" "}
        {value.text.length < 50 && (
          <span className="text-amber-600">
            — at least 50 required before tailoring
          </span>
        )}
      </div>
    </section>
  );
}
