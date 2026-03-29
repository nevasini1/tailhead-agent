# Trailhead agent — LLM-driven planner + Playwright discovery

**Version:** 0.5.1 (see `pyproject.toml`).

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
| **Documentation (PDF)** | **Source:** [`docs/trailhead-agent-project-report.html`](docs/trailhead-agent-project-report.html), [`docs/trailhead-agent-engineering-reference.html`](docs/trailhead-agent-engineering-reference.html) — open in browser, **Ctrl+P → Save as PDF**. **Prebuilt PDFs:** [`docs/trailhead-agent-project-report.pdf`](docs/trailhead-agent-project-report.pdf), [`docs/trailhead-agent-engineering-reference.pdf`](docs/trailhead-agent-engineering-reference.pdf) (generated via Edge; if a viewer shows blank PDFs, use the HTML). Regenerate: [`docs/HOW_TO_SAVE_PDF.md`](docs/HOW_TO_SAVE_PDF.md) or `powershell -File scripts\print_docs_to_pdf.ps1` |
| **PDF (optional fpdf2)** | `pip install -e ".[docs]"` then `python scripts/generate_*_pdf.py` → writes **`docs/fpdf-output/`** (does not overwrite main **`docs/*.pdf`**). fpdf2 can look blank in some viewers; prefer HTML + print or `print_docs_to_pdf.ps1` |
| **Browser agent primitives** | [`browser_agent_primitives.py`](src/trailhead_agent/browser_agent_primitives.py) — Playwright timeout defaults, locator-based shell wait, human-varied recording scrolls; optional **`TRAILHEAD_CHROMIUM_EXTRA_ARGS`** |
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
| **Exit codes** | `0` success; `1` generic / no unit opened; `2` configuration, URL validation, **discovery failure** (`DiscoveryError`: login wall, no unit links, trail layout), or **org / `sf` integration** (`OrgExecutorError`); `3` LLM/API failure; `130` Ctrl+C |
| **Structured logs** | `--log-json` → one JSON object per line on stderr |
| **Machine output** | `plan --json` → single JSON document on stdout (INFO logs suppressed to reduce noise). The plan is an **ordered study queue**: each unit has `title`, `href`, and **`reason`** (short LLM rationale when the ranker returned one). It is not a full written syllabus—Trailhead content lives at each URL. |
| **Health** | `trailhead-agent doctor` (`--json`) checks version, LLM keys, **`sf` on PATH**, org executor type, and **`sf org display`** connectivity when `sf` exists (**never** prints secrets) |
| **Start URL safety** | `validate_start_url()` enforces `https`, `TRAILHEAD_ALLOWED_HOST`, and `/content/learn/` in the path |
| **LLM resilience** | Tenacity retries on rate limits / 5xx / connection errors (`LLM_MAX_RETRIES`, `LLM_RETRY_MIN_WAIT_S`, `LLM_RETRY_MAX_WAIT_S`) |
| **Ranking pipeline** | **Pydantic** contracts (`llm_schemas.py`); logs `pipeline_stage=` (`build_payload`, `planner`, `llm_primary`, `validate`, `llm_repair`, `materialize`). Env: **`LLM_PLANNER_PHASE=1`** (extra planner call), **`LLM_RANKING_REPAIR=0`** to disable repair, **`LLM_OPENAI_STRICT_SCHEMA=1`** (OpenAI-only strict `json_schema`) |
| **LangGraph orchestrator** | **Required.** Ranking always runs through **[LangGraph](https://github.com/langchain-ai/langgraph)** (`ranking_graph.py`): prepare → planner → rank → conditional repair → finalize. Installed with the base package (`langgraph`, `langchain-core` in `pyproject.toml`). |
| **E2E artifacts** | **`plan --save-e2e`** or **`plan --artifacts-dir PATH`** saves Playwright **`.webm`** + **`e2e-plan-<trace_id>.json`** / **`e2e-plan-latest.json`**. **`video_files`** lists **only this run’s** session clips (each row: `name`, `size_bytes`, `mtime_utc`, **`role`** `primary` \| `session`); **`primary_video`** names the main clip. By default, hash-named `.webm` files are **renamed** to **`plan-primary.webm`**, **`open-unit-primary.webm`**, **`org-prepare.webm`** (sidecars: **`plan-session-01.webm`**, …); disable with **`TRAILHEAD_E2E_FRIENDLY_VIDEO_NAMES=0`**. Open **`e2e-report.html`** in the same folder for a compact **gallery** (inline videos, manifest, JSON links). Disable HTML with **`TRAILHEAD_E2E_HTML_REPORT=0`**. **`video_files_other_in_dir`** lists other `.webm` files in the folder. **`e2e-manifest.json`** appends **`plan`**, **`open-unit`**, and recorded **`org prepare --open-playground`**; **`e2e-org-prepare-latest.json`** summarizes the org browser clip. Env: **`TRAILHEAD_RECORD_VIDEO_DIR`**. **Recording demo browser:** default headed + **`slow_mo`** when recording — **`TRAILHEAD_RECORDING_DEMO_AUTO=0`** or **`--no-recording-demo-browser`** for CI. **Persistent profile + recording:** extra restored tabs are closed at start (may add short sidecar `.webm` files); use **`primary_video`** / **`role=primary`** for the main demo. Title cards: **`TRAILHEAD_DEMO_TITLECARDS=0`**, **`TRAILHEAD_DEMO_TITLECARD_MS`**. **`plan --walk-ranked N`** / **`open-unit --visit-count N`**. Scripts: **`scripts/run-e2e-plan.ps1`** / **`run-e2e-plan.sh`**. Sample **`artifacts/`** may omit large **`.webm`** files. |
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

### Recording demo browser (auto)

**`TRAILHEAD_DEMO_NARRATION`** (default **on**): **`plan`**, **`open-unit`**, and **`org prepare --open-playground`** print a step-by-step trace on **stderr** (`[trailhead-agent]` lines): resolved **`--start-url`** / **`--intent`**, LLM env hints, recording/demo browser prefs, discovery title samples, each LangGraph node (prepare → planner → rank → repair → finalize), and the final ranked queue. **`plan --json`** still prints only JSON on stdout. Disable with **`TRAILHEAD_DEMO_NARRATION=0`** (tests set this in **`tests/conftest.py`**).

When **`TRAILHEAD_RECORD_VIDEO_DIR`** is set (**`plan --artifacts-dir`**, **`plan --save-e2e`**, or **`org prepare --open-playground`** with the env var), **recording demo auto** is **on** by default: **headed** Chromium (unless you already exported **`TRAILHEAD_AGENT_HEADLESS`**), Playwright **`slow_mo`** (~65 ms), **1440×900** viewport, **`AGENT_ACTION_DELAY_MS=100`**, and a slightly longer bottom scroll — so live runs and **`.webm`** files read more clearly. Disable for headless CI: **`TRAILHEAD_RECORDING_DEMO_AUTO=0`**, **`plan --no-recording-demo-browser`**, or **`org prepare --no-recording-demo-browser`**. Tune **`TRAILHEAD_DEMO_SLOW_MO_MS`** and viewport env vars (see **`.env.example`**). **`trailhead-agent doctor`** prints whether a recording dir is active and whether demo auto is enabled.

**Playwright-style habits in code:** [`browser_agent_primitives.py`](src/trailhead_agent/browser_agent_primitives.py) sets **context/page default timeouts**, uses **locator `wait_for(attached)`** for a coarse Trailhead shell signal (**`TRAILHEAD_SHELL_WAIT_TIMEOUT_MS`**), and uses **varied scroll chunks** during recording (motion pacing — not a substitute for assertions). See the [Playwright best practices](https://playwright.dev/docs/best-practices) and [actionability](https://playwright.dev/docs/actionability) docs.

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

With **`--open-playground`**, the run writes **`e2e-org-prepare-latest.json`** (and **`e2e-report.html`** when recordings exist). The JSON may include a **`demo_guide`** block (optional human-facing copy); **`e2e-report.html`** is a compact viewer (videos, manifest, JSON links).

## Architecture

1. **Session** — Chromium; optional persistent profile or password login.
2. **Discovery** — Collects module/unit links (trail → module roots → units when needed). Scroll rounds (**`TRAILHEAD_DISCOVERY_SCROLL_ROUNDS`**, default 4) and optional **Load/Show more** clicks (**`TRAILHEAD_DISCOVERY_PAGINATION_CLICKS`**, default 8) help lazy listings. **`TRAILHEAD_DISCOVERY_NAV_WAIT_UNTIL`** can be set to **`load`** if the TOC is late. **Login / geo / error interstitials** are detected; **empty or degenerate** scrapes (no links, empty titles, duplicate-title noise) raise **`DiscoveryError` (exit 2)** with hints and stderr lines for **`page_url`** / **`page_title`** — the LLM is not called on bad discovery.
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
- **`plan-primary.webm` stops on a title slide or feels cut off** — After the title-card sequence (Phase 1 inputs → discovery → LLM ordered output → next steps, then optional Phase 5 walk slides), **`plan`** (when recording) navigates back to your **`--start-url`** module, waits for **`load`**, then dwells at least **`TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS`** (default **5500** ms, plus the usual scroll demo). With **`--walk-ranked N`** and at least one successful visit, the clip ends on the last opened unit instead. Tune dwell with **`TRAILHEAD_PLAN_RECORDING_TAIL_MIN_MS`** or **`TRAILHEAD_PAGE_SETTLE_MS`**. List length on the LLM slide: **`TRAILHEAD_DEMO_TITLECARD_RANK_MAX`** (default **18**).
- **`org-prepare.webm` looks blank or only a title card** — When **`TRAILHEAD_RECORD_VIDEO_DIR`** is set, **`org prepare --open-playground`** waits for **`load`**, then holds at least **`TRAILHEAD_ORG_PREPARE_RECORDING_MIN_MS`** (default **5500** ms, combined with **`TRAILHEAD_PAGE_SETTLE_MS`**) and runs the same **smooth scroll demo** as **`plan`** so the module UI has time to paint. Increase **`TRAILHEAD_ORG_PREPARE_RECORDING_MIN_MS`** or **`TRAILHEAD_PAGE_SETTLE_MS`** if Trailhead is slow; use **`TRAILHEAD_AGENT_HEADLESS=0`** to watch the browser live.
- **No “Launch Playground” / Salesforce org in the `.webm`** — Recordings stay on **Trailhead** only (human-in-the-loop: you click Launch yourself). The browser session tries to **scroll Launch / Playground / hands-on labels into view** when recording (**`TRAILHEAD_RECORDING_PLAYGROUND_CTA_SCROLL`**, default on). You usually need to be **signed in** to Trailhead and may need **`TRAILHEAD_BROWSER_USER_DATA_DIR`** + prior **`auth`** so CTAs are not hidden. The **Salesforce org UI** never appears until a real Launch / login flow completes outside automation.
- **`Permission denied` / `nllMonFltProxy` / `SSLKEYLOGFILE`** — Some security software sets `SSLKEYLOGFILE` to an invalid path. This app clears known-bad values after `load_dotenv()`. You can also remove `SSLKEYLOGFILE` from **User environment variables** in Windows.
- **`403 PERMISSION_DENIED` / Generative Language API disabled** — Enable the API for the Google Cloud project tied to your key: open the link in the error, or use a key from [Google AI Studio](https://aistudio.google.com/apikey) (often simpler).

## Compliance

Use a **personal** Trailhead account, respect Salesforce Terms of Service, and treat this as **planning + navigation**, not automated cheating.
