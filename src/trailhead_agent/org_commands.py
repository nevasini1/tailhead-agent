"""
CLI handlers for `trailhead-agent org *` (doctor, checklist, prepare).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from trailhead_agent.cli_org_executor import (
    org_display_says_connected,
    resolve_org_alias,
    run_sf_org_display_json,
    sf_on_path,
)
from trailhead_agent.config import load_config, persistent_profile_dir, record_video_dir, start_url_from_env
from trailhead_agent.context import get_trace_id
from trailhead_agent.demo_titlecards import demo_org_prepare_browser
from trailhead_agent.e2e_artifacts import append_e2e_manifest_recording, new_webm_names_sorted_by_mtime, webm_basenames
from trailhead_agent.errors import OrgExecutorError
from trailhead_agent.org_checklists import (
    checklist_json_list,
    checklist_markdown_table,
    default_org_checklists_path,
    resolve_checklist_for_context,
)
from trailhead_agent.org_executor import OrgStep, TrailheadUnitContext, get_default_org_executor
from trailhead_agent.runner import run_dry_plan
from trailhead_agent.session import TrailheadBrowser
from trailhead_agent.validation import validate_start_url

logger = logging.getLogger(__name__)


def _executor_label(ex: object) -> str:
    return type(ex).__name__


def run_org_doctor(*, json_out: bool, org_alias: str | None = None) -> int:
    load_dotenv_if_needed()
    ex = get_default_org_executor()
    alias_resolved = resolve_org_alias(org_alias)
    sf_ok = sf_on_path()
    org_connected = False
    sf_exit: int | None = None
    sf_hint = ""
    if sf_ok:
        code, data, err = run_sf_org_display_json(org_alias=alias_resolved)
        sf_exit = code
        org_connected = code == 0 and data is not None and org_display_says_connected(data)
        if not org_connected and err:
            sf_hint = err[:300]
    env_executor = os.environ.get("TRAILHEAD_ORG_EXECUTOR", "noop").strip().lower() or "noop"
    report: dict[str, Any] = {
        "executor": _executor_label(ex),
        "trailhead_org_executor_env": env_executor,
        "sf_on_path": sf_ok,
        "org_alias_configured": bool(alias_resolved),
        "org_alias": alias_resolved or "",
        "org_connected": org_connected,
        "sf_org_display_exit_code": sf_exit,
        "browser_profile_configured": persistent_profile_dir() is not None,
        "checklists_file": str(default_org_checklists_path()),
    }
    if sf_hint:
        report["sf_stderr_hint"] = sf_hint
    logger.info(
        "org_executor stage=org_doctor executor=%s sf_on_path=%s org_connected=%s",
        report["executor"],
        sf_ok,
        org_connected,
    )
    if json_out:
        print(json.dumps(report, indent=2))
    else:
        print(f"org doctor - executor: {report['executor']} (TRAILHEAD_ORG_EXECUTOR={env_executor})")
        print(f"  sf on PATH: {sf_ok}")
        print(f"  org alias: {alias_resolved or '(default / not set)'}")
        print(f"  org connected (sf org display): {org_connected}")
        print(f"  browser profile dir set: {report['browser_profile_configured']}")
        print(f"  checklists file: {report['checklists_file']}")
        if not sf_ok:
            print("  Install Salesforce CLI: https://developer.salesforce.com/tools/salesforcecli")
    return 0


def load_dotenv_if_needed() -> None:
    from dotenv import load_dotenv

    from trailhead_agent.config import sanitize_environment

    load_dotenv()
    sanitize_environment()


def load_units_from_plan_json(path: Path) -> list[dict[str, str]]:
    text = path.expanduser().read_text(encoding="utf-8")
    data = json.loads(text)
    raw = data.get("units")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        href = str(row.get("href") or "").strip()
        title = str(row.get("title") or "").strip()
        if href:
            out.append({"title": title or href, "href": href})
    return out


def _steps_from_dicts(rows: list[dict[str, str]]) -> list[OrgStep]:
    return [OrgStep(step_id=r["step_id"], description=r["description"], verification=r["verification"]) for r in rows]


def run_org_checklist(
    *,
    json_out: bool,
    plan_json: Path | None,
    unit_href: str | None,
    unit_title: str,
    start_url: str | None,
    intent: str | None,
    top_n: int,
    checklist_config: Path | None,
    agent_config_path: Path | None,
) -> int:
    load_dotenv_if_needed()
    sources = sum(
        1
        for b in (
            plan_json is not None,
            bool((unit_href or "").strip()),
            bool((start_url or "").strip() and (intent or "").strip()),
        )
        if b
    )
    if sources != 1:
        raise OrgExecutorError(
            "Provide exactly one of: --plan-json PATH, --unit-href URL, or both --start-url and --intent."
        )

    units: list[dict[str, str]] = []
    if plan_json is not None:
        units = load_units_from_plan_json(plan_json)
    elif unit_href:
        units = [{"title": unit_title or unit_href, "href": unit_href.strip()}]
    else:
        su = validate_start_url((start_url or "").strip())
        it = (intent or "").strip()
        if not it:
            raise OrgExecutorError("--intent is required with --start-url for checklist.")
        cfg = load_config(agent_config_path)
        plan = run_dry_plan(cfg, start_url=su, intent=it, label=su, log_units=False)
        units = [{"title": u.title, "href": u.href} for u in plan.units]

    if not units:
        raise OrgExecutorError("No units to show checklists for.")

    n = max(1, min(top_n, len(units)))
    ex = get_default_org_executor()
    blocks: list[dict[str, Any]] = []
    for u in units[:n]:
        ctx = TrailheadUnitContext(title=u["title"], href=u["href"])
        steps, key = resolve_checklist_for_context(ctx, registry_path=checklist_config)
        proposed = ex.propose_steps(ctx)
        use = proposed if proposed else steps
        blocks.append(
            {
                "title": u["title"],
                "href": u["href"],
                "checklist_source": key,
                "steps": checklist_json_list(use),
            }
        )
        logger.info(
            "org_executor stage=org_checklist href=%s steps=%d source=%s",
            u["href"],
            len(use),
            key,
        )

    if json_out:
        print(json.dumps({"units": blocks}, ensure_ascii=False, indent=2))
    else:
        for b in blocks:
            print(f"\n## {b['title']}\n{b['href']}\n(source: {b['checklist_source']})\n")
            print(checklist_markdown_table(_steps_from_dicts(b["steps"])))
    return 0


def run_org_prepare(
    *,
    json_out: bool,
    org_alias: str | None,
    start_url: str | None,
    open_playground: bool,
    project_dir: Path | None,
    deploy: bool,
    agent_config_path: Path | None,
) -> int:
    load_dotenv_if_needed()
    ex = get_default_org_executor()
    alias_resolved = resolve_org_alias(org_alias)
    ctx = TrailheadUnitContext(
        title="prepare",
        href=(start_url or start_url_from_env() or "https://trailhead.salesforce.com/"),
    )
    warnings: list[str] = []

    ready = ex.ensure_playground_ready(ctx, org_alias=alias_resolved)
    if not sf_on_path():
        warnings.append("sf CLI not on PATH")

    if open_playground:
        env_open = os.environ.get("TRAILHEAD_PLAYGROUND_OPEN", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
        if not env_open:
            warnings.append("TRAILHEAD_PLAYGROUND_OPEN disables browser navigation; skipped.")
        else:
            su = (start_url or start_url_from_env() or "").strip()
            if not su:
                raise OrgExecutorError("--start-url or TRAILHEAD_START_URL required with --open-playground.")
            url = validate_start_url(su)
            cfg = load_config(agent_config_path)
            logger.info("org_executor stage=prepare open_playground url=%s", url)
            vroot = record_video_dir()
            before_w = webm_basenames(vroot) if vroot else set()
            with TrailheadBrowser(cfg) as br:
                demo_org_prepare_browser(br.page)
                br.page.goto(url, wait_until="domcontentloaded")
                br.delay()
            if vroot:
                newv = new_webm_names_sorted_by_mtime(vroot, before_w)
                append_e2e_manifest_recording(
                    vroot,
                    {
                        "source": "org_prepare",
                        "command": "org prepare",
                        "trace_id": get_trace_id(),
                        "primary_video": (newv[-1] if newv else None),
                        "new_videos": list(newv),
                        "start_url": url,
                    },
                )
            warnings.append(
                "Browser opened Trailhead page - complete Launch Playground / login manually "
                "(human-in-the-loop)."
            )

    deploy_result: dict[str, Any] | None = None
    if deploy:
        if not project_dir or not project_dir.is_dir():
            raise OrgExecutorError("--deploy requires --project-dir pointing to an SFDX project directory.")
        step = OrgStep(step_id="deploy", description="Metadata deploy", verification="sf_deploy")
        from trailhead_agent.cli_org_executor import CliOrgExecutor

        cex = CliOrgExecutor(org_alias=alias_resolved, project_dir=project_dir)
        res = cex.execute_step(ctx, step)
        deploy_result = {"ok": res.ok, "message": res.message}
        if not res.ok:
            raise OrgExecutorError(res.message or "Deploy failed.")

    report: dict[str, Any] = {
        "executor": _executor_label(ex),
        "org_alias_resolved": alias_resolved or "",
        "playground_ready": ready,
        "warnings": warnings,
        "deploy": deploy_result,
    }
    logger.info("org_executor stage=prepare done ready=%s", ready)
    if json_out:
        print(json.dumps(report, indent=2))
    else:
        print(f"prepare - executor: {report['executor']}")
        print(f"  org connected / ready (sf): {ready}")
        for w in warnings:
            print(f"  note: {w}")
        if deploy_result:
            print(f"  deploy: {deploy_result}")
    return 0

