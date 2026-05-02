import { useState } from "react";
import { JdStep } from "./components/JdStep";
import { ResumeStep } from "./components/ResumeStep";
import { TailorStep } from "./components/TailorStep";
import { useLocalStorage } from "./hooks/useLocalStorage";
import { sampleResume } from "./sampleResume";
import type { JobDescription, ResumeInput, TailorSettings } from "./types";

const TABS = ["Your resume", "Job description", "Tailor & download"] as const;

export default function App() {
  const [resume, setResume] = useLocalStorage<ResumeInput>("rt:resume", sampleResume);
  const [jd, setJd] = useLocalStorage<JobDescription>("rt:jd", { text: "" });
  const [settings] = useLocalStorage<TailorSettings>("rt:settings", {
    tiebreaker: "input_order",
  });
  const [tab, setTab] = useState<0 | 1 | 2>(0);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Resume Tailor</h1>
            <p className="text-xs text-slate-500">
              Bullets you wrote, tailored to one JD, in 10 seconds.
            </p>
          </div>
          <a
            href="https://github.com/akin-oz/resume-tailor"
            className="text-xs text-slate-600 hover:underline"
          >
            GitHub
          </a>
        </div>
      </header>

      <nav className="mx-auto max-w-6xl px-6 pt-4" aria-label="Steps">
        <div role="tablist" className="flex gap-1 border-b border-slate-200">
          {TABS.map((label, i) => (
            <button
              key={label}
              role="tab"
              aria-selected={tab === i}
              onClick={() => setTab(i as 0 | 1 | 2)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === i
                  ? "border-accent text-accent"
                  : "border-transparent text-slate-600 hover:text-slate-900"
              }`}
            >
              <span className="text-slate-400 mr-2">{i + 1}.</span>
              {label}
            </button>
          ))}
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-6 py-6">
        {tab === 0 && <ResumeStep value={resume} onChange={setResume} />}
        {tab === 1 && <JdStep value={jd} onChange={setJd} />}
        {tab === 2 && <TailorStep resume={resume} jd={jd} settings={settings} />}
      </main>

      <footer className="mx-auto max-w-6xl px-6 py-6 text-xs text-slate-500">
        Your data stays in your browser. No accounts, no database, no server-side
        storage. Stub mode works offline; OpenAI mode kicks in when{" "}
        <code className="font-mono">OPENAI_API_KEY</code> is configured server-side.
      </footer>
    </div>
  );
}
