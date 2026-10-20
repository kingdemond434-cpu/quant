"""The kelly_survival leg is alive, and its E8 block follows the E8 book (2026-10-20).

reports/KELLY_SURVIVAL.json was last written 2026-10-11 12:19Z while the hourly cycle kept
running. `--book` solved the whole certified book BEFORE the one write; on the box its
certificate replay outran the leg's budget, so the gold block the readers need (2h expiry) was
never written. The gold block is now written first. And the E8 windows the live book does not
fund (data/CERT_BOOK_LIVE.json names gold_asia only) are 0 in the solve, never 0.0025.
"""
from __future__ import annotations

import ast
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

ks = pytest.importorskip("kelly_survival", reason="ships with the desk")
from mt5desk.kelly_sizing import load_kelly_survival  # noqa: E402

HC = _DESK / "research" / "hourly_cycle.py"
needs_worlds = pytest.mark.skipif(not ks.WORLDS.exists(), reason="no allocator worlds here")


def _book(tmp: Path, e8: dict, enabled: bool = True) -> Path:
    p = tmp / "CERT_BOOK_LIVE.json"
    p.write_text(json.dumps({"enabled": enabled, "e8": e8, "fusion": {"gold_asia": 0.05}}),
                 encoding="utf-8")
    return p


def test_enabled_windows_follow_the_book(tmp_path: Path) -> None:
    on, _ = ks.e8_enabled_windows(_book(tmp_path, {"gold_asia": 0.01, "AUDCHF_x_asia": 0.0}))
    assert on == ("asia",)
    on, _ = ks.e8_enabled_windows(_book(tmp_path, {"gold_asia": 0.01}, enabled=False))
    assert on == ks.WINDOWS
    assert ks.e8_enabled_windows(tmp_path / "absent.json")[0] == ks.WINDOWS


def test_the_live_book_funds_gold_asia_only_on_e8() -> None:
    on, src = ks.e8_enabled_windows()
    assert on == ("asia",), src


@needs_worlds
@pytest.mark.parametrize("live", [False, True])
def test_e8_never_funds_a_window_the_book_disables(tmp_path: Path, live: bool) -> None:
    book = None if live else _book(tmp_path, {"gold_asia": 0.01})
    doc = ks.solve(cert_book=book)
    e8 = doc["e8"]
    assert e8["enabled_windows"] == ["asia"]
    if e8["status"] == "OK":
        assert e8["windows"]["london_am"]["risk_frac"] == 0.0
        assert e8["windows"]["afternoon"]["risk_frac"] == 0.0
    out = tmp_path / "K.json"
    ks._write(out, doc)
    read = load_kelly_survival(out, "e8")
    if read is not None:
        assert read.get("london_am", 0.0) == 0.0 and read.get("afternoon", 0.0) == 0.0


@needs_worlds
def test_a_failing_book_solve_still_leaves_a_fresh_gold_block(tmp_path: Path,
                                                             monkeypatch) -> None:
    def boom() -> dict:
        raise TimeoutError("stand-in for the leg budget killing the certificate replay")
    monkeypatch.setattr(ks, "solve_book", boom)
    out = tmp_path / "K.json"
    with pytest.raises(TimeoutError):
        ks.main(["--book", "--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    age = (datetime.now(tz=UTC) - datetime.fromisoformat(doc["generated_at"])).total_seconds()
    assert age < 600 and "e8" in doc and "fusion" in doc


# ------------------------------------------------------------------ III.16: wired AND running
def _main_calls() -> list[ast.Call]:
    tree = ast.parse(HC.read_text(encoding="utf-8"))
    main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    return [n for n in ast.walk(main) if isinstance(n, ast.Call)]


def test_hourly_main_costs_the_kelly_survival_producer() -> None:
    found = False
    for c in _main_calls():
        if getattr(c.func, "id", None) == "_costed" and c.args and \
                isinstance(c.args[0], ast.Constant) and c.args[0].value == "kelly_survival":
            inner = [n for n in ast.walk(c.args[1]) if isinstance(n, ast.Call)
                     and getattr(n.func, "id", None) == "_producer"]
            assert inner and [a.value for a in inner[0].args[:2]] == \
                ["kelly_survival", "research/kelly_survival.py"]
            found = True
    assert found, "hourly_cycle.main has no _costed('kelly_survival', _producer(...)) leg"


def test_the_leg_is_in_the_core_plan_and_not_on_an_own_clock() -> None:
    import hourly_cycle as hc
    assert "kelly_survival" in hc.CORE_LEGS
    assert "kelly_survival" not in hc.OWN_CLOCK_LEGS
    assert hc.in_plan("kelly_survival", "core") and hc.in_plan("kelly_survival", "all")


@needs_worlds
def test_the_cycle_producer_actually_writes_the_artifact(tmp_path: Path) -> None:
    import hourly_cycle as hc
    out = tmp_path / "KELLY_SURVIVAL.json"
    res = hc._producer("kelly_survival", "research/kelly_survival.py", "--out", str(out))
    assert res.get("exit_code") == 0, res
    assert load_kelly_survival(out, "e8") is not None or \
        json.loads(out.read_text(encoding="utf-8"))["e8"]["status"] != "OK"
