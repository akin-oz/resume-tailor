# CLAUDE.md

Project context for Claude Code. Loaded automatically at session start.

This is a long-form file by design — the user picked "(c) full design philosophy" when setting up agent boundaries. If you're a future contributor reading this, the rules here are non-negotiable; the rationales explain *why*.

---

## Mission

Resume Tailor takes a candidate's verified facts plus a job description and produces a tailored, ATS-friendly PDF resume.

The differentiator from "ask ChatGPT to write me a resume" is **provenance**:

> An LLM with no constraints will hallucinate metrics and titles. Resume Tailor gives the model only the bullets the user wrote themselves, and restricts it to selecting and ordering from that pool. Their facts stay their facts.

This thesis is the technical heart of the project. Every architectural choice should make sense in light of it.

## Anti-hallucination contract

The model never returns free text where a fact lives. It returns **IDs** the user authored.

- Each `Story` (bullet) has a stable opaque `id`. The frontend mints it; the backend validates it.
- The AI receives `{id, text, keywords}` per bullet and must echo back IDs only.
- Server-side validators (`api/app/domain/tailor_ai.py:validate_experiences`) drop any ID not in the input pool. The model cannot smuggle an invented bullet through.
- The profile paragraph is constrained too: 45–75 words, banned-phrase list, no em dashes, vocabulary anchored to the user's `profile_seed`. Output failing those checks falls back to a clean truncation of the seed — never to an unverified rewrite.
- Skills returned by the model are filtered to the input skill pool with the same dedup pattern.
- A second-stage **resume parser** (`api/app/domain/parse.py`) is pure-Python heuristics, no LLM. The user reviews + edits before tailoring, so the bullet-pool contract holds even when starting from a PDF.

When in doubt, ask: *"Could this code path let the model introduce a fact the user didn't write?"* If yes, add a validator.

## Tech stack — non-negotiable

| Layer | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, WeasyPrint, OpenAI SDK |
| Frontend | React 18 + Vite + TypeScript (strict) + Tailwind. No UI-kit dependency; shadcn-style primitives only. |
| Build / deps | `uv` for Python, `npm` for the frontend |
| Testing | `pytest` + `httpx` (backend), `vitest` + RTL (frontend, deferred), one Playwright e2e for the golden path (deferred) |
| Lint / typecheck | `ruff` + `mypy --strict` (backend), `eslint` + `prettier` + `tsc` (frontend) |

Every additional dependency must be **justified in the README**. Default to standard library / platform features. Don't pull in TanStack Query just because everyone does — pull it in when caching is an actual problem.

## Domain model conventions

- All Pydantic models inherit from `_Strict`: `extra="forbid"`, `str_strip_whitespace=True`, `alias_generator=to_camel`, `populate_by_name=True`.
- **Wire format is camelCase** (TS-friendly, OpenAPI-friendly). Python attributes stay snake_case. Routes set `response_model_by_alias=True`.
- Errors are RFC 7807 `application/problem+json`. OpenAI transient failures map to **503** with `Retry-After`, never a generic 500.
- Partial dates (`YYYY` or `YYYY-MM`) are common on resumes; `date` is too strict. Use the `PartialDate` alias.
- IDs are opaque strings, regex-constrained `^[A-Za-z0-9_.\-]+$`. Frontend mints UUID-based IDs (e.g. `exp-${crypto.randomUUID()}`) — length-based IDs collide after deletion.

## Slice discipline

**Each PR is one vertical slice, ≤400 LOC excluding lockfiles, with tests.**

The Stop hook warns when the staged diff exceeds 400 LOC.

### Vertical means by feature, not by layer

This is the trap I keep falling into. A vertical slice is a thin column through *every* layer — domain + route + tests + UI — that delivers **one user-visible capability**. Each slice ships independently and is demoable on its own.

Reference: [Milan Jovanović — Vertical Slice Architecture](https://www.milanjovanovic.tech/blog/vertical-slice-architecture).

**Counter-example (the one I made on PR #2):** the resume parser was 1023 LOC, so I split it into:

- #4: parser domain only (`parse.py` + types + tests)
- #5: HTTP route on top of #4
- #6: UI that calls the route

That's *horizontal* slicing — split by layer. None of those PRs ship alone:

- #4 had no callers
- #5 had no UI
- #6 returned 404 in production

User-visible value only appeared when all three merged. Each "slice" was actually a layer in disguise.

**The right split** would have been by feature subset:

- A. Upload PDF → contact card pre-fills (`parse_contact` only, route, UI for that one card). Demoable: a user can upload a PDF and see their name + email show up.
- B. Add experience extraction. Same upload UI, now also fills experience cards.
- C. Add education + skills + summary. Completes the feature.

Each is end-to-end. Each ~300 LOC. Each merged into production gives the user something new to try.

### When a feature is genuinely indivisible

Sometimes a single function or pipeline IS the substance of the slice (the parser's `parse.py` is 444 LOC of one cohesive flow with no natural seam to extract a "smaller parser" from). When that happens:

1. Don't fake-split it by layer — produces unshippable intermediates
2. Don't extract dead-code "subroutines" just to make file sizes smaller
3. Call out the size exception in the PR description with the rationale

The 400-LOC budget is a forcing function for *feature decomposition*, not layer decomposition. When feature decomposition is genuinely impossible, override the budget openly rather than pretending you split.

### Other drift to watch for

- **Coupled changes** — sometimes a model change forces a route + test update. That's fine. But "while I'm in there" cleanup is what bloats slices. Cut it.

When you forecast > 400 LOC: **propose a split before coding.** If you're already mid-slice and growing, stop and split. Use the `slice-splitter` subagent if it helps.

Past offenders for reference (don't add to this list):

| Slice | LOC | Notes |
|---|---|---|
| Domain model | 250 | ✓ |
| Stub tailor + FastAPI app + tests | 785 | bundled too much |
| WeasyPrint + 2 templates + previews | 668 | should have been two slices |
| OpenAI tailor | 642 | acceptable; central to the thesis |
| Frontend skeleton + WeasyPrint swap | 785 | combined two distinct things |
| Resume parser (PR #2 → #4/#5/#6) | 1023 → 716 + 110 + 198 | **wrong both ways:** too big as one PR; horizontally sliced when "rescued" |

## Workflow

**Branch per feature.** Refuse to commit on `main` (the PreToolUse hook enforces this). Create `claude/<feature-name>` from main.

**Plan in writing before coding.** Three sentences is enough:
- What problem.
- The simplest end-to-end path.
- What's deferred.

For exploratory questions ("how should we approach X?"), respond in 2-3 sentences with a recommendation and the main trade-off — *don't* implement until the user agrees.

**PRs ship as drafts** until CI is green. Mark ready-for-review only after `make check` passes locally and CI confirms.

**Commit messages:** subject line ≤72 chars, imperative mood. Body explains the *why*, not the *what* (the diff already shows the what). Three sentences is usually enough; multi-paragraph epics are over-explaining. Past habit: long bullet-list commits — those are fine for the rare big slice but shouldn't become the default.

**CodeRabbit triage:** classify each finding as take/skip/ask, with rationale. Don't rubber-stamp. Skip security theater (e.g. pinning every action to a SHA on a personal portfolio repo). Take real bugs (path traversal, race conditions, hallucination guards).

## Quality gates

Local quality bar before commit:

```bash
make check
# = ruff check + ruff format --check + mypy --strict + pytest
```

The pre-commit hook runs this automatically when `api/` or `web/` files are staged. If it fails, fix it before retrying — don't `--no-verify`.

Frontend:

```bash
cd web && npm run build   # tsc -b && vite build
```

Tests are about behavior, not coverage theater:
- AI-output validation (unknown IDs dropped, banned phrases rejected, word count enforced)
- Template rendering produces no unresolved `{{placeholders}}`
- E2E generates a PDF and asserts it has content
- Parser's section/contact/experience/skills heuristics on representative input

## Deployment

**Live URLs:**
- Frontend: `https://resume-tailor-web.akinoztorun.workers.dev/`
- Backend: `https://resume-tailor-api-6vbv.onrender.com`

**Backend** → Render free tier. `Dockerfile` at the root, `render.yaml` declares the service. ~30s cold start after 15 min idle; acceptable for a portfolio demo.

**Frontend** → Cloudflare Workers Static Assets (the modern pattern that supersedes Pages). `web/wrangler.jsonc` pins `account_id` so the deploy works with a minimal-scope token. `make deploy-web` builds + uploads.

**Don't try to put Cloud Run back.** That path was abandoned after a multi-hour fight with Workspace org policies, IPv6 routing, and `*.run.app` edge weirdness. Render is good enough.

For the deploy walkthrough — including the gotchas (Cloudflare 525 for proxied custom domains, GCP IAM for Cloud Build, `*.run.app` routing flap) — invoke the **deploy-walker** subagent. It has the context pre-loaded so the main session doesn't re-litigate it.

## Out of scope (deliberately)

Each of these has been considered and explicitly cut for v1. **Don't add without asking.**

- Accounts / authentication
- Database / persistence
- PDF watermarking
- Multi-language
- Mobile app
- Paid tier
- ChatGPT-style chat UI
- "Improve my bullet" rewriting (selection-only)
- Scraping JDs from URLs
- Word/DOCX export
- OCR for scanned PDFs (the parser surfaces "PDF may be scanned" instead)

If the user asks for one of these, push back: "this was deliberately cut — should we revisit?"

## Drift patterns (to avoid)

Things I've noticed myself doing wrong in past sessions:

- **Over-budget slices.** See the table above. Use the `slice-splitter` subagent before committing if the diff is big.
- **Horizontal slicing dressed up as vertical.** When a feature is too big, the wrong fix is to split it into "domain" / "route" / "UI" PRs — none of those ship alone. The right fix is to split by *feature subset* (parse contact only → parse experiences → parse education) so each slice delivers something demoable. See the parser PRs (#2 → #4/#5/#6) for the antipattern in production.
- **Implementing before confirming the plan.** When the user asks "how should we approach X?", I jump to code. Stop, propose 2-3 sentences, wait for greenlight.
- **Ceremonial commit messages.** Three sentences usually beat eleven bullet points. Save the long form for the rare structurally significant change.
- **Not pushing back.** When a user request conflicts with a project principle (e.g. "use an LLM for the parser" vs the no-LLM-without-confirmation philosophy), surface the tension first. Ship only after they confirm.
- **CodeRabbit rubber-stamping.** Triage actively. Skipping ~20% of findings is the right answer; taking 100% is sloppy.
- **Long output when short would do.** This applies to chat replies too, not just commits.

## Subagent quick reference

Spawn via the Agent tool with `subagent_type`:

- `slice-splitter` — pre-commit, when diff > 400 LOC: returns a 2-/3-way split proposal
- `review-triager` — when CodeRabbit posts: returns per-finding take/skip/ask
- `deploy-walker` — for deploy walkthroughs (Render, Cloudflare); has the project's known-gotchas pre-loaded
- `honest-reviewer` — fresh code review with no awareness of recent decisions; surfaces things I'd otherwise defend

The first three improve speed; the last one is the most useful for catching genuine issues.

## Useful commands

```bash
# Local dev
make install            # uv sync + npm install
make dev                # run api (8000) + web (5173) in parallel
make check              # lint + typecheck + tests

# Backend
make api                # uvicorn dev server
make typecheck          # mypy --strict on api/app
make test               # pytest

# Frontend
cd web && npm run dev   # vite dev server
cd web && npm run build # production build
cd web && npm run typecheck

# Deploy
make build-web                                    # build frontend dist
CLOUDFLARE_API_TOKEN=cf_... make deploy-web       # push to Cloudflare
make previews                                     # regenerate template thumbnails
```
