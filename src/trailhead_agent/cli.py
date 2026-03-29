from __future__ import annotations

import argparse
import json
import logging
import os
import uuid
from pathlib import Path

from dotenv import load_dotenv

from trailhead_agent import __version__
from trailhead_agent.cli_org_executor import org_display_says_connected, run_sf_org_display_json, sf_on_path
from trailhead_agent.config import (
    intent_from_env,
    load_config,
    sanitize_environment,
    start_url_from_env,
)
from trailhead_agent.context import set_trace_id
from trailhead_agent.e2e_artifacts import write_e2e_open_unit_output, write_e2e_plan_output
from trailhead_agent.errors import (
    ConfigurationError,
    DiscoveryError,
    LLMProviderError,
    OrgExecutorError,
    TrailheadAgentError,
    UrlValidationError,
)
from trailhead_agent.logging_utils import configure_logging
from trailhead_agent.org_commands import run_org_checklist, run_org_doctor, run_org_prepare
from trailhead_agent.org_executor import get_default_org_executor
from trailhead_agent.runner import open_first_ranked_unit, run_auth_setup, run_dry_plan


def _log_level(name: str) -> int:
    return getattr(logging, name.upper(), logging.INFO)


def _add_browser_e2e_args(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to YAML (browser/selectors only)",
    )
    p.add_argument(
        "--artifacts-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "plan / open-unit: save Playwright .webm + e2e JSON under DIR "
            "(same as TRAILHEAD_RECORD_VIDEO_DIR). Directory is created if missing."
        ),
    )
    p.add_argument(
        "--save-e2e",
        action="store_true",
        help="plan / open-unit: shorthand for --artifacts-dir ./artifacts/e2e (from cwd).",
    )


def _run_doctor(*, json_out: bool) -> int:
    load_dotenv()
    sanitize_environment()
    prov = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    creds: dict[str, str | bool] = {"provider": prov, "ranking_orchestrator": "langgraph"}
    if prov in ("gemini", "google"):
        ok = bool(
            os.environ.get("GOOGLE_API_KEY", "").strip()
            or os.environ.get("GEMINI_API_KEY", "").strip()
        )
        creds["api_key_configured"] = ok
    elif prov in ("anthropic", "claude"):
        creds["api_key_configured"] = bool(os.environ.get("ANTHROPIC_API_KEY", "").strip())
    else:
        creds["api_key_configured"] = bool(os.environ.get("OPENAI_API_KEY", "").strip())

    cfg_path = os.environ.get("TRAILHEAD_AGENT_CONFIG", "").strip() or "(default config/default.yaml)"
    ex = get_default_org_executor()
    sf_ok = sf_on_path()
    org_connected = False
    if sf_ok:
        from trailhead_agent.cli_org_executor import resolve_org_alias

        alias = resolve_org_alias(None)
        code, data, _ = run_sf_org_display_json(org_alias=alias)
        org_connected = code == 0 and data is not None and org_display_says_connected(data)

    report = {
        "version": __version__,
        "llm": creds,
        "config_path_hint": cfg_path,
        "trailhead_start_url_set": bool(start_url_from_env()),
        "trailhead_intent_set": bool(intent_from_env()),
        "org_executor": type(ex).__name__,
        "trailhead_org_executor_env": os.environ.get("TRAILHEAD_ORG_EXECUTOR", "noop").strip().lower()
        or "noop",
        "sf_on_path": sf_ok,
        "sf_org_connected": org_connected,
    }
    if json_out:
        print(json.dumps(report, indent=2))
    else:
        print(f"trailhead-agent {__version__}")
        print(f"  LLM provider: {prov}")
        print(f"  Ranking orchestrator: {creds.get('ranking_orchestrator', 'langgraph')}")
        print(f"  API key configured: {creds.get('api_key_configured', False)}")
        print(f"  TRAILHEAD_START_URL set: {report['trailhead_start_url_set']}")
        print(f"  TRAILHEAD_INTENT set: {report['trailhead_intent_set']}")
        print(f"  Org executor: {report['org_executor']} ({report['trailhead_org_executor_env']})")
        print(f"  sf on PATH: {sf_ok}")
        print(f"  sf org connected: {org_connected}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Trailhead helper: Playwright discovers links; an LLM ranks/filters from your intent. "
            "No quiz automation."
        ),
    )
    parser.add_argument(
        "--log-json",
        action="store_true",
        help="Emit logs as one JSON object per line on stderr",
    )
    parser.add_argument(
        "--log-level",
        default=os.environ.get("TRAILHEAD_LOG_LEVEL", "INFO"),
        help="DEBUG, INFO, WARNING, ERROR (default INFO or TRAILHEAD_LOG_LEVEL)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    sub = parser.add_subparsers(dest="command", required=True)

    p_doc = sub.add_parser("doctor", help="Check version, LLM keys, org executor / sf (summary)")
    p_doc.add_argument("--json", action="store_true", help="Single JSON document on stdout")

    p_plan = sub.add_parser("plan", help="Discover units and LLM-rank into a study plan")
    _add_browser_e2e_args(p_plan)
    p_plan.add_argument(
        "--start-url",
        default=None,
        help="Trailhead trail or module URL (or TRAILHEAD_START_URL)",
    )
    p_plan.add_argument(
        "--intent",
        default=None,
        help="Natural-language goal for the LLM (or TRAILHEAD_INTENT)",
    )
    p_plan.add_argument("--label", default=None, help="Optional label for logs / JSON output")
    p_plan.add_argument(
        "--json",
        action="store_true",
        help="Print a single JSON document to stdout (logs on stderr)",
    )
    p_plan.add_argument(
        "--walk-ranked",
        type=int,
        default=0,
        metavar="N",
        help=(
            "After ranking, navigate to the first N ranked unit URLs (navigation only; E2E .webm). "
            "Uses TRAILHEAD_PAGE_SETTLE_MS; max 100. Default 0."
        ),
    )

    p_open = sub.add_parser("open-unit", help="Open first N LLM-ranked units in the browser")
    _add_browser_e2e_args(p_open)
    p_open.add_argument("--start-url", default=None, help="Or TRAILHEAD_START_URL")
    p_open.add_argument("--intent", default=None, help="Or TRAILHEAD_INTENT")
    p_open.add_argument("--label", default=None)
    p_open.add_argument(
        "--visit-count",
        type=int,
        default=1,
        metavar="N",
        help="Visit the first N ranked units (default 1; max 100).",
    )

    p_auth = sub.add_parser("auth", help="Interactive Trailhead sign-in (persistent profile)")
    p_auth.add_argument("--config", type=Path, default=None, help="Path to YAML (browser/selectors only)")

    p_org = sub.add_parser("org", help="Salesforce org / Playground helpers (human-in-the-loop)")
    org_sub = p_org.add_subparsers(dest="org_command", required=True)

    p_od = org_sub.add_parser("doctor", help="sf CLI, org alias, executor, checklists file")
    p_od.add_argument("--json", action="store_true")
    p_od.add_argument("--sf-org-alias", default=None, help="Override TRAILHEAD_SF_ORG_ALIAS for this check")

    p_oc = org_sub.add_parser(
        "checklist",
        help="Print org checklist for units (from plan JSON, single href, or plan via start-url+intent)",
    )
    p_oc.add_argument("--json", action="store_true")
    p_oc.add_argument("--plan-json", type=Path, default=None, metavar="PATH", help="e2e-plan or plan JSON")
    p_oc.add_argument("--unit-href", default=None, help="Single Trailhead unit URL")
    p_oc.add_argument("--unit-title", default="", help="With --unit-href")
    p_oc.add_argument("--start-url", default=None, help="With --intent: build plan first (browser + LLM)")
    p_oc.add_argument("--intent", default=None)
    p_oc.add_argument("--top-n", type=int, default=5, metavar="N", help="Max units from plan (default 5)")
    p_oc.add_argument(
        "--checklist-config",
        type=Path,
        default=None,
        help="Override org_checklists.yaml path",
    )
    p_oc.add_argument("--config", type=Path, default=None, help="YAML for browser when using --start-url")

    p_op = org_sub.add_parser("prepare", help="Check sf org; optional Trailhead browser + optional deploy")
    p_op.add_argument("--json", action="store_true")
    p_op.add_argument("--sf-org-alias", default=None)
    p_op.add_argument("--start-url", default=None, help="For --open-playground (or TRAILHEAD_START_URL)")
    p_op.add_argument(
        "--open-playground",
        action="store_true",
        help="Open Trailhead URL in browser (navigation only; you launch Playground manually)",
    )
    p_op.add_argument("--project-dir", type=Path, default=None, help="SFDX project root for --deploy")
    p_op.add_argument(
        "--deploy",
        action="store_true",
        help="Run sf project deploy start (requires --project-dir; explicit opt-in)",
    )
    p_op.add_argument("--config", type=Path, default=None, help="Browser YAML when using --open-playground")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    load_dotenv()
    sanitize_environment()

    level = logging.DEBUG if args.verbose else _log_level(args.log_level)
    if getattr(args, "command", None) == "plan" and getattr(args, "json", False) and not args.verbose:
        level = logging.WARNING
    configure_logging(level=level, json_format=args.log_json)
    log = logging.getLogger("trailhead_agent.cli")

    trace_id = str(uuid.uuid4())
    set_trace_id(trace_id)
    log.info("run_started command=%s trace_id=%s version=%s", args.command, trace_id, __version__)

    artifacts_dir: Path | None = getattr(args, "artifacts_dir", None)
    if getattr(args, "save_e2e", False) and artifacts_dir is None:
        artifacts_dir = Path("artifacts") / "e2e"
    if artifacts_dir is not None and args.command in ("plan", "open-unit"):
        root = artifacts_dir.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        os.environ["TRAILHEAD_RECORD_VIDEO_DIR"] = str(root)
        log.info("e2e_artifacts_dir=%s", root)

    try:
        if args.command == "doctor":
            return _run_doctor(json_out=args.json)

        if args.command == "org":
            if args.org_command == "doctor":
                return run_org_doctor(json_out=args.json, org_alias=args.sf_org_alias)
            if args.org_command == "checklist":
                return run_org_checklist(
                    json_out=args.json,
                    plan_json=args.plan_json,
                    unit_href=args.unit_href,
                    unit_title=args.unit_title or "",
                    start_url=args.start_url,
                    intent=args.intent,
                    top_n=args.top_n,
                    checklist_config=args.checklist_config,
                    agent_config_path=args.config,
                )
            if args.org_command == "prepare":
                return run_org_prepare(
                    json_out=args.json,
                    org_alias=args.sf_org_alias,
                    start_url=args.start_url,
                    open_playground=args.open_playground,
                    project_dir=args.project_dir,
                    deploy=args.deploy,
                    agent_config_path=args.config,
                )
            return 1

        cfg = load_config(getattr(args, "config", None))

        if args.command == "auth":
            run_auth_setup(cfg)
            return 0

        start = (args.start_url or start_url_from_env() or "").strip()
        intent = (args.intent or intent_from_env() or "").strip()
        if not start or not intent:
            parser.error(
                "Provide --start-url and --intent, or set TRAILHEAD_START_URL and TRAILHEAD_INTENT."
            )

        if args.command == "plan":
            if args.walk_ranked < 0 or args.walk_ranked > 100:
                parser.error("--walk-ranked must be between 0 and 100")
            plan = run_dry_plan(
                cfg,
                start_url=start,
                intent=intent,
                label=args.label,
                log_units=not args.json,
                walk_ranked=args.walk_ranked,
            )
            write_e2e_plan_output(plan)
            if args.json:
                print(json.dumps(plan.to_json_dict(), ensure_ascii=False))
            return 0

        if args.command == "open-unit":
            if args.visit_count < 1 or args.visit_count > 100:
                parser.error("--visit-count must be between 1 and 100")
            ou = open_first_ranked_unit(
                cfg,
                start_url=start,
                intent=intent,
                label=args.label,
                visit_count=args.visit_count,
            )
            write_e2e_open_unit_output(
                start_url=start,
                intent=intent,
                label=args.label,
                success=ou.ok,
                opened_href=ou.opened_href,
                ranked_unit_hrefs=ou.ranked_unit_hrefs,
                visit_count=args.visit_count,
                visited_unit_hrefs=ou.visited_unit_hrefs,
                primary_video=ou.primary_video,
                e2e_session_videos=ou.e2e_session_videos,
            )
            return 0 if ou.ok else 1

    except DiscoveryError as e:
        log.error("%s", e)
        for h in e.hints:
            log.error("  Hint: %s", h)
        return e.exit_code
    except UrlValidationError as e:
        log.error("%s", e)
        return e.exit_code
    except ConfigurationError as e:
        log.error("%s", e)
        return e.exit_code
    except LLMProviderError as e:
        log.error("%s", e)
        return e.exit_code
    except OrgExecutorError as e:
        log.error("%s", e)
        return e.exit_code
    except TrailheadAgentError as e:
        log.error("%s", e)
        return e.exit_code
    except KeyboardInterrupt:
        log.warning("Interrupted.")
        return 130

    return 1


def entrypoint() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entrypoint()
