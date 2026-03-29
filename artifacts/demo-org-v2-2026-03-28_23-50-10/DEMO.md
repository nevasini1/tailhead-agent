# End-to-end demo: plan + org workflow (PLAN_ORG_EXECUTOR v2)

This folder was generated in one run to exercise the implemented journeys from [`PLAN_ORG_EXECUTOR.md`](../../PLAN_ORG_EXECUTOR.md) (human-in-the-loop; no quiz automation).

## Commands used

```powershell
cd <repo-root>
$demo = "artifacts\demo-org-v2-<timestamp>"
python -m trailhead_agent plan --json --artifacts-dir $demo --walk-ranked 3
python -m trailhead_agent doctor --json
python -m trailhead_agent org doctor --json
python -m trailhead_agent org checklist --plan-json "$demo\e2e-plan-latest.json" --top-n 3 --json
python -m trailhead_agent org prepare --json
```

(`TRAILHEAD_START_URL` / `TRAILHEAD_INTENT` / LLM keys came from `.env` on the machine that generated this demo.)

## Artifact → journey mapping

| ID | Journey | File(s) |
|----|---------|---------|
| **J0** | Extended `doctor` (LLM + `sf` + org executor) | `00-doctor.json` |
| **J0** | `org doctor` (executor, checklists path, `sf org display` when `sf` exists) | `01-org-doctor.json` |
| **J1** | Checklist from ranked plan (`--plan-json`) | `02-org-checklist-from-plan.json`, `02-org-checklist-from-plan.md` |
| **J2** | Open Trailhead in browser (navigation only) | *Not run in batch demo* — run: `python -m trailhead_agent org prepare --open-playground --start-url "<module URL>"` |
| **J3** | Ensure org target (`sf org display`) | Reflected in `01-org-doctor.json` (`org_connected`, `sf_on_path`) and `03-org-prepare-no-browser.json` |
| **J4** | Optional deploy | *Not run* — requires real SFDX project: `org prepare --deploy --project-dir <path>` |

## Plan + video

| File | Purpose |
|------|---------|
| `plan-stdout.json` | Same plan object as stdout from `plan --json` |
| `e2e-plan-latest.json` | E2E bundle (+ `saved_at_utc`, `video_files`, `walk_ranked_visits`) |
| `e2e-plan-<trace_id>.json` | Copy keyed by trace |
| `*.webm` | Playwright recording (discovery + LLM wait + **3** ranked `goto` steps) |

## Reproduce with `CliOrgExecutor`

```powershell
$env:TRAILHEAD_ORG_EXECUTOR = "cli"
# optional: $env:TRAILHEAD_SF_ORG_ALIAS = "YourAlias"
python -m trailhead_agent org doctor --json
```
