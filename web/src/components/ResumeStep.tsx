import type { Experience, ResumeInput, Story } from "../types";

const SECTION = "rounded-lg border border-slate-200 bg-white p-4 mb-4";
const LABEL = "block text-xs font-medium text-slate-600 mb-1";
const INPUT =
  "w-full rounded border border-slate-300 px-2 py-1 text-sm focus:border-accent focus:ring-1 focus:ring-accent";

interface Props {
  value: ResumeInput;
  onChange: (next: ResumeInput) => void;
}

export function ResumeStep({ value, onChange }: Props) {
  const update = (patch: Partial<ResumeInput>) => onChange({ ...value, ...patch });

  const setExperience = (idx: number, exp: Experience) => {
    const next = [...value.experiences];
    next[idx] = exp;
    update({ experiences: next });
  };

  const addExperience = () => {
    // crypto.randomUUID() is opaque, unique, and safe across deletions —
    // length-based IDs collide after a remove + re-add.
    const nextId = `exp-${crypto.randomUUID()}`;
    update({
      experiences: [
        ...value.experiences,
        {
          id: nextId,
          company: "",
          title: "",
          start: new Date().getFullYear().toString(),
          stories: [],
        },
      ],
    });
  };

  const removeExperience = (idx: number) => {
    update({ experiences: value.experiences.filter((_, i) => i !== idx) });
  };

  return (
    <div>
      <section className={SECTION}>
        <h2 className="text-sm font-semibold text-slate-900 mb-3">Contact</h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Name">
            <input
              className={INPUT}
              value={value.contact.name}
              onChange={(e) =>
                update({ contact: { ...value.contact, name: e.target.value } })
              }
            />
          </Field>
          <Field label="Email">
            <input
              className={INPUT}
              type="email"
              value={value.contact.email}
              onChange={(e) =>
                update({ contact: { ...value.contact, email: e.target.value } })
              }
            />
          </Field>
          <Field label="Location">
            <input
              className={INPUT}
              value={value.contact.location ?? ""}
              onChange={(e) =>
                update({
                  contact: { ...value.contact, location: e.target.value || null },
                })
              }
            />
          </Field>
          <Field label="LinkedIn">
            <input
              className={INPUT}
              placeholder="https://linkedin.com/in/…"
              value={value.contact.linkedin ?? ""}
              onChange={(e) =>
                update({
                  contact: { ...value.contact, linkedin: e.target.value || null },
                })
              }
            />
          </Field>
        </div>
      </section>

      <section className={SECTION}>
        <h2 className="text-sm font-semibold text-slate-900 mb-1">Profile seed</h2>
        <p className="text-xs text-slate-500 mb-2">
          Your one-paragraph self-summary in your own voice. The model may rephrase
          it but won&rsquo;t introduce new facts.
        </p>
        <textarea
          className={`${INPUT} min-h-[100px]`}
          value={value.profileSeed}
          onChange={(e) => update({ profileSeed: e.target.value })}
        />
      </section>

      <section className={SECTION}>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-slate-900">Experience</h2>
          <button
            type="button"
            onClick={addExperience}
            className="text-xs text-accent hover:underline"
          >
            + Add experience
          </button>
        </div>
        {value.experiences.map((exp, idx) => (
          <ExperienceCard
            key={exp.id}
            value={exp}
            onChange={(next) => setExperience(idx, next)}
            onRemove={() => removeExperience(idx)}
          />
        ))}
      </section>

      <section className={SECTION}>
        <h2 className="text-sm font-semibold text-slate-900 mb-1">Skills</h2>
        <p className="text-xs text-slate-500 mb-2">Comma-separated.</p>
        <input
          className={INPUT}
          value={(value.skills ?? []).join(", ")}
          onChange={(e) =>
            update({
              skills: e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
            })
          }
        />
      </section>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className={LABEL}>{label}</span>
      {children}
    </label>
  );
}

interface ExpProps {
  value: Experience;
  onChange: (next: Experience) => void;
  onRemove: () => void;
}

function ExperienceCard({ value, onChange, onRemove }: ExpProps) {
  const update = (patch: Partial<Experience>) => onChange({ ...value, ...patch });

  const setStory = (idx: number, story: Story) => {
    const next = [...value.stories];
    next[idx] = story;
    update({ stories: next });
  };

  const addStory = () => {
    // Same uniqueness reasoning as addExperience — bullet IDs are opaque
    // identifiers the backend joins on, so they must never get reused.
    const nextId = `${value.id}.${crypto.randomUUID()}`;
    update({
      stories: [...value.stories, { id: nextId, text: "", keywords: [] }],
    });
  };

  const removeStory = (idx: number) => {
    update({ stories: value.stories.filter((_, i) => i !== idx) });
  };

  return (
    <div className="rounded border border-slate-200 p-3 mb-3 last:mb-0">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Title">
          <input
            className={INPUT}
            value={value.title}
            onChange={(e) => update({ title: e.target.value })}
          />
        </Field>
        <Field label="Company">
          <input
            className={INPUT}
            value={value.company}
            onChange={(e) => update({ company: e.target.value })}
          />
        </Field>
        <Field label="Start (YYYY or YYYY-MM)">
          <input
            className={INPUT}
            value={value.start}
            onChange={(e) => update({ start: e.target.value })}
          />
        </Field>
        <Field label="End (blank = Present)">
          <input
            className={INPUT}
            value={value.end ?? ""}
            onChange={(e) => update({ end: e.target.value || null })}
          />
        </Field>
      </div>

      <div className="mt-3">
        <div className="flex items-center justify-between mb-1">
          <span className={LABEL}>Stories — bullets the tailor picks from</span>
          <button
            type="button"
            onClick={addStory}
            className="text-xs text-accent hover:underline"
          >
            + Add bullet
          </button>
        </div>
        {value.stories.map((story, idx) => (
          <StoryRow
            key={story.id}
            value={story}
            onChange={(next) => setStory(idx, next)}
            onRemove={() => removeStory(idx)}
          />
        ))}
      </div>

      <div className="mt-3 text-right">
        <button
          type="button"
          onClick={onRemove}
          className="text-xs text-slate-500 hover:text-red-600"
        >
          Remove experience
        </button>
      </div>
    </div>
  );
}

interface StoryRowProps {
  value: Story;
  onChange: (next: Story) => void;
  onRemove: () => void;
}

function StoryRow({ value, onChange, onRemove }: StoryRowProps) {
  return (
    <div className="flex gap-2 mb-2">
      <input
        className={INPUT}
        placeholder="Bullet text"
        value={value.text}
        onChange={(e) => onChange({ ...value, text: e.target.value })}
      />
      <input
        className={`${INPUT} max-w-[40%]`}
        placeholder="keywords (comma-separated)"
        value={value.keywords.join(", ")}
        onChange={(e) =>
          onChange({
            ...value,
            keywords: e.target.value
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean),
          })
        }
      />
      <button
        type="button"
        onClick={onRemove}
        aria-label="Remove bullet"
        className="text-slate-400 hover:text-red-600 px-2"
      >
        ×
      </button>
    </div>
  );
}
