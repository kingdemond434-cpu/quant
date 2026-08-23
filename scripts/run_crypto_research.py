"""DOMINATED (2026-08-23): this role -- the perpetual autonomous hypothesis factory -- is filled
on the MT5 desk by desks/mt5/research/research_loop.py under MT5-ResearchSupervisor, already
running. Native-crypto machinery stays in the repo per standing instruction, but is retired from
any live schedule (the 10 quant-autodiscovery-slice*.timer systemd units that ran this).

Industrialized crypto hypothesis factory over the Parquet lake -- the daily throughput engine.

Feeds the whole crypto universe (lake bars + Level-3 funding) into the generic AutoDiscoveryLab: the
same validation gauntlet, net of real perp cost, with cross-campaign DSR deflation on the cumulative
trial count. The funding_stress_reversal generator (LIQUIDITY family) is the one genuinely
crypto-native hypothesis; the price families re-test the graveyard cheaply (content-hash dedup) and
the gauntlet rejects them. Survivors expected to be few or zero -- that is the honest point.

Emits web/autodiscovery_crypto.json (dashboard) + reports/crypto_research/*.json (durable ledger).
Idempotent: after the first full cycle, dedup skips already-tested hypotheses so re-runs are cheap
and only NEW symbols / generators are tested -- safe to run every daily cycle.

    python scripts/run_crypto_research.py
"""

from __future__ import annotations

# PATH BOOTSTRAP. `python scripts/x.py` puts scripts/ on sys.path, NOT the repo root, so `libs`
# resolves only if the project happens to be pip-installed into the interpreter in use. The daily
# cycle invokes these by path. Without this the libs imports fail -- and in run_trade_forensics a
# broad `except Exception` caught exactly that and shipped {"error": "ModuleNotFoundError"} into
# the artifact, where an error string is indistinguishable from data to every reader downstream.
import sys as _sys
from pathlib import Path as _P

if str(_P(__file__).resolve().parent.parent) not in _sys.path:
    _sys.path.insert(0, str(_P(__file__).resolve().parent.parent))


import argparse
import json
from pathlib import Path

from migrations import MIGRATIONS

from libs.autodiscovery.crypto_adapter import (
    DEFAULT_FAMILIES,
    build_lab,
    load_universe,
    web_payload,
)
from libs.autodiscovery.models import Family
from libs.autodiscovery.reports import failure_analysis_report, research_report, survivor_report
from libs.data.timeframe import Timeframe
from libs.store.connection import Database
from libs.store.migrations import run_migrations

_OUT = Path("reports/crypto_research")
_WEB = Path("web/autodiscovery_crypto.json")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="data/sor_crypto.sqlite")
    parser.add_argument("--families", default=",".join(f.value for f in DEFAULT_FAMILIES))
    parser.add_argument("--timeframe", choices=("D1", "H8"), default="D1")
    parser.add_argument("--max-symbols", type=int, default=30,
                        help="cap the universe to the top-N liquid perps (0 = all)")
    parser.add_argument("--offset", type=int, default=0,
                        help="skip the top-N-offset liquid perps (chunked/parallel cycles)")
    args = parser.parse_args()

    tf = Timeframe(args.timeframe)
    limit = args.max_symbols or None
    symbols, provider = load_universe(tf, limit=limit, offset=args.offset)
    if not symbols:
        raise SystemExit(f"no crypto {tf.value} data in lake; run scripts/ingest_crypto.py first")

    families = [Family(f.strip()) for f in args.families.split(",") if f.strip()] or None
    db = Database(Path(args.db))
    run_migrations(db, MIGRATIONS)
    # `tf` is the interval `load_universe` read, so it is also the clock every stored
    # annual_sharpe is annualised on: D1 -> 365/yr, H8 -> 1095/yr (R0086).
    lab = build_lab(db, provider, timeframe=tf, families=families)

    print(f"crypto {tf.value}: {len(symbols)} liquid symbols (cap {limit}) | "
          f"families: {[f.value for f in (families or [])]}")
    result = lab.cycle(symbols)
    print(f"\n[cycle] tested={result.tested} survivors={result.survivors} "
          f"rejected={result.rejected} promoted_paper={result.promoted_to_paper} "
          f"skipped_dup={result.skipped_duplicate}")

    # PILOT INSTRUMENT (2026-07-12): record this cycle's information value + refresh the pilot
    # card. Over 30 days this measures survivors-per-1,000 -- the number that decides whether
    # scaling generation (more VPS/hardware) is EV-positive or the constraint is data/mechanism.
    from libs.research.information_value import record_factory_cycle
    card = record_factory_cycle(result.tested, result.survivors, timeframe=tf.value)
    print(f"[pilot] survivors/1000={card['survivors_per_1000']} "
          f"info_bits/exp={card.get('info_bits_per_experiment')} -> {card.get('verdict_hint')}")

    _OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "research_report": research_report(lab.store),
        "survivor_report": survivor_report(lab.store),
        "failure_analysis_report": failure_analysis_report(lab.store),
    }.items():
        (_OUT / f"{name}.json").write_text(json.dumps(payload, indent=2, default=str), "utf-8")
    _WEB.parent.mkdir(parents=True, exist_ok=True)
    _WEB.write_text(json.dumps(web_payload(lab.store, result, timeframe=tf.value),
                              indent=2, default=str), "utf-8")
    print(f"reports -> {_OUT}/ | dashboard -> {_WEB}")
    if result.survivors == 0:
        print("ZERO survivors net-of-cost (honest).")
    db.close()


if __name__ == "__main__":
    main()
