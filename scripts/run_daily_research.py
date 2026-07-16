"""Daily research batch -- one entry point for the scheduler (Windows Task: QuantDaily).

Runs the forward-accumulating pipeline in order, isolating each step so one failure does not abort
the rest: (1) log broker swap rates (seeds the carry sleeve), (2) refresh the liquid crypto lake +
funding shadow, (3) cross-asset combo shadow, (4) the MT5 alpha-portfolio campaign, (5) rebuild the
dashboard scoreboard. Steps needing the MT5 terminal (1) are best-effort; the research steps run on
cached data regardless.

    python scripts/run_daily_research.py
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PY = sys.executable
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
    for label, args in _STEPS:
        print(f"\n--- {label} ---", flush=True)
        try:
            proc = subprocess.run([_PY, *args], cwd=_ROOT, timeout=1800,
                                  capture_output=True, text=True, check=False)
            tail = "\n".join(proc.stdout.strip().splitlines()[-6:])
            print(tail)
            if proc.returncode != 0:
                print(f"[stderr] {proc.stderr.strip()[-400:]}")
            results.append((label, "ok" if proc.returncode == 0 else f"exit {proc.returncode}"))
        except Exception as e:  # best-effort daily batch, never abort the chain
            results.append((label, f"error: {e!r}"[:80]))
            print(f"[error] {e!r}")
    print("\n=== summary ===")
    for label, status in results:
        print(f"  {label:34} {status}")


if __name__ == "__main__":
    main()
