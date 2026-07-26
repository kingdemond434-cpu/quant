"""Daily institutional research cycle -- the CRO everyday loop.

ONE complete cycle, run daily by Task Scheduler:
  1. run_daily_research.py   -- forward-accumulating pipeline: candidate generation + validation +
                                data archiving (feeds the research system for testing)
  2. research_cycle.py       -- regenerate the 3 state files, ROI reprioritization, calibration
  3. run_leverage_opt.py     -- recompute growth-optimal leverage per sleeve + joint
  4. run_live_combined.py    -- refresh the molded book
Then it appends a DATED entry to data/cro_cycle_log.json (bottleneck, next highest-ROI task,
deployed metrics, calibration, candidates tested) and prints the next action. Continuous process:
no terminal state except the absence of positive expected-Research-ROI work.

Each step is isolated -- one failure never aborts the cycle. Idempotent + safe to re-run.

    python scripts/daily_research_cycle.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from libs.ops.platform_paths import venv_python

_ROOT = Path(__file__).resolve().parent.parent
_PY = venv_python(_ROOT)
_LOG = _ROOT / "data" / "cro_cycle_log.json"

# ordered pipeline; (label, script, timeout_s). Heavy research first, then bookkeeping.
_STEPS = [
    ("ci_gate",           "scripts/run_ci.py",              300),
    ("recorder_watch",    "scripts/ensure_recorder.py",      60),  # data moat must never sleep
    ("stablecoin_flows",  "scripts/run_stablecoin_flows.py", 180),  # daily on-chain clock tick
    ("fred_macro",        "scripts/collect_fred_macro.py",   120),  # free US-macro (key-gated)
    ("naver_krsearch",    "scripts/collect_naver_krsearch.py", 60),  # KR attention (key-gated)
    ("root_cause",        "scripts/run_root_cause.py",       120),  # classify losses pre-reaction
    ("desk_digest",       "scripts/render_desk_digest.py",    60),  # Obsidian-readable daily brief
    ("micro_audit",       "scripts/run_micro_audit.py",      480),  # 3 cold LLMs on 24h delta
    ("cadence",           "scripts/run_cadence.py",          900),  # stage-aware review scheduler
    ("research_feed",     "scripts/collect_research_feed.py", 120),  # arXiv q-fin -> vault inbox
    ("growth_audit",      "scripts/run_growth_audit.py",       60),  # under-utilization = defect
    ("research_pipeline", "scripts/run_daily_research.py",  7200),
    ("autodiscovery",     "scripts/run_crypto_research.py", 1800),  # industrialized crypto factory
    ("state_files",       "scripts/research_cycle.py",      300),
    ("trade_forensics",   "scripts/run_trade_forensics.py",  60),  # class-bleed probe (daily)
    ("nav_attest",        "scripts/run_nav_attest.py",       60),  # hash-chained track record
    # gap-2 §3-§6: the ONE production caller for the S1 rails (naked-position reconcile, pager
    # de-risk ladder, 6h canary, numeric ramp gate, stage machine). Inert at S0/without keys --
    # but it must run daily from S0 so the rails are exercised BEFORE they are load-bearing,
    # rather than executing for the first time on the day real money is behind them.
    ("live_guard",        "scripts/run_live_guard.py",       120),
    ("listing_watch",     "scripts/run_listing_watch.py",    60),  # gap-53 data clock
    # §42(6): the CONSUMER for that clock. Collection without a promotion path is acquisition the
    # desk can never convert, so the study runs on the same cadence as the collector rather than
    # waiting for someone to remember it exists.
    ("event_study",       "scripts/run_event_study.py",     300),
    # §42: cross-venue funding on the THIN tail -- where a small book is not the worst-capitalised
    # participant. The liquid names are already screened; this starts the clock on the other end.
    ("tail_funding",      "scripts/collect_tail_funding_divergence.py", 120),
    ("kimchi_premium",    "scripts/collect_kimchi_premium.py", 90),  # gap-74 forward clock
    ("onchain_activity",  "scripts/collect_onchain_activity.py", 120),
    # licence-clean Glassnode/Coin-Metrics replacement (facts reconstructed from chain)
    ("onchain_metrics",   "scripts/collect_onchain_metrics.py", 180),  # on-chain throughput
    ("stablecoin_supply", "scripts/collect_stablecoin_supply.py", 120),  # supply momentum clock
    ("cny_premium",       "scripts/collect_cny_premium.py", 60),  # USDT/CNY P2P premium (#76)
    ("axis_shadows",      "scripts/run_axis_shadows.py",     120),  # Stage-B forward eval
    ("reject_rescore",    "scripts/run_rejection_rescore.py", 300),  # feed near-miss reject scores
    ("rejection_shadow",  "scripts/run_rejection_shadow.py",  60),  # gate-leak recovery audit
    ("cost_model",        "scripts/run_cost_model.py",      600),  # measured exec costs (daily)
    ("shadow_8h",         "scripts/run_shadow_8h.py",       420),  # 3x-obs challenger shadow
    ("leverage_opt",      "scripts/run_leverage_opt.py",    120),
    ("molded_refresh",    "scripts/run_live_combined.py",   120),
    ("git_snapshot",      "scripts/git_snapshot.py",        120),  # daily forensic code history
]


def _run(script: str, timeout: int) -> dict[str, object]:
    try:
        r = subprocess.run([_PY, script], cwd=str(_ROOT), timeout=timeout,
                           capture_output=True, text=True, check=False)
        tail = (r.stdout or r.stderr or "").strip().splitlines()[-1:] or [""]
        return {"ok": r.returncode == 0, "rc": r.returncode, "tail": tail[0][:160]}
    except subprocess.TimeoutExpired:
        return {"ok": False, "rc": "timeout", "tail": f"timeout after {timeout}s"}
    except Exception as e:
        return {"ok": False, "rc": "error", "tail": repr(e)[:160]}


def _load(p: Path, d: object) -> object:
    try:
        return json.loads(p.read_text("utf-8"))
    except (OSError, json.JSONDecodeError):
        return d


def main() -> None:
    steps: dict[str, object] = {}
    for label, script, timeout in _STEPS:
        steps[label] = _run(script, timeout)
        print(f"[{label}] {steps[label]}")

    # read resulting institutional state for the dated cycle log
    eng = _load(_ROOT / "engineering_backlog.json", {})
    state = _load(_ROOT / "research_state.json", {})
    port = _load(_ROOT / "web" / "portfolio.json", {}).get("deployed", {})
    cal = _load(_ROOT / "web" / "calibration.json", {})
    disc = _load(_ROOT / "web" / "discovery.json", {})
    nxt = eng.get("next_action")

    entry = {
        "date": datetime.now(tz=UTC).strftime("%Y-%m-%d"),
        "ts": datetime.now(tz=UTC).isoformat(),
        "steps_ok": {k: v.get("ok") for k, v in steps.items()},
        "binding_constraint": state.get("binding_constraint"),
        "next_highest_roi_task": ({"id": nxt.get("id"), "roi": nxt.get("roi")} if nxt else None),
        "open_backlog": [i.get("id") for i in eng.get("open", [])],
        "deployed": {k: port.get(k) for k in ("equity", "net_pnl", "days_live", "deployed_sharpe")},
        "calibration": {k: cal.get(k) for k in ("n_resolved", "brier", "bias_label")},
        "data_clocks": [p.get("status") for p in disc.get("pending", [])],
    }
    log = _load(_LOG, [])
    if not isinstance(log, list):
        log = []
    log.append(entry)
    _LOG.write_text(json.dumps(log[-400:], indent=2), "utf-8")

    print(f"CRO cycle {entry['date']}: next-ROI={entry['next_highest_roi_task']} "
          f"| constraint={entry['binding_constraint']}")
    if nxt is None:
        print("  no positive-ROI engineering task -> research capital = WAIT on data clocks "
              "+ scope next orthogonal free-data stream (see research_agenda.json).")


if __name__ == "__main__":
    sys.exit(main())
