# Design: Trailhead planning agent

This document supports the Preconfigured-style take-home: **scope**, **threat model**, **failure modes**, and a credible **v2** roadmap.

## Goals

- **Assist** learners with **navigation and prioritization** on Salesforce Trailhead using natural-language intent.
- **Do not** automate quizzes, knowledge checks, or credential stuffing.
- **Separate concerns**: browser discovery (Playwright) vs. reasoning (LLM) vs. future Salesforce org work.

## Architecture

| Layer | Responsibility |
|--------|------------------|
| **CLI** | Args / env, exit codes, `--json` / `--log-json`, trace IDs |
| **Validation** | HTTPS + host allowlist + `/content/learn/` path |
| **Session** | Chromium; optional persistent profile (Google SSO) or password login |
| **Discovery** | Extract module/unit links; trail pages may require crawling module roots. Scroll rounds (`TRAILHEAD_DISCOVERY_SCROLL_ROUNDS`) merge lazy-loaded anchors; optional **pagination clicks** (`TRAILHEAD_DISCOVERY_PAGINATION_CLICKS`) on Load/Show more patterns; configurable **`TRAILHEAD_DISCOVERY_NAV_WAIT_UNTIL`**. `detect_discovery_blockers()` flags login / geo / error pages; degenerate scrapes (empty titles, duplicate-title noise) raise **`DiscoveryError`** with **`page_url` / `page_title`** in **`details`**. |
| **LLM agent** | **Pydantic**-validated ranking JSON (`llm_schemas.py`); optional **planner phase** + **repair pass** on schema/allowlist failure; optional **OpenAI strict JSON Schema**; **href allowlist** (no invented URLs). **LangGraph** (`ranking_graph.py`) is the **mandatory** orchestrator: **StateGraph** with conditional routing (prepare → planner → rank → repair? → finalize). |
| **`org_executor`** | Protocol + `NoopOrgExecutor` / **`CliOrgExecutor`** (`TRAILHEAD_ORG_EXECUTOR=cli`); YAML checklists in `config/org_checklists.yaml`; CLI: **`org doctor`**, **`org checklist`**, **`org prepare`**. Human-in-the-loop only. |

Data flow: `start_url` → Playwright collects `UnitRef` list → optional planner LLM notes → primary ranking LLM → validate with **Pydantic** → optional repair LLM → materialize ordered `UnitRef` → `RunPlan` (+ `trace_id`, `duration_ms` in JSON). Optionally **`plan --walk-ranked N`** / **`open-unit --visit-count N`** performs **navigation-only** `goto` to the first *N* ranked unit URLs (with page settle + optional scroll) in one recorded session so E2E video reflects LLM order. Logs include `pipeline_stage=*` and `e2e_walk_ranked` for observability.

## Threat model (high level)

| Risk | Mitigation |
|------|------------|
| **Secret leakage** | Keys only in `.env` / CI secrets; never logged; `.gitignore` includes `.env` |
| **Open redirect / SSRF** | `validate_start_url()` restricts host and path prefix |
| **Prompt injection from Trailhead** | Candidates are structured `title`/`href` only; system prompt forbids new URLs |
| **Academic dishonesty** | No auto-answers; documentation states intended use |
| **Dependency supply chain** | Pin minimum versions in `pyproject.toml`; CI runs tests |
| **Subprocess / `sf` injection** | Org alias and paths validated before `subprocess` argv lists; no shell=True |
| **`sf` missing or wrong org** | `org doctor` / `prepare` report clearly; exit code 2 via `OrgExecutorError` where applicable |

## Failure modes

| Failure | Behavior |
|---------|----------|
| **Trailhead DOM changes** | Discovery returns fewer links; tune waits (`TRAILHEAD_PAGE_SETTLE_MS`), **`TRAILHEAD_DISCOVERY_SCROLL_ROUNDS`**, **pagination clicks**, or selectors in YAML. Zero usable links or degenerate TOC → **`DiscoveryError`** with hints and **`details`** (no LLM call). |
| **SSO / MFA** | Password login may fail; use `trailhead-agent auth` + persistent profile |
| **LLM 429 / quota** | Retries (Tenacity) + mapped error with links to rate-limit docs |
| **Windows `SSLKEYLOGFILE` injection** | `sanitize_environment()` strips known-bad values |
| **Invalid LLM JSON** | `LLMProviderError` (Tenacity retries transport errors only); schema errors may trigger one **repair** completion; empty allowlisted ranking → discovery order |

## Observability

- **`trace_id`**: per CLI invocation (contextvar + JSON logs).
- **`duration_ms`**: wall time for `plan` browser + LLM segment.
- **E2E bundles**: When `TRAILHEAD_RECORD_VIDEO_DIR` is set, `plan` / `open-unit` write JSON next to `.webm` files (`e2e-plan-*.json`, `e2e-open-unit-*.json`, `*-latest.json`) with **`video_files`** = **this session’s** clips (each row has **`role`**: `primary` vs `session`), **`primary_video`**, **`video_files_other_in_dir`** for other clips in the same folder, and **`e2e-manifest.json`** appends each `plan` / `open-unit` / recorded **`org prepare`**. **`e2e-org-prepare-latest.json`** is written when **`org prepare --open-playground`** records video. By default, session `.webm` files are **renamed** from Playwright hashes to **`plan-primary.webm`**, **`open-unit-primary.webm`**, **`org-prepare.webm`** (disable: **`TRAILHEAD_E2E_FRIENDLY_VIDEO_NAMES=0`**). **`e2e-report.html`** (disable: **`TRAILHEAD_E2E_HTML_REPORT=0`**) is a self-contained **gallery**: embedded `<video>` previews, colored chips (plan / org / open-unit), manifest timeline, JSON links, and an **Org prepare** explainer panel fed by **`e2e-org-prepare-latest.json`** (executor, `playground_ready`, warnings, deploy — merged at end of `org prepare` after the browser closes). Restored multi-tab persistent profiles may still produce short sidecar `.webm` files when extra tabs are closed at session start.
- **`--log-json`**: one JSON object per line on stderr for ingestion.

## v2 roadmap (honest)

1. **`OrgExecutor` implementation** — `sf project deploy`, Tooling API, or guided browser inside the org.
2. **Checklist extraction** — optional second LLM pass on unit HTML → verified checklist (human-in-the-loop).
3. **Caching** — disk cache of discovery + LLM results keyed by `(start_url, intent_hash)` for CI cost control.
4. **Structured config** — Pydantic settings for all env (optional migration from raw `os.environ`).

## Tradeoffs (assignment narrative)

- **LLM vs. rules**: Intent-driven ranking scales better than YAML keyword lists but costs tokens and depends on vendor uptime.
- **Headless vs. headed**: Headless is CI-friendly; some sites and Google login need headed + persistent context.
- **Scope stop**: Full “complete Trailhead” would require org automation, legal review, and ongoing selector maintenance — out of scope for a 6-hour exercise.
