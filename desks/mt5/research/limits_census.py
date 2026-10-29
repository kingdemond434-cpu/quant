#!/usr/bin/env python3
"""EVERY ACTIVE LIMIT ON THE DESK, NAMED BY WHAT KIND OF LIMIT IT IS (ARCH-25, 2026-10-07).

    python desks/mt5/research/limits_census.py [--out PATH]

The desk held its limits in a dozen places -- `stall_watch.json` for memory and disk, the seat
ledger for model allowances, `data/secrets` for data access, `gate_policy` for the statistical
bar, `rails.RAILS` for capital -- and nothing said which kind each one was. That matters because
each kind has a different owner and a different right answer:

  IMPLEMENTATION  a budget or timeout the code imposes on itself. Code can lift it; when it binds
                  the fix is engineering, never a purchase and never a lower bar.
  RESOURCE        a real bottleneck of the machine: memory, disk, cores. Measured on this host
                  now (psutil) and on the trading box (its stall_watch). Lifted by hardware or by
                  using less, never by pretending.
  ACCESS          access and budget: a key the desk lacks, a provider allowance, a spend cap, the
                  desk's own cost base. Lifted by acquiring, never by routing around a refusal.
  SCIENCE         a statistical safeguard (the gate policy). NEVER lifted to buy throughput:
                  "validation never relaxes". Listed so it is never mistaken for a bottleneck.
  CAPITAL         a capital control (the rails register). Billed by research/missed_growth.py;
                  Rule 1 says it must prove it raises robust forward E[log W] or be weakened.

Each row carries `binding`: True when the latest measurement shows the limit is what stopped
the desk, False when it was measured and had headroom, None when it was not measured. None is
a verdict (L1.28a), never folded into False. `binding_by_class` is the headline: a desk whose
binding limits are all SCIENCE and CAPITAL is spending its effort correctly; one bound by
IMPLEMENTATION is leaving growth on the floor for an engineering reason.

Read-only. Never prints a key: credentials are reported by file name and presence only, through
`scripts/check_credentials.py`, which reads shape and never content.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DESK = ROOT / "desks" / "mt5"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(DESK) not in sys.path:
    sys.path.insert(0, str(DESK))

OUT = DESK / "reports" / "LIMITS_CENSUS.json"
STALL = (DESK / "data" / "stall_watch.json", ROOT / "data" / "stall_watch.json")
RUNTIME = ROOT / "docs" / "research" / "runtime_state.json"
MISSED = DESK / "reports" / "MISSED_GROWTH.json"
ECON = DESK / "reports" / "DESK_ECONOMICS.json"
CLASSES = ("IMPLEMENTATION", "RESOURCE", "ACCESS", "SCIENCE", "CAPITAL")
#: Free physical memory under this share of total is a binding resource limit.
MEM_FLOOR_SHARE = 0.10
#: Disk under this many GB free is binding (the recovery drills' disk floor).
DISK_FLOOR_GB = 10.0
#: Credentials the mandate retired: absent is correct, so absence binds nothing.
RETIRED_CREDENTIALS = {
    "binance_testnet.json": "crypto-exchange venue, retired by the MT5 universe mandate",
    "binance_spot_testnet.json": "crypto-exchange venue, retired by the MT5 universe mandate",
}
#: A trading-box reading older than this is not a reading of the box now.
STALL_MAX_AGE_H = 6.0


def _json(p: Path) -> Any:
    try:
        return json.loads(p.read_text("utf-8-sig"))
    except (OSError, ValueError):
        return None


def _age_h(stamp: Any) -> float | None:
    """Hours since an ISO stamp. PowerShell writes 7 fractional digits, which Python refuses,
    so the fraction is cut to microseconds; a stamp with no offset is read as UTC."""
    m = re.match(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?(Z|[+-]\d\d:\d\d)?$",
                 str(stamp or ""))
    if not m:
        return None
    frac = (m.group(2) or "")[:7]
    off = m.group(3) or "+00:00"
    t = datetime.fromisoformat(m.group(1) + frac + ("+00:00" if off == "Z" else off))
    return (datetime.now(tz=UTC) - t).total_seconds() / 3600.0


def _row(name: str, cls: str, where: str, binding: bool | None, evidence: str,
         **kw: Any) -> dict[str, Any]:
    assert cls in CLASSES, cls
    return {"name": name, "class": cls, "where": where, "binding": binding,
            "evidence": evidence, **kw}


def resource_rows() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        import psutil  # type: ignore[import-untyped,unused-ignore]
        vm = psutil.virtual_memory()
        du = psutil.disk_usage(str(ROOT))
        host = socket.gethostname()
        tot, free = vm.total / 1024**3, vm.available / 1024**3
        out.append(_row(f"memory@{host}", "RESOURCE", "psutil (this host, now)",
                        free < MEM_FLOOR_SHARE * tot,
                        f"{free:.1f} of {tot:.1f} GB available", total_gb=round(tot, 1),
                        free_gb=round(free, 2)))
        out.append(_row(f"disk@{host}", "RESOURCE", "psutil (this host, now)",
                        du.free / 1024**3 < DISK_FLOOR_GB,
                        f"{du.free / 1024**3:.1f} GB free (floor {DISK_FLOOR_GB})",
                        free_gb=round(du.free / 1024**3, 2)))
        out.append(_row(f"cores@{host}", "RESOURCE", "psutil (this host, now)", None,
                        f"{psutil.cpu_count()} logical cores; binding is read from the "
                        "implementation rows (a budget that timed out), not guessed from load",
                        cores=psutil.cpu_count()))
    except Exception as exc:
        out.append(_row("this_host", "RESOURCE", "psutil", None,
                        f"UNMEASURED: {type(exc).__name__}"))
    sw = next((d for d in (_json(p) for p in STALL) if isinstance(d, dict)), None)
    if sw is None:
        out.append(_row("memory@trading_box", "RESOURCE", "data/stall_watch.json", None,
                        "UNMEASURED: no stall_watch on this host"))
        return out
    age_h = _age_h(sw.get("checked_at"))
    if age_h is None or age_h > STALL_MAX_AGE_H:
        out.append(_row("trading_box", "RESOURCE", "data/stall_watch.json", None,
                        f"UNMEASURED: stall_watch checked_at {sw.get('checked_at')} is "
                        f"{'unreadable' if age_h is None else f'{age_h:.0f}h old'}"))
        return out
    mem = sw.get("memory") or {}
    tot, free = mem.get("total_phys_mb"), mem.get("free_phys_mb")
    if isinstance(tot, (int, float)) and isinstance(free, (int, float)) and tot > 0:
        out.append(_row("memory@trading_box", "RESOURCE", "data/stall_watch.json",
                        free < MEM_FLOOR_SHARE * tot,
                        f"{free} of {tot} MB free at {sw.get('checked_at')}",
                        checked_at=sw.get("checked_at")))
    fg = sw.get("free_gb")
    if isinstance(fg, (int, float)):
        out.append(_row("disk@trading_box", "RESOURCE", "data/stall_watch.json",
                        fg < DISK_FLOOR_GB, f"{fg} GB free at {sw.get('checked_at')}"))
    return out


def access_rows(now: datetime) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from libs.ops import llm_seat as ls
        spend, cap, free_only = ls.month_spend_usd(now), ls.monthly_cap_usd(), ls.free_tier_only()
        out.append(_row("llm_monthly_cap", "ACCESS", "libs/ops/llm_seat.py monthly_cap_usd",
                        (not free_only) and spend >= cap,
                        f"${spend:.2f} of ${cap:.2f} this month; free tier only={free_only}"))
        left, today = ls.free_budget_left(now), ls.calls_today(now)
        out.append(_row("llm_free_daily_requests", "ACCESS",
                        "libs/ops/llm_seat.py free_budget_left", left <= 0,
                        f"{today} completions today, {left} left in the free allowance"))
    except Exception as exc:
        out.append(_row("llm_allowance", "ACCESS", "libs/ops/llm_seat.py", None,
                        f"UNMEASURED: {type(exc).__name__}: {str(exc)[:120]}"))
    try:
        spec = importlib.util.spec_from_file_location(
            "_check_credentials", ROOT / "scripts" / "check_credentials.py")
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod          # its dataclasses resolve their module by name
        spec.loader.exec_module(mod)
        inv = mod.build()
        for c in inv.get("credentials") or []:
            st, name = str(c.get("status")), Path(str(c.get("file"))).name
            if name in RETIRED_CREDENTIALS:
                out.append(_row(f"credential:{name}", "ACCESS", "LAWS universe (MT5 only)",
                                False, f"{st}; {RETIRED_CREDENTIALS[name]}", tier=c.get("tier")))
                continue
            out.append(_row(f"credential:{name}", "ACCESS",
                            "scripts/check_credentials.py (presence only)",
                            st != "OK", f"{st}; tier {c.get('tier')}",
                            tier=c.get("tier")))
    except Exception as exc:
        out.append(_row("credentials", "ACCESS", "scripts/check_credentials.py", None,
                        f"UNMEASURED: {type(exc).__name__}"))
    econ = _json(ECON)
    if isinstance(econ, dict):
        ok = econ.get("hurdle_acceptable")
        # A hurdle over a cost base with unknown lines is a floor: it can say "binding" (even
        # the floor is too heavy) but never "headroom".
        complete = bool(econ.get("cost_base_complete"))
        out.append(_row("desk_cost_base", "ACCESS", "reports/DESK_ECONOMICS.json",
                        None if ok is None else (not ok) if (complete or not ok) else None,
                        f"{econ.get('verdict')}; undeclared "
                        f"{econ.get('undeclared_line_items')}"))
    else:
        out.append(_row("desk_cost_base", "ACCESS", "reports/DESK_ECONOMICS.json", None,
                        "UNMEASURED: run scripts/run_desk_economics.py"))
    return out


def science_rows() -> list[dict[str, Any]]:
    try:
        from research import gate_policy as gp
    except Exception as exc:
        return [_row("gate_policy", "SCIENCE", "desks/mt5/research/gate_policy.py", None,
                     f"UNMEASURED: {type(exc).__name__}")]
    return [_row(f"gate:{g}", "SCIENCE", f"gate_policy {gp.VERSION}", None,
                 f"threshold {gp.THRESHOLDS.get(g) or '(spec params)'}; never lifted to buy "
                 "throughput", params=gp._PARAMS.get(g))
            for g in gp.GATES]


def capital_rows() -> list[dict[str, Any]]:
    from libs.portfolio.rails import RAILS
    doc = _json(MISSED)
    verdicts = (doc or {}).get("rails") if isinstance(doc, dict) else None
    verdicts = verdicts if isinstance(verdicts, dict) else {}
    out = []
    for r in RAILS:
        v = verdicts.get(r.name) or {}
        verdict = str(v.get("verdict") or "UNMEASURED")
        binding = (None if verdict == "UNMEASURED"
                   else verdict != "NOT_BINDING")
        out.append(_row(f"rail:{r.name}", "CAPITAL", r.where, binding,
                        f"missed_growth {verdict}"
                        + (f", {v.get('annualised_logw')} logW/yr" if "annualised_logw" in v
                           else ""), kind=r.kind, tunable=r.tunable))
    return out


def implementation_rows() -> list[dict[str, Any]]:
    doc = _json(RUNTIME)
    organs = (doc or {}).get("organs") if isinstance(doc, dict) else None
    if not isinstance(organs, list):
        return [_row("organ_budgets", "IMPLEMENTATION", "docs/research/runtime_state.json",
                     None, "UNMEASURED: no runtime attestation")]
    hit = [o.get("organ") for o in organs
           if any(t in str(o.get("last_run_outcome") or "").lower()
                  for t in ("timeout", "budget", "timed out"))]
    out = [_row(f"budget:{name}", "IMPLEMENTATION", "component resource_budget / timeout",
                True, "last run ended on its own budget or timeout") for name in hit]
    measured = sum(1 for o in organs if o.get("last_run_outcome") not in (None, "UNMEASURED"))
    out.append(_row("organ_budgets", "IMPLEMENTATION", "docs/research/runtime_state.json",
                    bool(hit) if measured else None,
                    f"{len(hit)} of {measured} organs with a recorded outcome ended on a "
                    f"budget; {len(organs) - measured} have no recorded outcome"))
    return out


def build(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(tz=UTC)
    rows = (implementation_rows() + resource_rows() + access_rows(now) + science_rows()
            + capital_rows())
    by = {c: {"rows": sum(1 for r in rows if r["class"] == c),
              "binding": sum(1 for r in rows if r["class"] == c and r["binding"] is True),
              "unmeasured": sum(1 for r in rows if r["class"] == c and r["binding"] is None)}
          for c in CLASSES}
    return {"generated_at": now.isoformat(timespec="seconds"), "host": socket.gethostname(),
            "classes": {"IMPLEMENTATION": "code imposes it; engineering lifts it",
                        "RESOURCE": "the machine; hardware or less use lifts it",
                        "ACCESS": "keys, allowances, spend; acquisition lifts it",
                        "SCIENCE": "statistical safeguard; never lifted",
                        "CAPITAL": "capital control; billed by missed_growth (Rule 1)"},
            "binding_by_class": by,
            "binding": [r for r in rows if r["binding"] is True],
            "rows": rows}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    doc = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=1, default=str), "utf-8")
    b = doc["binding_by_class"]
    print("limits census: " + "; ".join(f"{c} {v['binding']}/{v['rows']} binding"
                                        f" ({v['unmeasured']} unmeasured)"
                                        for c, v in b.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
