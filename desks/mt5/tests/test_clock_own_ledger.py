"""Each forward clock writes its OWN ledger, named by its full key (2026-11-13): the legacy
`ledger_{sym}_{fam}_{win}.json` was shared by every parameterization and overwritten."""
from __future__ import annotations

import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
for _p in (str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import shadow_forward as sf  # noqa: E402

KEYS = [
    "GBPSEK.formula.asia#atr_n=20_entry_z=1.5_expr=['ts_backfill', 'a']",
    "GBPSEK.formula.asia#atr_n=20_entry_z=1.5_expr=['zscore', 'b']",
    "GBPSEK.formula.asia@M30#atr_n=20_entry_z=1.5_expr=['zscore', 'b']",
    "CHFNOK.carry.asia@M15#input_symbol=CHFNOK_session=ny",
    "CHFNOK.carry.asia@M15#session=ny",
]


def test_every_parameterization_gets_its_own_file() -> None:
    paths = {sf.clock_ledger_path(k, k.split(".")[0], k.split(".")[1], "asia") for k in KEYS}
    assert len(paths) == len(KEYS)
    for p in paths:
        assert p.parent == sf.CLOCK_LEDGER_DIR
        assert not set(p.name) & sf._UNSAFE_NAME and len(p.name) < 160


def test_a_simple_key_keeps_a_readable_name() -> None:
    p = sf.clock_ledger_path("CHFDKK.overnight_gap_decay.asia", "CHFDKK",
                             "overnight_gap_decay", "asia")
    assert p.name == "ledger_CHFDKK_overnight_gap_decay_asia.json"


def test_the_engine_writes_the_own_ledger_and_records_it() -> None:
    src = (DESK / "research" / "shadow_forward.py").read_text("utf-8")
    assert "clock_ledger_path(key, sym, fam, win)" in src
    assert 'st["ledger_file"]' in src
