import { useEffect, useState } from "react";
import {
  fetchTemplates,
  postRenderHtml,
  postRenderPdf,
  postTailor,
} from "../api";
import type {
  JobDescription,
  ResumeInput,
  TailorResult,
  TailorSettings,
  TemplateId,
  TemplateMeta,
} from "../types";

const CARD = "rounded-lg border border-slate-200 bg-white p-4";

interface Props {
  resume: ResumeInput;
  jd: JobDescription;
  settings: TailorSettings;
}

export function TailorStep({ resume, jd, settings }: Props) {
  const [templates, setTemplates] = useState<TemplateMeta[]>([]);
  const [templateId, setTemplateId] = useState<TemplateId>("modern");
  const [tailored, setTailored] = useState<TailorResult | null>(null);
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState<string | null>(null);

  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch((err) => setTailorError(`Could not load templates: ${err.message}`));
  }, []);

  const onTailor = async () => {
    if (jd.text.length < 50) {
      setTailorError("Job description must be at least 50 characters.");
      return;
    }
    setTailoring(true);
    setTailorError(null);
    try {
      const result = await postTailor({ resume, jd, settings });
      setTailored(result);
    } catch (err) {
      setTailorError(err instanceof Error ? err.message : String(err));
    } finally {
      setTailoring(false);
    }
  };

  // Re-render the preview whenever the tailored result or template changes.
  useEffect(() => {
    if (!tailored) return;
    setRendering(true);
    postRenderHtml({ resume, tailored, templateId, format: "html" })
      .then(setPreviewHtml)
      .catch((err) => setTailorError(err.message))
      .finally(() => setRendering(false));
  }, [resume, tailored, templateId]);

  const onDownloadPdf = async () => {
    if (!tailored) return;
    setDownloading(true);
    try {
      const blob = await postRenderPdf({ resume, tailored, templateId, format: "pdf" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${resume.contact.name.replace(/\s+/g, "_")}_resume.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setTailorError(err instanceof Error ? err.message : String(err));
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]">
      <aside className="space-y-4">
        <section className={CARD}>
          <h2 className="text-sm font-semibold mb-2">Tailor</h2>
          <button
            type="button"
            onClick={onTailor}
            disabled={tailoring}
            className="w-full rounded bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
            aria-live="polite"
          >
            {tailoring ? "Selecting bullets…" : tailored ? "Re-tailor" : "Tailor"}
          </button>
          {tailorError && (
            <p className="mt-2 text-xs text-red-600" role="alert">
              {tailorError}
            </p>
          )}
        </section>

        {tailored && (
          <section className={CARD} aria-live="polite">
            <h2 className="text-sm font-semibold mb-2">Result</h2>
            <dl className="text-xs space-y-1 text-slate-700">
              <div className="flex justify-between">
                <dt className="text-slate-500">Archetype</dt>
                <dd className="font-medium">{tailored.archetypeUsed}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Bullets picked</dt>
                <dd className="font-medium">
                  {tailored.experiences.reduce((n, e) => n + e.storyIds.length, 0)}
                </dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Profile words</dt>
                <dd className="font-medium">{tailored.profile.split(/\s+/).length}</dd>
              </div>
            </dl>
            {tailored.profileFallbackUsed && (
              <p className="mt-2 text-xs text-amber-600">
                Profile fell back to your seed (model output failed validation).
              </p>
            )}
            {tailored.droppedStoryIds.length > 0 && (
              <p className="mt-2 text-xs text-amber-600">
                Dropped {tailored.droppedStoryIds.length} hallucinated ID(s).
              </p>
            )}
            {tailored.keywordsInjected.length > 0 && (
              <div className="mt-3">
                <p className="text-xs text-slate-500 mb-1">Why these bullets:</p>
                <div className="flex flex-wrap gap-1">
                  {tailored.keywordsInjected.map((kw) => (
                    <span
                      key={kw}
                      className="rounded-full bg-teal-50 px-2 py-0.5 text-[10px] text-teal-800"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {tailored && (
          <section className={CARD}>
            <h2 className="text-sm font-semibold mb-2">Template</h2>
            <div className="space-y-2">
              {templates.map((t) => (
                <label
                  key={t.id}
                  className={`block rounded border p-2 text-xs cursor-pointer ${
                    templateId === t.id
                      ? "border-accent bg-teal-50"
                      : "border-slate-200 hover:border-slate-300"
                  }`}
                >
                  <input
                    type="radio"
                    name="template"
                    value={t.id}
                    checked={templateId === t.id}
                    onChange={() => setTemplateId(t.id)}
                    className="sr-only"
                  />
                  <div className="font-medium">{t.name}</div>
                  <div className="text-slate-500 mt-0.5">{t.description}</div>
                </label>
              ))}
            </div>
            <button
              type="button"
              onClick={onDownloadPdf}
              disabled={downloading || !previewHtml}
              className="mt-3 w-full rounded border border-slate-300 px-3 py-2 text-sm hover:bg-slate-50 disabled:opacity-50"
              aria-live="polite"
            >
              {downloading ? "Rendering PDF…" : "Download PDF"}
            </button>
          </section>
        )}
      </aside>

      <section className={CARD}>
        <h2 className="text-sm font-semibold mb-2">Preview</h2>
        {!tailored && (
          <div className="text-sm text-slate-500 py-12 text-center">
            Click Tailor to generate a preview.
          </div>
        )}
        {tailored && (
          <div className="border border-slate-200 rounded overflow-hidden bg-slate-100">
            {rendering && (
              <div className="text-xs text-slate-500 p-2">Rendering preview…</div>
            )}
            {previewHtml && (
              <iframe
                title="Resume preview"
                srcDoc={previewHtml}
                className="w-full h-[800px] bg-white"
              />
            )}
          </div>
        )}
      </section>
    </div>
  );
}
