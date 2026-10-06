"""Readers use the live state, never the stale desk-root copies, and say UNMEASURED/STALE by name.

MEASURED 2026-10-06: seven JSON files at the desk root (sync_marker, gateway_state, hunt11,
mech_battery, mech_split, portfolio_projection, regime_state) were committed by the retired Dell
sync on 2026-08-17 and are written by nothing since. Their live writers write under data/ or
reports/. Two readers still read the root copies:

    research/swap_exposure.py   BASE / "portfolio_projection.json"  (the projection writes reports/)
    scripts/check_gold_live.py  BASE / "gateway_state.json" FIRST   (the gateway writes data/)

so the swap verdict was measured on an August book and the arm check answered `armed` from August.
"""
from __future__ import annotations

import ast
import json
import os
import sys
from pathlib import Path

import pytest

DESK = Path(__file__).resolve().parents[1]
REPO = DESK.parent.parent
for _p in (str(DESK), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

STALE_ROOT = ("sync_marker", "gateway_state", "hunt11", "mech_battery", "mech_split",
              "portfolio_projection", "regime_state")


def _desk_root_reads(src: str) -> list[tuple[int, str]]:
    """`<BASE|DESK> / "<stale>.json"` with nothing between the desk and the file name."""
    hits = []
    for n in ast.walk(ast.parse(src)):
        if (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                and isinstance(n.left, ast.Name) and n.left.id in {"BASE", "DESK"}
                and isinstance(n.right, ast.Constant)
                and n.right.value in {f"{s}.json" for s in STALE_ROOT}):
            hits.append((n.lineno, n.right.value))
    return hits


def _desk_modules() -> list[Path]:
    """Modules whose BASE/DESK is the desk directory (research/, scripts/, mt5desk/, side_channels/)."""
    out = []
    for sub in ("research", "scripts", "mt5desk", "side_channels"):
        out += list((DESK / sub).glob("*.py"))
    return out


def test_no_desk_module_reads_a_stale_desk_root_state_file() -> None:
    offenders = []
    for p in _desk_modules():
        try:
            src = p.read_text("utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "Path(__file__).resolve().parent.parent" not in src:
            continue  # BASE is not the desk directory here
        offenders += [f"{p.relative_to(DESK)}:{ln} {name}" for ln, name in _desk_root_reads(src)]
    assert not offenders, offenders


# --- swap_exposure ------------------------------------------------------------------------------

@pytest.fixture()
def swap():
    import research.swap_exposure as m
    return m


def test_swap_exposure_reads_the_live_writer_s_path(swap) -> None:
    assert swap.PROJECTION == DESK / "reports" / "portfolio_projection.json"
    src = (DESK / "research" / "portfolio_projection.py").read_text("utf-8")
    assert '(BASE / "reports" / "portfolio_projection.json").write_text(' in src


def test_absent_projection_is_unmeasured_never_the_root_copy(swap, tmp_path: Path) -> None:
    st = swap.projection_status(tmp_path / "reports" / "portfolio_projection.json")
    assert st["state"] == "UNMEASURED" and st["cells"] is None
    assert "absent" in st["why"]


def test_old_projection_is_stale(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text(json.dumps({"rows": [{"name": "x"}]}), encoding="utf-8")
    old = p.stat().st_mtime - swap.PROJECTION_MAX_AGE_S - 60
    os.utime(p, (old, old))
    st = swap.projection_status(p)
    assert st["state"] == "STALE" and st["cells"] is None
    assert st["age_hours"] > swap.PROJECTION_MAX_AGE_S / 3600.0


def test_fresh_projection_is_read(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text(json.dumps({"rows": [{"name": "x"}]}), encoding="utf-8")
    st = swap.projection_status(p)
    assert st["state"] == "OK" and st["cells"] == [{"name": "x"}]


def test_unreadable_projection_is_unmeasured(swap, tmp_path: Path) -> None:
    p = tmp_path / "portfolio_projection.json"
    p.write_text("{not json", encoding="utf-8")
    assert swap.projection_status(p)["state"] == "UNMEASURED"


def test_main_names_the_outcome_in_the_artifact(swap, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(swap, "PROJECTION", tmp_path / "absent.json")
    monkeypatch.setattr(swap, "OUT", tmp_path / "swap_exposure.json")
    monkeypatch.setattr(sys, "argv", ["swap_exposure.py"])
    assert swap.main() == 3
    art = json.loads((tmp_path / "swap_exposure.json").read_text("utf-8"))
    assert art["state"] == "UNMEASURED" and art["rows"] == [] and art["why"]


# --- check_gold_live ----------------------------------------------------------------------------

def _gold_live():
    """Loaded by file: the repo root also has a `scripts` package, so a name import is ambiguous."""
    import importlib.util  # noqa: PLC0415

    spec = importlib.util.spec_from_file_location(
        "_check_gold_live_under_test", DESK / "scripts" / "check_gold_live.py")
    assert spec and spec.loader
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_check_gold_live_reads_only_the_gateway_s_own_state() -> None:
    m = _gold_live()
    assert m.GATEWAY_STATE == DESK / "data" / "gateway_state.json"


def test_check_gold_live_names_absent_state_unmeasured(tmp_path: Path, monkeypatch,
                                                       capsys) -> None:
    m = _gold_live()
    monkeypatch.setattr(m, "DATA", tmp_path)
    monkeypatch.setattr(m, "GATEWAY_STATE", tmp_path / "gateway_state.json")
    rc = m.main([])
    out = capsys.readouterr().out
    assert rc == 1
    assert "armed is UNMEASURED" in out
    assert "gateway_state armed UNMEASURED" in out
