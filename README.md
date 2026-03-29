# Trailhead agent — LLM-driven planner + Playwright discovery

**Version:** 0.5.0 (see `pyproject.toml`).

This project uses **two layers**:

1. **Playwright** — Opens Trailhead, collects candidate links (module/unit URLs). Structural rules only (HTTPS, allowed host, `/content/learn/` paths).
2. **LLM agent** — Reads your **natural-language intent** and the candidate list, then **selects and orders** units. No YAML keyword policies.

It does **not** auto-submit quiz answers or bypass assessments.

## Assignment deliverables (Preconfigured-style)

| Deliverable | Where |
|-------------|--------|
| **Design / threat model / v2** | [`DESIGN.md`](DESIGN.md) |
| **Org + Playground** | [`org_executor.py`](src/trailhead_agent/org_executor.py), [`cli_org_executor.py`](src/trailhead_agent/cli_org_executor.py), [`org_commands.py`](src/trailhead_agent/org_commands.py), [`config/org_checklists.yaml`](config/org_checklists.yaml); roadmap: [`PLAN_ORG_EXECUTOR.md`](PLAN_ORG_EXECUTOR.md) |
| **CI (tests + lint + types)** | [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — Python 3.11 & 3.12, `pytest`, `ruff`, `mypy` |
| **Optional E2E** | [`.github/workflows/e2e.yml`](.github/workflows/e2e.yml) — manual `workflow_dispatch`; set secrets `GOOGLE_API_KEY`, `TRAILHEAD_START_URL`, `TRAILHEAD_INTENT` |
| **Container** | [`Dockerfile`](Dockerfile) + [`.dockerignore`](.dockerignore) — `docker build -t trailhead-agent .` then pass env at run time |
| **Golden tests** | `tests/fixtures/`, `test_golden_ranking.py`, `test_plan_json.py` |
| **Observability** | Per-run `trace_id`, `duration_ms` + `agent_version` on `plan --json`; `--log-json` adds `trace_id` / `llm_provider` on each log line |
| **429 / quota UX** | `llm_errors.raise_mapped_llm_error()` — actionable messages + doc links |

### Time log (replace with your real numbers)

| Phase | Minutes | Notes |
|-------|---------|--------|
| Research | *fill* | Trailhead DOM, Gemini/OpenAI constraints, Windows SSL env |
| Coding | *fill* | Agent, CLI, tests, CI, Docker |
| Documentation | *fill* | README, DESIGN.md |
| **Total** | *fill* | |

## Production / operations

| Topic | Detail |
|--------|--------|
| **Exit codes** | `0` success; `1` generic / no unit opened; `2` configuration, URL validation, or **org / `sf` integration** (`OrgExecutorError`); `3` LLM/API failure; `130` Ctrl+C |
| **Structured logs** | `--log-json` → one JSON object per line on stderr |
| **Machine output** | `plan --json` → single JSON document on stdout (INFO logs suppressed to reduce noise). The plan is an **ordered study queue**: each unit has `title`, `href`, and **`reason`** (short LLM rationale when the ranker returned one). It is not a full written syllabus—Trailhead content lives at each URL. |
| **Health** | `trailhead-agent doctor` (`--json`) checks version, LLM keys, **`sf` on PATH**, org executor type, and **`sf org display`** connectivity when `sf` exists (**never** prints secrets) |
| **Start URL safety** | `validate_start_url()` enforces `https`, `TRAILHEAD_ALLOWED_HOST`, and `/content/learn/` in the path |
| **LLM resilience** | Tenacity retries on rate limits / 5xx / connection errors (`LLM_MAX_RETRIES`, `LLM_RETRY_MIN_WAIT_S`, `LLM_RETRY_MAX_WAIT_S`) |
| **Ranking pipeline** | **Pydantic** contracts (`llm_schemas.py`); logs `pipeline_stage=` (`build_payload`, `planner`, `llm_primary`, `validate`, `llm_repair`, `materialize`). Env: **`LLM_PLANNER_PHASE=1`** (extra planner call), **`LLM_RANKING_REPAIR=0`** to disable repair, **`LLM_OPENAI_STRICT_SCHEMA=1`** (OpenAI-only strict `json_schema`) |
| **LangGraph orchestrator** | **Required.** Ranking always runs through **[LangGraph](https://github.com/langchain-ai/langgraph)** (`ranking_graph.py`): prepare → planner → rank → conditional repair → finalize. Installed with the base package (`langgraph`, `langchain-core` in `pyproject.toml`). |
| **E2E artifacts** | **`plan --save-e2e`** or **`plan --artifacts-dir PATH`** saves Playwright **`.webm`** + **`e2e-plan-<trace_id>.json`** / **`e2e-plan-latest.json`** (same as stdout JSON plus `saved_at_utc`, `video_files`). **`open-unit`** supports the same flags. Env alternative: **`TRAILHEAD_RECORD_VIDEO_DIR`**. **`plan --walk-ranked N`** (and **`open-unit --visit-count N`**) navigates the first *N* ranked unit URLs in one session after ranking so recordings show clear URL-by-URL progression (navigation only). Plan JSON may include **`walk_ranked_visits`**. One-shot scripts default to walking a few units: **`scripts/run-e2e-plan.ps1`** / **`run-e2e-plan.sh`** (override with `-WalkRanked 0` or **`WALK_RANKED=0`**). This repo may include **sample runs under `artifacts/`** for demos; for your own work, prefer not committing large or repeated recordings (re-add `artifacts/` to `.gitignore` locally if needed). |
| **Gemini SDK** | Prefer `pip install -e ".[gemini]"` (**google-genai**). Legacy `google-generativeai` is optional: `pip install -e ".[legacy-gemini]"` |
| **Tests / types** | `pip install -e ".[dev]"` then `pytest` and `mypy src/trailhead_agent tests` |

## What you configure

| Source | Purpose |
|--------|---------|
| **`.env`** | LLM keys, `TRAILHEAD_START_URL`, `TRAILHEAD_INTENT`, tuning, optional **org / `sf`** settings (`TRAILHEAD_ORG_EXECUTOR`, `TRAILHEAD_SF_ORG_ALIAS`, …) — see `.env.example` |
| **`config/default.yaml`** | Browser + login **selectors** only |

Optional: **`TRAILHEAD_AGENT_PROMPT_FILE`** for a custom system prompt.

## Setup (Windows)

```powershell
cd $env:USERPROFILE\Downloads\preconfigured-trailhead-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[gemini]"
playwright install chromium
copy .env.example .env
```

Fill `.env` with **`TRAILHEAD_START_URL`**, **`TRAILHEAD_INTENT`**, and your LLM credentials (`OPENAI_API_KEY` or `LLM_PROVIDER=gemini` + `GOOGLE_API_KEY`, etc.).

### Sign-in (Google OAuth)

Use **`TRAILHEAD_BROWSER_USER_DATA_DIR`** and **`trailhead-agent auth`** once; see `.env.example`.

## Commands

The CLI uses **subcommands**: `doctor`, `plan`, `open-unit`, `auth`, and `org` (with `org doctor` / `org checklist` / `org prepare`). Global options: **`--log-json`**, **`--log-level`**, **`-v`** / **`--verbose`** (before the subcommand). Examples:

```powershell
trailhead-agent doctor
trailhead-agent doctor --json

trailhead-agent plan --start-url "https://trailhead.salesforce.com/content/learn/modules/apex_database" --intent "Prioritize hands-on and coding; exclude quizzes and exams."

trailhead-agent plan --json --start-url "..." --intent "..."   # stdout = JSON only

trailhead-agent open-unit --start-url "..." --intent "..."

trailhead-agent plan --artifacts-dir ./artifacts/demo --walk-ranked 5 --start-url "..." --intent "..."

trailhead-agent open-unit --visit-count 3 --start-url "..." --intent "..."

trailhead-agent auth
python -m trailhead_agent doctor
```

### Org / Salesforce CLI (human-in-the-loop)

Uses static checklists in [`config/org_checklists.yaml`](config/org_checklists.yaml). Set **`TRAILHEAD_ORG_EXECUTOR=cli`** for `sf org display`-backed readiness checks and optional **`sf project deploy`**. See [`.env.example`](.env.example).

```powershell
trailhead-agent org doctor
trailhead-agent org doctor --json --sf-org-alias myScratch1

trailhead-agent org checklist --plan-json .\artifacts\run-2026-03-28_20-20-38\e2e-plan-latest.json --json
trailhead-agent org checklist --unit-href "https://trailhead.salesforce.com/content/learn/modules/apex_database/apex_database_intro"

trailhead-agent org prepare --json
trailhead-agent org prepare --open-playground --start-url "https://trailhead.salesforce.com/content/learn/modules/apex_database"
# Deploy (explicit): requires a real SFDX project directory
trailhead-agent org prepare --deploy --project-dir C:\path\to\sfdx-project --sf-org-alias myScratch1
```

## Architecture

1. **Session** — Chromium; optional persistent profile or password login.
2. **Discovery** — Collects module/unit links (trail → module roots → units when needed).
3. **`llm_agent`** — OpenAI (default), **Gemini** (`google-genai`), or Anthropic; JSON-only parsing with href allowlisting.
4. **Runner** — `plan` / `open-unit`; URL validation before navigation.
5. **`org_executor`** — **`NoopOrgExecutor`** by default; **`CliOrgExecutor`** when **`TRAILHEAD_ORG_EXECUTOR=cli`** (`sf org display`, YAML checklists, optional **`sf project deploy`**). CLI: **`trailhead-agent org …`**. See [`DESIGN.md`](DESIGN.md) and [`PLAN_ORG_EXECUTOR.md`](PLAN_ORG_EXECUTOR.md).

## Docker

```bash
docker build -t trailhead-agent .
docker run --rm \
  -e GOOGLE_API_KEY -e LLM_PROVIDER=gemini \
  -e TRAILHEAD_START_URL -e TRAILHEAD_INTENT \
  trailhead-agent plan --json
```

(`ENTRYPOINT` is `trailhead-agent`; **`plan`** reads **`TRAILHEAD_START_URL`** / **`TRAILHEAD_INTENT`** from the environment if you omit **`--start-url`** / **`--intent`**. Default image **`CMD`** is **`doctor --json`**.)

Override entrypoint if you need `auth` (headed browser usually requires a local display / X11; use host Chrome + `.env` instead for OAuth).

## Troubleshooting (Gemini / Windows)

- **Playwright `.webm` looks like one static Trailhead screen** — That is expected for a **module** start URL: the agent loads the module page, **reads link elements in the DOM** (no clicking), then calls the LLM over the network (nothing visible in the browser). The LLM work is not shown in the video. For clearer **progression after ranking**, use **`plan --walk-ranked N`** or **`open-unit --visit-count N`** with **`--artifacts-dir`** so the browser visits the first *N* ranked unit URLs in order. Other options: a **trail** start URL, **`TRAILHEAD_AGENT_HEADLESS=0`**, **`TRAILHEAD_PAGE_SETTLE_MS`**, and the pre-LLM **smooth scroll** (disable with **`TRAILHEAD_VIDEO_SCROLL_DEMO=0`**).
- **`Permission denied` / `nllMonFltProxy` / `SSLKEYLOGFILE`** — Some security software sets `SSLKEYLOGFILE` to an invalid path. This app clears known-bad values after `load_dotenv()`. You can also remove `SSLKEYLOGFILE` from **User environment variables** in Windows.
- **`403 PERMISSION_DENIED` / Generative Language API disabled** — Enable the API for the Google Cloud project tied to your key: open the link in the error, or use a key from [Google AI Studio](https://aistudio.google.com/apikey) (often simpler).

## Compliance

Use a **personal** Trailhead account, respect Salesforce Terms of Service, and treat this as **planning + navigation**, not automated cheating.
