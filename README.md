# Resume Tailor

Type your real experience once. Paste any JD. Pick a template. Get a clean, truthful, tailored PDF in ~10 seconds.

> An LLM with no constraints will hallucinate metrics and titles. Resume Tailor gives the model **only the bullets you wrote yourself**, and restricts it to selecting and ordering from that pool. Your facts stay your facts.

---

## Run in 60 seconds

```bash
git clone https://github.com/akin-oz/resume-tailor.git
cd resume-tailor
make install   # uv sync + npm install
make dev       # runs api (8000) and web (5173) in parallel
# → web:  http://localhost:5173
# → api:  http://localhost:8000/docs
```

No API key required. Without `OPENAI_API_KEY`, the tailor runs in **deterministic stub mode**: each bullet you tag with keywords (`"ownership"`, `"product management"`, `"mentoring"`, …) is scored against the JD by case-insensitive overlap, and the top-N per role are picked. Skills get the same treatment. The frontend is fully usable; tests run green.

With a key, the same endpoint dispatches to OpenAI under the strict bullet-pool contract: the model returns IDs from your bullet pool, gets validated server-side (unknown IDs dropped, profile checked against banned phrases / em-dashes / 45–75 word window — bad output falls back to a clean `profile_seed` truncation, never to a hallucinated profile).

With a key:

```bash
export OPENAI_API_KEY=sk-...
make dev
```

---

## Architecture

```text
api/           FastAPI + Pydantic v2 + Playwright
  app/
    domain/   Pure functions: tailor.py, render.py, archetype.py
    routers/  Thin HTTP layer
    main.py
  tests/
web/           React 18 + Vite + TS (strict) + Tailwind + TanStack Query
  src/
templates/     Folder-per-template. Add a folder, no backend code changes.
  modern/     {template.html.j2, style.css, meta.json, preview.png}
  classic/
  compact/
prompts/       tailor_system.md — versioned, reviewable
scripts/       build_previews.py (Playwright screenshots, runs in CI)
Makefile       make dev | test | lint | typecheck
```

Type safety end-to-end: Pydantic models → OpenAPI schema → TypeScript types via `openapi-typescript`. Zod re-validates at the network boundary on the frontend. No `any`.

---

## Design notes

- **Bullet pool with ID validation.** The model receives stories as `{id, text, keywords}` and must return only IDs. Unknown IDs are dropped server-side with a log line — the model cannot smuggle in invented bullets.
- **User-tagged keywords drive ranking.** Each bullet carries free-form keyword tags written by the user. Stub mode uses keyword/JD overlap directly; AI mode passes them as scoring hints. No fixed taxonomy — your resume, your vocabulary.
- **Profile paragraph guardrails.** 45–75 words, banned-phrase list (`thrilled`, `passionate`, `cutting-edge`, `leverage`, …), no em dashes, vocabulary constrained to the user's `profileSeed` + stories. Failing output falls back to a clean truncation of `profileSeed`.
- **Archetype detection.** Lightweight keyword heuristic runs first; the model gets the detected archetype as context. The user can override via the UI.
- **Stub mode.** No `OPENAI_API_KEY` → the same `TailorResult` shape comes from a deterministic function. Tests are hermetic; demos work offline.
- **Pure core, I/O at the edge.** `domain/tailor.py` and `domain/render.py` take and return data. Routers are thin. AI calls and Playwright live behind interfaces.
- **Single Playwright browser per worker.** Reused across requests; PDF render <2s warm.

---

## Why FastAPI + React (the trade-offs)

FastAPI gives us Pydantic v2 (the same domain types we'd want for validation, serialization, and OpenAPI) for free. The cost is a two-language repo. For a portfolio piece focused on type safety and a clean domain model, that cost buys more than a JS-only stack would. Next.js with server actions would collapse the layers, but at the cost of leaning on framework magic for the very boundary we want to make explicit.

---

## API

| Method | Path                                  | Description                                                         |
| ------ | ------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/api/templates`                      | List templates with preview URLs                                    |
| GET    | `/api/templates/{id}/preview`         | Template preview PNG (404 until `make previews` runs)               |
| POST   | `/api/tailor`                         | Validated `TailorResult` (3–8s with AI; <100ms in stub mode)        |
| POST   | `/api/render`                         | `text/html` or `application/pdf` (~200–500ms via WeasyPrint)        |
| GET    | `/healthz`                            | `{ status, pdf, openai }`                                           |

PDF rendering uses **WeasyPrint** — a Python library, no headless browser. Resumes are static paged content (no JS, simple CSS), exactly its sweet spot. WeasyPrint needs Cairo, Pango, and font libs at runtime; on Debian/Ubuntu install with `apt install libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libfontconfig1 fonts-liberation`. The Dockerfile bakes them in.

Errors are RFC 7807 `application/problem+json`. OpenAI `RateLimitError` / `APIConnectionError` / timeouts map to **503** with a `retryAfter` hint, not a generic 500.

---

## Adding a template

Drop a folder under `templates/<id>/` containing `template.html.j2`, `style.css`, and `meta.json`. Run `scripts/build_previews.py`. No backend code changes required.

---

## Deploy

Two pieces, two providers — decoupled by the camelCase JSON contract.

### Backend → Fly.io

WeasyPrint needs Cairo + Pango at runtime, which rules out Cloudflare Workers / Vercel / Lambda. Fly is the lightest deploy that fits.

```bash
fly launch --no-deploy                                  # claims name + region
fly secrets set CORS_ORIGINS=https://<your-web-host>    # comma-separated list
fly secrets set OPENAI_API_KEY=sk-...                   # optional; stub mode runs without
fly deploy
```

Defaults to `min_machines_running = 0` (scale-to-zero): free when idle, ~1-3s wake on the first request. Bump to 1 for instant response. The Dockerfile is a two-stage build, ~250MB final.

### Frontend → Cloudflare Workers (Static Assets)

The new `assets`-only deploy pattern that supersedes Pages for SPAs. Single command — Wrangler uploads `dist/` to the global edge.

```bash
# Set this so the production bundle hardcodes the backend URL:
echo "VITE_API_BASE=https://<your-fly-app>.fly.dev" > web/.env.production

CLOUDFLARE_API_TOKEN=cf_... make deploy-web
```

The token needs **Workers Scripts: Edit** permission on the account (create at `dash.cloudflare.com/profile/api-tokens` → "Edit Cloudflare Workers" template).

After both are deployed, double-check `CORS_ORIGINS` on the backend matches the Workers URL exactly (`https://resume-tailor-web.<account>.workers.dev`).

> **Why not Vercel/Render/Lambda?** Vercel and AWS Lambda cap deploy size at 50MB — Chromium alone (with Playwright) was 150MB+; even the WeasyPrint stack with native libs is tight. Render's free web service spins down for 15 min, killing the <2s render promise. Fly's auto-stop machines sleep but wake fast.

---

## Out of scope (deliberately)

No accounts. No database. No Word/DOCX export. No scraping JDs from URLs. No "improve my bullet" rewriting. No chat UI. No multi-language. Each was considered and cut.

---

## License

MIT
