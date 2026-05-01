#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


LANGUAGES = ("python", "typescript", "go", "java", "dotnet")
REQUIRED_SCENARIOS = ("owner-provider-parity", "health", "fixed-price", "llm", "local-negative", "auth-negative")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build local SDK E2E DB reconciliation evidence.")
    parser.add_argument("--log", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--postgres-dsn", required=True)
    parser.add_argument("--command", default="")
    parser.add_argument("--max-cost-usdc", default="0.010000")
    parser.add_argument("--screenshots-json", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    events = parse_events(Path(args.log))
    event_errors = validate_events(events, Decimal(args.max_cost_usdc))
    invocation_ids = sorted(
        {
            str(event.get("invocationId"))
            for event in events
            if event.get("scenario") in {"fixed-price", "llm"} and event.get("invocationId")
        }
    )

    db = query_db(args.postgres_dsn, args.run_id, invocation_ids)
    db_errors = validate_db(events, db, Decimal(args.max_cost_usdc))
    screenshots = load_screenshots(args.screenshots_json)

    evidence = {
        "runId": args.run_id,
        "command": args.command,
        "events": events,
        "db": db,
        "screenshots": screenshots,
        "checks": {
            "passed": not event_errors and not db_errors,
            "eventErrors": event_errors,
            "dbErrors": db_errors,
        },
        "summary": build_summary(events, db),
    }

    (out_dir / "evidence.json").write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(evidence), encoding="utf-8")
    (out_dir / "report.html").write_text(render_html(evidence), encoding="utf-8")

    if event_errors or db_errors:
        for error in event_errors + db_errors:
            print(f"[sdk-local-evidence] {error}", file=sys.stderr)
        return 1
    print(f"[sdk-local-evidence] report written to {out_dir / 'report.md'}")
    return 0


def parse_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict) and event.get("language") and event.get("scenario"):
            events.append(event)
    return events


def validate_events(events: list[dict[str, Any]], max_cost: Decimal) -> list[str]:
    errors: list[str] = []
    seen: dict[str, set[str]] = defaultdict(set)
    for event in events:
        language = str(event.get("language", ""))
        scenario = str(event.get("scenario", ""))
        seen[language].add(scenario)
        if scenario in {"fixed-price", "llm"} and not event.get("invocationId"):
            errors.append(f"{language} {scenario} did not emit invocationId")
        if scenario == "llm":
            charge = decimal_or_none(event.get("chargedUsdc"))
            if charge is None:
                errors.append(f"{language} llm did not emit numeric chargedUsdc")
            elif charge <= 0:
                errors.append(f"{language} llm chargedUsdc must be > 0, got {charge}")
            elif charge > max_cost:
                errors.append(f"{language} llm chargedUsdc {charge} exceeds maxCostUsdc {max_cost}")
    for language in LANGUAGES:
        missing = sorted(set(REQUIRED_SCENARIOS) - seen.get(language, set()))
        if missing:
            errors.append(f"{language} missing scenarios: {', '.join(missing)}")
    return errors


def query_db(dsn: str, run_id: str, invocation_ids: list[str]) -> dict[str, Any]:
    invocations = psql_json(
        dsn,
        f"""
        WITH ids(id) AS ({values_clause(invocation_ids)})
        SELECT COALESCE(jsonb_agg(to_jsonb(q) ORDER BY q.created_at), '[]'::jsonb)
        FROM (
          SELECT invocation_id, quote_id, service_id, credential_id, idempotency_key, status,
                 charged_usdc::text AS charged_usdc, created_at::text AS created_at,
                 finished_at::text AS finished_at
          FROM synapse_invocations
          WHERE invocation_id IN (SELECT id FROM ids)
             OR idempotency_key LIKE {sql_literal(run_id + '-%')}
          ORDER BY created_at
        ) q
        """,
    )
    db_invocation_ids = sorted({row["invocation_id"] for row in invocations if row.get("invocation_id")})
    quote_ids = sorted({row["quote_id"] for row in invocations if row.get("quote_id")})
    quotes = psql_json(
        dsn,
        f"""
        WITH ids(id) AS ({values_clause(quote_ids)})
        SELECT COALESCE(jsonb_agg(to_jsonb(q) ORDER BY q.created_at), '[]'::jsonb)
        FROM (
          SELECT quote_id, service_id, credential_id, quoted_price_usdc::text AS quoted_price_usdc,
                 price_model, status, created_at::text AS created_at
          FROM synapse_service_quotes
          WHERE quote_id IN (SELECT id FROM ids)
          ORDER BY created_at
        ) q
        """,
    )
    budget_events = psql_json(
        dsn,
        f"""
        WITH ids(id) AS ({values_clause(db_invocation_ids)})
        SELECT COALESCE(jsonb_agg(to_jsonb(q) ORDER BY q.created_at), '[]'::jsonb)
        FROM (
          SELECT event_id, credential_id, quote_id, invocation_id, event_kind,
                 amount_usdc::text AS amount_usdc,
                 remaining_lifetime_usdc::text AS remaining_lifetime_usdc,
                 remaining_daily_usdc::text AS remaining_daily_usdc,
                 created_at::text AS created_at
          FROM synapse_budget_events
          WHERE invocation_id IN (SELECT id FROM ids)
          ORDER BY created_at
        ) q
        """,
    )
    ledger_entries = psql_json(
        dsn,
        f"""
        WITH ids(id) AS ({values_clause(db_invocation_ids)})
        SELECT COALESCE(jsonb_agg(to_jsonb(q) ORDER BY q.created_at), '[]'::jsonb)
        FROM (
          SELECT entry_id, reference_type, reference_id, business_type,
                 debit_account_id, credit_account_id, amount_usdc::text AS amount_usdc,
                 status, created_at::text AS created_at
          FROM synapse_ledger_entries
          WHERE reference_id IN (SELECT id FROM ids)
          ORDER BY created_at
        ) q
        """,
    )
    audit_events = psql_json(
        dsn,
        f"""
        WITH ids(id) AS ({values_clause(db_invocation_ids)})
        SELECT COALESCE(jsonb_agg(to_jsonb(q) ORDER BY q.created_at), '[]'::jsonb)
        FROM (
          SELECT event_id, event_type, business_type, credential_id, service_id,
                 invocation_id, amount_delta::text AS amount_delta, result_status,
                 detail_json::text AS detail_json, created_at::text AS created_at
          FROM synapse_audit_events
          WHERE invocation_id IN (SELECT id FROM ids)
             OR EXISTS (
               SELECT 1 FROM ids
               WHERE synapse_audit_events.detail_json::text LIKE '%' || ids.id || '%'
             )
          ORDER BY created_at
        ) q
        """,
    )
    return {
        "invocations": invocations,
        "serviceQuotes": quotes,
        "budgetEvents": budget_events,
        "ledgerEntries": ledger_entries,
        "auditEvents": audit_events,
        "rowCounts": {
            "invocations": len(invocations),
            "serviceQuotes": len(quotes),
            "budgetEvents": len(budget_events),
            "ledgerEntries": len(ledger_entries),
            "auditEvents": len(audit_events),
        },
    }


def psql_json(dsn: str, sql: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["psql", dsn, "-X", "-A", "-t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = result.stdout.strip()
    if not output:
        return []
    parsed = json.loads(output)
    if not isinstance(parsed, list):
        raise ValueError("psql query did not return a JSON array")
    return parsed


def validate_db(events: list[dict[str, Any]], db: dict[str, Any], max_cost: Decimal) -> list[str]:
    errors: list[str] = []
    invocation_rows = {row["invocation_id"]: row for row in db["invocations"] if row.get("invocation_id")}
    ledger_by_invocation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    audit_by_invocation: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in db["ledgerEntries"]:
        ledger_by_invocation[str(row.get("reference_id", ""))].append(row)
    expected_invocation_ids = {
        str(event.get("invocationId") or "")
        for event in events
        if event.get("scenario") in {"fixed-price", "llm"} and event.get("invocationId")
    }
    for row in db["auditEvents"]:
        invocation_id = audit_invocation_id(row, expected_invocation_ids)
        if invocation_id:
            audit_by_invocation[invocation_id].append(row)

    for event in events:
        scenario = event.get("scenario")
        if scenario not in {"fixed-price", "llm"}:
            continue
        language = event.get("language")
        invocation_id = str(event.get("invocationId") or "")
        row = invocation_rows.get(invocation_id)
        if not row:
            errors.append(f"{language} {scenario} invocation {invocation_id} missing from synapse_invocations")
            continue
        if scenario == "llm":
            charge = decimal_or_none(row.get("charged_usdc"))
            if charge is None or charge <= 0:
                errors.append(f"{language} llm DB charge must be > 0, got {row.get('charged_usdc')}")
            elif charge > max_cost:
                errors.append(f"{language} llm DB charge {charge} exceeds maxCostUsdc {max_cost}")
            if not ledger_by_invocation.get(invocation_id):
                errors.append(f"{language} llm invocation {invocation_id} missing ledger entries")
            if not audit_by_invocation.get(invocation_id):
                errors.append(f"{language} llm invocation {invocation_id} missing audit events")
    return errors


def build_summary(events: list[dict[str, Any]], db: dict[str, Any]) -> dict[str, Any]:
    rows = []
    by_language: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for event in events:
        by_language[str(event.get("language"))][str(event.get("scenario"))] = event
    for language in LANGUAGES:
        fixed = by_language.get(language, {}).get("fixed-price", {})
        llm = by_language.get(language, {}).get("llm", {})
        rows.append(
            {
                "language": language,
                "passed": all(s in by_language.get(language, {}) for s in REQUIRED_SCENARIOS),
                "fixedInvocationId": fixed.get("invocationId", ""),
                "fixedChargedUsdc": fixed.get("chargedUsdc", ""),
                "llmInvocationId": llm.get("invocationId", ""),
                "llmChargedUsdc": llm.get("chargedUsdc", ""),
            }
        )
    return {"languages": rows, "dbRowCounts": db["rowCounts"]}


def audit_invocation_id(row: dict[str, Any], expected_ids: set[str]) -> str:
    direct = str(row.get("invocation_id") or "").strip()
    if direct:
        return direct
    detail = str(row.get("detail_json") or "")
    for invocation_id in expected_ids:
        if invocation_id and invocation_id in detail:
            return invocation_id
    return ""


def render_markdown(evidence: dict[str, Any]) -> str:
    lines = [
        "# SDK Local E2E Evidence",
        "",
        f"- Run ID: `{evidence['runId']}`",
        f"- Command: `{evidence['command']}`",
        f"- Passed: `{str(evidence['checks']['passed']).lower()}`",
        "",
        "## SDK Results",
        "",
        "| SDK | Pass | Fixed invocation | Fixed charged USDC | LLM invocation | LLM charged USDC |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in evidence["summary"]["languages"]:
        lines.append(
            f"| {row['language']} | {yes_no(row['passed'])} | `{row['fixedInvocationId']}` | "
            f"`{row['fixedChargedUsdc']}` | `{row['llmInvocationId']}` | `{row['llmChargedUsdc']}` |"
        )
    lines += ["", "## DB Row Counts", ""]
    for name, count in evidence["summary"]["dbRowCounts"].items():
        lines.append(f"- `{name}`: {count}")
    if evidence["summary"]["dbRowCounts"].get("budgetEvents") == 0:
        lines.append("- `synapse_budget_events` returned 0 rows in this local backend; ledger and audit rows are used as hard billing evidence.")
    if evidence.get("screenshots"):
        lines += ["", "## Screenshots", ""]
        for item in evidence["screenshots"]:
            lines.append(f"- `{item.get('name')}`: `{item.get('path')}`")
    if evidence["checks"]["eventErrors"] or evidence["checks"]["dbErrors"]:
        lines += ["", "## Errors", ""]
        for error in evidence["checks"]["eventErrors"] + evidence["checks"]["dbErrors"]:
            lines.append(f"- {error}")
    return "\n".join(lines) + "\n"


def render_html(evidence: dict[str, Any]) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td>{esc(row['language'])}</td>"
        f"<td>{'PASS' if row['passed'] else 'FAIL'}</td>"
        f"<td>{esc(row['fixedInvocationId'])}</td>"
        f"<td>{esc(row['fixedChargedUsdc'])}</td>"
        f"<td>{esc(row['llmInvocationId'])}</td>"
        f"<td>{esc(row['llmChargedUsdc'])}</td>"
        "</tr>"
        for row in evidence["summary"]["languages"]
    )
    counts = "\n".join(
        f"<li><code>{esc(name)}</code>: {count}</li>" for name, count in evidence["summary"]["dbRowCounts"].items()
    )
    screenshots = "\n".join(
        f"<li><code>{esc(str(item.get('name')))}</code>: {esc(str(item.get('path')))}</li>"
        for item in evidence.get("screenshots", [])
    )
    errors = "\n".join(
        f"<li>{esc(error)}</li>" for error in evidence["checks"]["eventErrors"] + evidence["checks"]["dbErrors"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>SDK Local E2E Evidence</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; margin: 32px; color: #111827; }}
    code {{ background: #f3f4f6; padding: 2px 5px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f9fafb; }}
    .pass {{ color: #047857; font-weight: 700; }}
    .fail {{ color: #b91c1c; font-weight: 700; }}
  </style>
</head>
<body>
  <h1>SDK Local E2E Evidence</h1>
  <p>Run ID: <code>{esc(evidence['runId'])}</code></p>
  <p>Command: <code>{esc(evidence['command'])}</code></p>
  <p>Status: <span class="{'pass' if evidence['checks']['passed'] else 'fail'}">{'PASS' if evidence['checks']['passed'] else 'FAIL'}</span></p>
  <h2>SDK Results</h2>
  <table>
    <thead><tr><th>SDK</th><th>Pass</th><th>Fixed invocation</th><th>Fixed charged USDC</th><th>LLM invocation</th><th>LLM charged USDC</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <h2>DB Row Counts</h2>
  <ul>{counts}</ul>
  <p><code>synapse_budget_events</code> may be empty on the current local backend; ledger and audit rows are the hard billing evidence.</p>
  <h2>Screenshots</h2>
  <ul>{screenshots}</ul>
  <h2>Errors</h2>
  <ul>{errors or '<li>None</li>'}</ul>
</body>
</html>
"""


def load_screenshots(path: str) -> list[dict[str, str]]:
    if not path:
        return []
    screenshot_path = Path(path)
    if not screenshot_path.exists():
        return []
    data = json.loads(screenshot_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def decimal_or_none(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def values_clause(values: list[str]) -> str:
    if not values:
        return "SELECT NULL::text WHERE false"
    return "VALUES " + ", ".join(f"({sql_literal(value)})" for value in values)


def sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


if __name__ == "__main__":
    raise SystemExit(main())
