# Demo: title cards + E2E contract (v0.5.1)

Sample **`plan`** run with **`--artifacts-dir`** (this folder) plus a follow-up **`org prepare --open-playground`** with **`TRAILHEAD_RECORD_VIDEO_DIR`** set to the same path.

## What to open

| File | Purpose |
|------|---------|
| **`e2e-plan-latest.json`** | Full plan + **`primary_video`**, **`e2e_session_videos`**, **`video_files`**, **`walk_ranked_visits`** |
| **`e2e-manifest.json`** | Ordered list of recordings: **`plan`** clip(s) and **`org_prepare`** clip |
| **`*.webm`** | Playwright videos (may be omitted from git if large; regenerate locally) |

## Commands (reference)

```powershell
$dir = "artifacts\demo-titlecards-2026-03-29"
python -m trailhead_agent plan --json --artifacts-dir $dir --walk-ranked 3 --start-url "https://trailhead.salesforce.com/content/learn/modules/apex_database" --intent "YOUR_INTENT"
$env:TRAILHEAD_RECORD_VIDEO_DIR = (Resolve-Path $dir).Path
python -m trailhead_agent org prepare --json --open-playground --start-url "https://trailhead.salesforce.com/content/learn/modules/apex_database"
```

**v0.5.1:** Discovery raises **`DiscoveryError`** with hints when no unit links or a login/geo wall is detected. With a persistent browser profile, **one tab** is used when recording so you usually get **one `.webm` per** `plan` / `open-unit` session.
