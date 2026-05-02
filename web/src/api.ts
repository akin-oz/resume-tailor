import type {
  RenderRequest,
  TailorRequest,
  TailorResult,
  TemplateMeta,
} from "./types";

// Same-origin in dev (Vite proxy) by default. In production builds, set
// VITE_API_BASE to the deployed backend URL — the frontend lives on
// Cloudflare while the backend (with WeasyPrint native libs) lives elsewhere.
const BASE = import.meta.env.VITE_API_BASE ?? "";

async function jsonOrThrow<T>(r: Response): Promise<T> {
  if (!r.ok) {
    const detail = await r.text().catch(() => "");
    throw new Error(`HTTP ${r.status}: ${detail || r.statusText}`);
  }
  return (await r.json()) as T;
}

export async function fetchTemplates(): Promise<TemplateMeta[]> {
  return jsonOrThrow(await fetch(`${BASE}/api/templates`));
}

export async function postTailor(req: TailorRequest): Promise<TailorResult> {
  return jsonOrThrow(
    await fetch(`${BASE}/api/tailor`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }),
  );
}

export async function postRenderHtml(req: RenderRequest): Promise<string> {
  const r = await fetch(`${BASE}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...req, format: "html" }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.text();
}

export async function postRenderPdf(req: RenderRequest): Promise<Blob> {
  const r = await fetch(`${BASE}/api/render`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...req, format: "pdf" }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}: ${await r.text()}`);
  return r.blob();
}
