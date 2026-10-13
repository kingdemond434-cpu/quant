"""LAB STYLE SCREEN: a lab cell that re-buys a style the book owns is held, never dropped.

  * saturation is read from STYLE_NOVELTY.json's dominant_style_counts at SATURATION_SHARE;
  * a KNOWN_STYLE cell in a saturated style is held; NOVEL, unsaturated and UNMEASURED cells are
    donated, each stamped with its reading;
  * a held cell is released once its style is no longer saturated, and an absent report holds
    nothing;
  * the verdict loop credits NOVEL certified k_eff, and the lab ranking draws on it.
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lab_style as ls  # noqa: E402
import llm_lab_roles as roles  # noqa: E402

COUNTS = {"passive_window": 20, "range_breakout_12bar": 8, "trend_20d": 1}


def _report(path: Path, counts: dict[str, int], n: int = 43) -> Path:
    path.write_text(json.dumps({"dominant_style_counts": counts, "n_measured": n,
                                "novel_threshold": 0.5}))
    return path


#: A stand-in for style_novelty: the row's params say what its projection reads.
def _fake_sn() -> Any:
    return SimpleNamespace(
        style_matrix=lambda close, index, sigs, high=None, low=None: (sigs, None),
        project=lambda y, X: y)


@pytest.fixture()
def wired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    import pandas as pd
    monkeypatch.setattr(ls, "_bars", lambda sym, d: pd.DataFrame({"close": [1.0, 1.1]}))
    monkeypatch.setattr(ls, "_family", lambda name: (lambda df, **p: dict(p["reads"]))
                        if name == "exogenous_conditioner" else None)
    return tmp_path


def _row(cid: str, nov: float | None, dom: str | None) -> dict[str, Any]:
    reads = ({"status": "MEASURED", "novelty_return": nov, "dominant_style": dom, "n": 80}
             if nov is not None else {"status": "UNMEASURED", "why": "short"})
    return {"cell_id": cid, "family": "exogenous_conditioner", "symbol": "USDCNH",
            "params": {"reads": reads}, "lab": "cb_tone"}


def test_saturation_is_a_share_of_the_measured_certificates(tmp_path: Path) -> None:
    sat = ls.saturation(_report(tmp_path / "s.json", COUNTS))
    assert sat["saturated"] == ["passive_window", "range_breakout_12bar"]
    assert ls.saturation(tmp_path / "absent.json")["status"] == "UNMEASURED"


def test_known_styles_the_book_owns_are_held_and_everything_else_donates(wired: Path) -> None:
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    rows = [_row("passive", 0.1, "passive_window"), _row("novel", 0.8, "passive_window"),
            _row("trend", 0.2, "trend_20d"), _row("unmeasured", None, None),
            {"cell_id": "nofam", "family": "nope", "symbol": "X", "params": {}}]
    out, summary = ls.screen(rows, report=rep, held_path=held, sn=_fake_sn())
    by = {r["cell_id"]: r["style_screen"]["verdict"] for r in out}
    assert by == {"novel": "NOVEL", "trend": "KNOWN_STYLE", "unmeasured": "UNMEASURED",
                  "nofam": "UNMEASURED"}
    assert summary["held"] == 1 and list(json.loads(held.read_text())) == ["passive"]
    # Nothing is lost: four donated, one held, five in.
    assert len(out) + summary["held_total"] == len(rows)


def test_a_held_cell_is_released_when_its_style_stops_being_saturated(wired: Path) -> None:
    rep, held = _report(wired / "s.json", COUNTS), wired / "held.json"
    ls.screen([_row("passive", 0.1, "passive_window")], report=rep, held_path=held,
              sn=_fake_sn())
    assert ls.release(report=rep, held_path=held) == ([], 1)
    _report(rep, {"trend_20d": 30, "passive_window": 2})
    freed, still = ls.release(report=rep, held_path=held)
    assert [r["cell_id"] for r in freed] == ["passive"] and still == 0
    assert "released" in freed[0]["style_screen"] and json.loads(held.read_text()) == {}


def test_no_style_report_holds_nothing(wired: Path) -> None:
    out, summary = ls.screen([_row("passive", 0.1, "passive_window")],
                             report=wired / "absent.json", held_path=wired / "h.json",
                             sn=_fake_sn())
    assert len(out) == 1 and summary["held"] == 0 and not (wired / "h.json").exists()


def test_without_style_novelty_every_cell_is_unmeasured_and_donated(
        wired: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "style_novelty", None)
    out, _ = ls.screen([_row("passive", 0.1, "passive_window")],
                       report=_report(wired / "s.json", COUNTS), held_path=wired / "h.json")
    assert out[0]["style_screen"]["verdict"] == "UNMEASURED"
    assert "#377" in out[0]["style_screen"]["why"]


def test_a_spent_budget_never_holds_a_row(wired: Path) -> None:
    out, summary = ls.screen([_row("passive", 0.1, "passive_window")], deadline=0.0,
                             report=_report(wired / "s.json", COUNTS),
                             held_path=wired / "h.json", sn=_fake_sn())
    assert len(out) == 1 and summary["not_reached"] == 1 and summary["held"] == 0


def test_the_verdict_loop_credits_novel_certified_keff(tmp_path: Path,
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    donate = tmp_path / "donate"
    donate.mkdir()
    rows = []
    for lab, v in (("N", "NOVEL"), ("S", "KNOWN_STYLE"), ("U", None)):
        for i in range(4):
            r: dict[str, Any] = {"cell_id": f"{lab}{i}", "lab": lab, "model": "m",
                                 "symbol": "USDCNH", "family": "exogenous_conditioner"}
            if v:
                r["style_screen"] = {"verdict": v}
            rows.append(r)
    (donate / "discoveries_x.json").write_text(json.dumps({"discoveries": rows}))
    ledger = tmp_path / "verdicts.jsonl"
    ledger.write_text("\n".join(json.dumps({"cell": r["cell_id"], "passed": True})
                                for r in rows) + "\n")
    monkeypatch.setattr(roles, "_keff", lambda cells: ({c["cid"]: 1.0 for c in cells}, "test"))
    doc = roles.verdict_loop(ledger, donate, [(x, "m") for x in "NSU" for _ in range(4)],
                             tmp_path / "credit.json")
    labs = doc["labs"]
    assert [labs[x]["keff"] for x in "NSU"] == [4.0, 4.0, 4.0]
    assert [labs[x]["novel_keff"] for x in "NSU"] == [4.0, 0.0, 2.0]
    assert labs["S"]["styles"] == {"KNOWN_STYLE": 4}
    rng = random.Random(5)  # noqa: S311 - not crypto
    firsts = [roles.thompson(labs, ["S", "N"], rng)[0] for _ in range(300)]
    assert firsts.count("N") > 250, "a lab of new styles outranks one re-buying owned styles"


def test_the_inventors_are_told_which_styles_the_book_owns(tmp_path: Path) -> None:
    line = ls.prompt_line(_report(tmp_path / "s.json", COUNTS))
    assert "passive_window (20)" in line and "trend_20d" not in line
    assert "UNMEASURED" in ls.prompt_line(tmp_path / "absent.json")
