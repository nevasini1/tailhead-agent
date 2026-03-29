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
| **Discovery** | Extract module/unit links; trail pages may require crawling module roots. Scroll rounds (`TRAILHEAD_DISCOVERY_SCROLL_ROUNDS`) merge lazy-loaded anchors. `detect_discovery_blockers()` flags login / geo / error pages; `DiscoveryError` (exit 2) if zero candidates after collection. |
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
| **Trailhead DOM changes** | Discovery returns fewer links; tune waits (`TRAILHEAD_PAGE_SETTLE_MS`), **`TRAILHEAD_DISCOVERY_SCROLL_ROUNDS`**, or selectors in YAML. Zero usable links → **`DiscoveryError`** with hints (no LLM call). |
| **SSO / MFA** | Password login may fail; use `trailhead-agent auth` + persistent profile |
| **LLM 429 / quota** | Retries (Tenacity) + mapped error with links to rate-limit docs |
| **Windows `SSLKEYLOGFILE` injection** | `sanitize_environment()` strips known-bad values |
| **Invalid LLM JSON** | `LLMProviderError` (Tenacity retries transport errors only); schema errors may trigger one **repair** completion; empty allowlisted ranking → discovery order |

## Observability

- **`trace_id`**: per CLI invocation (contextvar + JSON logs).
- **`duration_ms`**: wall time for `plan` browser + LLM segment.
- **E2E bundles**: When `TRAILHEAD_RECORD_VIDEO_DIR` is set, `plan` / `open-unit` write JSON next to `.webm` files (`e2e-plan-*.json`, `e2e-open-unit-*.json`, `*-latest.json`) including **`primary_video`**, **`e2e_session_videos`**, and append to **`e2e-manifest.json`** (chronological clips: plan, open-unit, `org prepare` when recording). Persistent-profile recording uses a **single tab** so one session typically yields **one** `.webm`.
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
