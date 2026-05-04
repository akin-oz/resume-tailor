# Evals

Tests that check the project's *thesis*, not just its code.

The unit tests in [`api/tests/`](../api/tests/) verify that individual
validators behave correctly in isolation. The evals here verify that the
end-to-end **bullet-pool contract** — "the model can never introduce a
fact the user didn't write" — actually holds on the public worked example
in [`examples/`](../examples/).

These are the regression tests for the README's headline claim.

## What's checked

[`check_provenance.py`](check_provenance.py) audits a `TailorResult` JSON
against the `ResumeInput` JSON it was tailored from:

| Check | What it asserts |
|---|---|
| **Story provenance** | every `storyId` in the output exists in the input pool for its `experienceId`. The model cannot smuggle in invented bullets. |
| **Skill provenance** | every output skill exists (case-insensitively) in the input skill list. |
| **Profile guardrails** | word count is in `[45, 75]`; no em-dash (`—`) or `--`; no banned phrases (`thrilled`, `passionate`, `cutting-edge`, `leverage`, `synergy`, …). |
| **Archetype** | `archetypeUsed` is one of the documented values (`backend`, `frontend`, `fullstack`, `data`, `ml`, `platform`, `mobile`, `generalist`). |
| **Drift visibility** | `droppedStoryIds` and `profileFallbackUsed` are surfaced in the report — silent fallbacks would otherwise hide regressions. |

The script imports nothing from `app.*` on purpose: it's an
**external** auditor of the contract, so a regression in the production
validators that breaks the contract on the worked example will be caught
here even if the internal unit tests still pass.

## Running

```bash
# CLI report (committed worked example).
python3 evals/check_provenance.py

# Or against your own files.
python3 evals/check_provenance.py \
  --resume path/to/resume.json \
  --tailored path/to/tailored.json

# As a pytest target (also runs in `make check`).
uv run pytest evals/
```

The pytest wrapper [`test_check_provenance.py`](test_check_provenance.py)
runs each check function twice: once on the committed worked example
(asserts pass), once on a deliberately-broken copy (asserts the auditor
catches the failure). The second layer is what proves the auditor itself
isn't a no-op.

## Why `check_provenance.py` duplicates constants from production

The banned-phrase list, profile word-count bounds, and allowed archetypes
are repeated in this script (rather than imported from `app.*`). That
means a deliberate change to the production validators must also update
the eval — surfacing the change in code review rather than silently
moving the goalposts. If the eval drifts, the test fails and the
contradiction is visible.

## Scope and limits

These evals only check what's mechanically verifiable: ID membership,
skill membership, word counts, banned strings, allowed enums. They
**don't** judge whether the bullets are well-chosen — that's a prompt /
ranking quality question and lives elsewhere (the LLM-vs-unconstrained
diff harness is a future addition; would require an `OPENAI_API_KEY`
and is gated to manual runs to avoid CI cost).

What the current evals *do* prove: when the worked example is rerun, no
silent regression in the validators can let an invented ID, an
unauthorised skill, or a banned-phrase profile slip through unnoticed.
That is the floor the rest of the project's claims rest on.
