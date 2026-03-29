# Plan: Org executor & Trailhead Playground workflow (v2)

This document is a **implementation roadmap** for extending the trailhead-agent with a real **`OrgExecutor`**—helping learners **prepare a Salesforce org / Playground** and follow **human-in-the-loop checklists** for hands-on units. It does **not** include auto-submitting Trailhead quizzes, knowledge checks, or bypassing assessments.

**Existing code:** [`src/trailhead_agent/org_executor.py`](src/trailhead_agent/org_executor.py) (`OrgExecutor` protocol, `TrailheadUnitContext`, `OrgStep`, `NoopOrgExecutor`, `get_default_org_executor`, **`CliOrgExecutor`**). **Wired from** [`cli.py`](src/trailhead_agent/cli.py) as **`trailhead-agent org …`** ([`org_commands.py`](src/trailhead_agent/org_commands.py)).

**Design alignment:** [`DESIGN.md`](DESIGN.md) v2 roadmap §1–2.

---

## 1. Goals and non-goals

### 1.1 Goals

- After (or alongside) a ranked plan, offer a **credible path** from a unit’s **title/href** to: “is my Playground ready?” → “what steps should I do in the org?” → optional **helpers** (CLI hints, deploy starter project, open browser to org).
- Keep **humans in the loop**: learner performs hands-on work and passes Trailhead’s own verification.
- **Observable**: structured logs / JSON fields for `org_executor` stages (no secrets).

### 1.2 Non-goals

- Automating Trailhead **quiz answers**, **challenge checks**, or **superbadge** validation.
- Scraping proprietary challenge solutions or hidden test criteria.
- Storing long-lived production org passwords in repo; use env + OS secret stores patterns only in docs.

---

## 2. User journeys (define before coding)

Document these as acceptance scenarios; implement smallest journey first.

| ID | Journey | Success signal |
|----|---------|----------------|
| J0 | `doctor` extended: reports whether `sf` is on PATH, default org alias set (optional) | JSON/text flags |
| J1 | Given top `UnitRef` from a plan, print a **static or mapped checklist** (Markdown or JSON) | User runs one new CLI subcommand |
| J2 | **Open Trailhead Playground** from Trailhead in browser (same Playwright session or new tab)—*navigation only* | Playground launch URL reached / user completes Salesforce login |
| J3 | **Ensure org target**: verify `sf org display` for configured alias; print next command if missing | Clear error + doc link |
| J4 | **Optional deploy**: run `sf project deploy start` against a **user-supplied** project path (opt-in flag) | Exit code surfaced; no silent deploy |

Refine J2/J4 after spike: Trailhead’s “Launch Playground” flow is UI-heavy; may stay “guided navigation” rather than headless completion.

---

## 3. Architecture decisions

### 3.1 Where `OrgExecutor` lives

- **Keep** the protocol in `org_executor.py`.
- Add **`PlaygroundOrgExecutor`** (or split: `CliOrgExecutor` + `BrowserPlaygroundHelper`) in the same package or `trailhead_agent/org/` subpackage if files grow.
- **Wire** via `get_default_org_executor()` reading env, e.g. `TRAILHEAD_ORG_EXECUTOR=noop|cli` (default `noop`).

### 3.2 Separation from ranking

- **No change** to href allowlist or LangGraph ranking contract in v2a.
- **Optional**: extend `RunPlan` JSON with `org_hints: [...]` only after checklist MVP is stable (avoid bloating plan schema early).

### 3.3 Browser vs CLI

| Concern | Browser (Playwright) | Salesforce CLI (`sf`) |
|--------|----------------------|------------------------|
| Launch Playground from Trailhead | Natural fit | N/A |
| Deploy metadata | Fragile in-browser | **Preferred** |
| Verify org connection | Possible via setup UI | **`sf org display`** |

**Recommendation:** use **CLI for org identity and deploy**; use **browser only** where Trailhead UI is the only entry (Playground launch), same compliance stance as today.

### 3.4 Checklist data sources (priority order)

1. **Static YAML/JSON map** keyed by module slug or unit href pattern → list of `OrgStep` (fast, testable, no extra LLM cost).
2. **Generic template** per unit type (“Apex module” → generic steps: open dev console, create class, run test)—still vetted text.
3. **Optional LLM assist** (later): generate *draft* checklist from **public** unit titles + user intent; **must** be labeled draft; human confirms before any automation. Align with DESIGN.md “checklist extraction” and keep out of default path until evals exist.

---

## 4. Protocol and model tweaks (if needed)

Review after MVP:

- `ensure_playground_ready` may need **`org_alias: str | None`** or read from `TRAILHEAD_SF_ORG_ALIAS` env.
- `execute_step` for CLI-backed steps might return structured result: `(ok: bool, stdout_snippet: str)`—consider a small `@dataclass` instead of bare `bool` for observability.
- Add **`OrgExecutorError`** in `errors.py` with exit code mapping (mirror LLM exit code pattern in CLI).

Document any protocol change in `DESIGN.md` and bump tests.

---

## 5. CLI surface (proposal)

Introduce incrementally:

```text
trailhead-agent org doctor          # sf present, org alias, optional browser profile
trailhead-agent org checklist       # --start-url + --intent OR --plan-json path → print steps
trailhead-agent org prepare         # optional: open playground flow + sf org check (flags TBD)
```

**Alternative:** single `trailhead-agent org` with subparsers (`doctor`, `checklist`, `prepare`).

**Flags (draft):**

- `--plan-json PATH` — consume existing `e2e-plan-*.json` or stdout plan; use first N units.
- `--unit-href URL` — single unit.
- `--sf-org-alias ALIAS` — override env.
- `--project-dir PATH` — optional deploy root for prepare (explicit opt-in).

---

## 6. Configuration and environment

Add to `.env.example` (when implementing):

| Variable | Purpose |
|----------|---------|
| `TRAILHEAD_SF_ORG_ALIAS` | Default target org for `sf` commands |
| `TRAILHEAD_ORG_EXECUTOR` | `noop` \| `cli` (future) |
| `TRAILHEAD_PLAYGROUND_OPEN` | `0`/`1` — whether `prepare` may navigate Trailhead for Launch |
| `TRAILHEAD_ORG_PROJECT_DIR` | Optional default deploy path (still require flag for mutating commands if safer) |

**Security:** never print refresh tokens; subprocess stderr/stdout scrubbing if needed.

### 6.1 E2E video manifest (implemented)

When **`TRAILHEAD_RECORD_VIDEO_DIR`** points at an artifacts folder, **`org prepare --open-playground`** appends a row to **`e2e-manifest.json`** (alongside **`plan`** / **`open-unit`** entries) with **`source`: `org_prepare`**, **`primary_video`**, and **`new_videos`**. Use the manifest to see every clip recorded into that directory, not only the latest `e2e-plan-*.json`.

---

## 7. Implementation phases

### Phase 0 — Inventory and spike (0.5–1 day)

- [ ] Manually record steps: Trailhead “Launch Playground” clicks vs deep link patterns (document in this file or `DESIGN.md`).
- [ ] Confirm `sf` version and non-interactive flags (`--json`) for scripting.
- [ ] Decide minimum Windows + macOS behavior (project already Windows-aware).

### Phase 1 — Wire + noop parity (0.5 day)

- [ ] Import `get_default_org_executor()` from `cli` only for `org doctor` showing “executor=noop”.
- [ ] Tests: CLI returns 0; JSON shape stable.

### Phase 2 — Checklist MVP (1–2 days)

- [ ] Add `data/org_steps/` or `config/org_checklists.yaml` with 1–2 real modules as examples.
- [ ] Implement resolver: `TrailheadUnitContext` → list[`OrgStep`] by normalizing href (module + unit slug).
- [ ] `org checklist` command: load plan or href; print Markdown table or `--json` array.
- [ ] Unit tests: resolver coverage; golden file for sample href.

### Phase 3 — CLI org executor (1–2 days)

- [ ] `CliOrgExecutor.ensure_playground_ready`: subprocess `sf org display --target-org <alias> --json`; parse JSON for `connected` / username.
- [ ] `propose_steps`: delegate to Phase 2 registry.
- [ ] `execute_step`: map `verification` types—e.g. `sf_deploy` runs deploy; `manual` no-op with log.
- [ ] Integration test **optional**, gated by `RUN_SF_INTEGRATION=1` and CI skip by default.

### Phase 4 — Browser-assisted Playground (1–3 days, highest uncertainty)

- [ ] Reuse `TrailheadBrowser` session or document “run `auth` first.”
- [ ] Navigate to unit page; locate “Launch” / Playground control via **configurable selectors** in `config/default.yaml` (same pattern as login).
- [ ] Stop at “user completes Salesforce login”—do not store org credentials.
- [ ] E2E: optional workflow_dispatch only; document flakiness.

### Phase 5 — Docs and polish

- [ ] README section “Org / Playground workflow.”
- [ ] Update `DESIGN.md` threat model: subprocess injection (sanitize alias/path), `sf` not found.
- [ ] `trailhead-agent doctor --json`: include org executor kind + `sf` on PATH.

---

## 8. Testing strategy

| Layer | What |
|-------|------|
| Unit | Href → module key extraction; YAML load; `CliOrgExecutor` with mocked `subprocess.run` |
| Golden | Sample checklist JSON for one module |
| Integration | Behind env flag; real `sf` org optional |
| E2E | Manual or CI manual only for Playground launch |

---

## 9. Observability

- Log prefix: `org_executor stage=...` with `trace_id`.
- JSON output: `executor`, `org_alias_resolved`, `steps_count`, `playground_ready: bool`, `warnings: []`.

---

## 10. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Trailhead DOM changes for Launch | Selectors in YAML; graceful degradation to “open unit URL manually” |
| `sf` not installed | Clear message in `org doctor`; exit code 2 |
| User runs deploy against wrong org | Require explicit `--target-org` or env; confirm flag for destructive-ish ops |
| Scope creep into quiz automation | Code review + keep protocol methods org-focused only |

---

## 11. Definition of done (v2a)

- [ ] Non-noop executor selectable via env.
- [ ] `org checklist` produces useful steps for at least **two** real Trailhead modules from fixture data.
- [ ] `org doctor` reports SF CLI + alias status.
- [ ] Documentation updated; tests green in CI without secrets.

---

## 12. Open questions (resolve in Phase 0 spike)

1. Is there a stable pattern to open a **specific** Playground from a unit without full UI traversal?
2. Should checklists live in-repo (OSS) or user-local `~/.trailhead-agent/` override path?
3. Multi-org learners: per-plan alias vs global env only?

---

*Last updated: aligned with repo `org_executor` stub and `DESIGN.md` v2 roadmap.*
