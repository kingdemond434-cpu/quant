"""The nine side-channel seats the box measured DEAD on 2026-11-24 each name a living heir (I11)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: The channels the box's 2026-11-05 runner allowed, so the seats that kept producing there.
OLD_ALLOW = {"cot", "central_bank", "weather", "github", "seasonality", "correlations"}
DEAD_ON_BOX = ("aaii", "earnings", "fear_greed", "google_trends", "investing", "sec_edgar",
               "shipping", "tradingview", "youtube")


def _load():
    spec = importlib.util.spec_from_file_location("cpy_repl", ROOT / "scripts" /
                                                  "check_producer_yield.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cpy_repl"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_every_dead_side_channel_seat_names_an_heir_the_old_runner_kept_alive() -> None:
    mod = _load()
    for seat in DEAD_ON_BOX:
        text = mod.REPLACEMENTS.get(seat)
        assert text, f"{seat} has no declared replacement"
        heir = mod.replacement_target(text)
        assert heir in OLD_ALLOW, f"{seat} -> {heir}, not a channel the box ran"
        assert heir not in DEAD_ON_BOX


def test_the_current_runner_allows_every_dead_seat_again() -> None:
    cmd = (ROOT / "ops" / "run_side_channel_miners.cmd").read_text(encoding="utf-8")
    line = next(ln for ln in cmd.splitlines() if "QUANT_MINERS_ALLOW=" in ln)
    allowed = set(line.split("=", 1)[1].strip('"').split(","))
    assert set(DEAD_ON_BOX) <= allowed
    assert {"china", "reddit"} <= allowed
