"""Daily research batch -- CRYPTO-ONLY, spawned by the always-on executor.

Runs the forward-accumulating pipeline in order, isolating each step so one failure does not abort
the rest. The authoritative step list is `_STEPS` below -- read that, not this paragraph.

THIS DOCSTRING USED TO DESCRIBE A DIFFERENT PROGRAM (R0421, corrected 2026-08-13). It advertised a
five-step chain built around "(4) the MT5 alpha-portfolio campaign" and a Windows Task scheduler,
while the code 40 lines below has been crypto-only for months and says so in its own comment
("MT5 abandoned."). Three of the steps it named no longer exist. A stale docstring is how a dead
path keeps looking alive: it is the first thing a reader trusts and the last thing anyone updates,
and here it survived the deletion of the very scripts it pointed at.

    python scripts/run_daily_research.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PY = sys.executable
# R0258: best-effort is right for the CHAIN, but a swallowed step failure killed the flagship
# cash-carry forward clock for a full day with zero alarm. Every run now leaves a machine-readable
# status artifact that run_alerts.py reads on its watchdog tick and PAGES on failed steps.
_STATUS = _ROOT / "data" / "research_chain_status.json"


def _write_status(failed: list[dict[str, object]], total: int) -> None:
    """Atomic status drop for the pager (same-dir tmp + os.replace, the run_deadman_switch.py
    idiom): the alerts reader must see either the whole old file or the whole new one, never a
    torn write. Best-effort -- a status-write failure must never abort the research chain."""
    payload = {
        "generated": datetime.now(tz=UTC).isoformat(),
        "runner": "run_daily_research",
        "steps_total": total,
        "failed": failed,
    }
    try:
        _STATUS.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATUS.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), "utf-8")
        os.replace(tmp, _STATUS)
    except OSError as e:
        print(f"[status-write-failed] {e!r}"[:160])
# Crypto-ONLY research chain. Data collection (OI/LS/taker/breadth/regime) is now owned by the
# always-on executor's flywheel, so this is PURE RESEARCH -- spawned daily by the executor (it no
# longer depends on the fragile QuantDaily scheduled task). MT5 abandoned.
_STEPS = [
    ("enrich crypto lake (basis/flow)", ["scripts/ingest_crypto_enriched.py", "--top", "80"]),
    ("funding forward shadow", ["scripts/run_shadow_forward.py"]),
    ("crypto-native portfolio", ["scripts/run_crypto_portfolio.py"]),
    ("autonomous edge discovery", ["scripts/run_discovery.py"]),
    ("regime allocation (shadow tilt)", ["scripts/run_regime_allocation.py"]),
    ("dynamic capital allocation", ["scripts/run_allocation.py"]),
    ("alpha lifecycle governance", ["scripts/run_lifecycle.py"]),
    ("alpha registry (persist sleeves)", ["scripts/run_alpha_registry.py"]),
    ("factor risk model (PCA decomposition)", ["scripts/run_factor_model.py"]),
    ("alpha tournament (capital competition)", ["scripts/run_tournament.py"]),
    ("derivative shadow (OI div / L-S contrarian)", ["scripts/run_derivative_shadow.py"]),
    ("derivative historical backtest (~30d hourly)", ["scripts/run_derivative_backtest.py"]),
    ("free signals (F&G / dominance / HL funding / basis)", ["scripts/collect_free_signals.py"]),
    ("free-data gauntlet (Fear&Greed, real history)", ["scripts/run_freedata_backtest.py"]),
    ("hyperliquid cross-venue funding (archive)", ["scripts/collect_hyperliquid_funding.py"]),
    ("variance overlays (vol-target + beta-hedge)", ["scripts/run_overlay_backtest.py"]),
    ("crypto-firm alphas (reversal/leadlag/illiq)", ["scripts/run_firm_alphas_backtest.py"]),
    ("cross-exchange dispersion (new family)", ["scripts/run_crossexchange_backtest.py"]),
    ("options VRP (Deribit DVOL, new family)", ["scripts/run_options_vrp_backtest.py"]),
    ("cash-and-carry (firm-grade, spot+perp)", ["scripts/run_cashcarry_backtest.py"]),
    ("cash-and-carry forward shadow", ["scripts/run_cashcarry_shadow.py"]),
    ("combined book (perp + cash-carry, one account)", ["scripts/run_combined_stats.py"]),
    ("molded live account (both testnets)", ["scripts/run_live_combined.py"]),
    ("capital & sizing plan (net profit, gated)", ["scripts/run_capital_plan.py"]),
    ("profit-capture analysis", ["scripts/run_capture_analysis.py"]),
    ("cross-sleeve allocation (HRP vs equal, gated)", ["scripts/run_sleeve_alloc.py"]),
    ("emit crypto target portfolio", ["scripts/run_crypto_target.py"]),
    ("crypto forward shadow (90-day run)", ["scripts/run_crypto_shadow.py"]),
    ("trend forward shadow (majors TS-mom, 90d)", ["scripts/run_trend_shadow.py"]),
    ("trend regime-gated challenger (90d)", ["scripts/run_trend_regime_shadow.py"]),
    ("edge-gated leverage (size to validated edge)", ["scripts/run_edge_gated_leverage.py"]),
    ("rebuild scoreboard", ["scripts/build_scoreboard.py"]),
    ("factory status (info-advantage score)", ["scripts/run_factory_status.py"]),
    ("data-pipeline health check", ["scripts/data_health.py"]),
]


def main() -> None:
    print(f"=== QuantDaily {datetime.now(tz=UTC).isoformat()} ===")
    results: list[tuple[str, str]] = []
    failed: list[dict[str, object]] = []
    for label, args in _STEPS:
        print(f"\n--- {label} ---", flush=True)
        try:
            proc = subprocess.run([_PY, *args], cwd=_ROOT, timeout=1800,
                                  capture_output=True, text=True, check=False)
            tail = "\n".join(proc.stdout.strip().splitlines()[-6:])
            print(tail)
            if proc.returncode != 0:
                print(f"[stderr] {proc.stderr.strip()[-400:]}")
                failed.append({"step": label, "rc": proc.returncode,
                               "tail": (proc.stderr.strip() or proc.stdout.strip())[-400:]})
            results.append((label, "ok" if proc.returncode == 0 else f"exit {proc.returncode}"))
        except Exception as e:  # best-effort daily batch, never abort the chain
            results.append((label, f"error: {e!r}"[:80]))
            failed.append({"step": label, "rc": "error", "tail": repr(e)[:400]})
            print(f"[error] {e!r}")
    _write_status(failed, len(_STEPS))
    print("\n=== summary ===")
    for label, status in results:
        print(f"  {label:34} {status}")
    if failed:
        # last stdout line ON PURPOSE: daily_research_cycle._run keeps exactly this line as the
        # step tail, so the outer cycle's own status artifact names the inner failures too.
        print(f"FAILED steps ({len(failed)}/{len(_STEPS)}): "
              + "; ".join(str(f["step"]) for f in failed))
        raise SystemExit(1)  # R0258: nonzero exit so callers that DO look see the truth


if __name__ == "__main__":
    main()
