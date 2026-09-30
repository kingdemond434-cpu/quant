"""The economic-rationale grade is a TAG, never a gate, and its contract is measured.

`research/rationale_grade.py` grades each candidate on mechanism / payer / constraint. These pin
the grading rules (boilerplate never counts, "nobody is compelled" is no payer), that tagging
only ADDS keys, that the fast admission screen's admissible population is identical with or
without the tag (mining never shrinks), and that the contract reports cert rate by grade with
Wilson intervals and an honest verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_DESK / "research"), str(_DESK), str(_ROOT), str(_DESK / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import rationale_grade as RG  # noqa: E402

FULL = {
    "symbol": "EURUSD", "family": "fx_fixing_reversal", "params": {},
    "mechanism_note": "benchmark-tracking funds must buy at the 4pm fix and dealers pre-hedge "
                      "the flow, pushing the price away from fair value into the fix",
    "payer": "passive funds mandated to execute at the published fix",
    "constraint": "dealer balance-sheet limits cap how much fix flow can be warehoused",
}


def test_all_three_from_the_cell_is_grade_a() -> None:
    g = RG.grade(FULL)
    assert g["grade"] == "A" and g["grade_cell_only"] == "A"
    assert all(c["source"] == "cell" for c in g["components"].values())


def test_boilerplate_never_counts() -> None:
    for note in ("relative_value_dislocation", "unknown", "price only", "",
                 "search population symreg over the desk's own grammar",
                 "source supplied exact recipe", "trend stuff"):
        g = RG.grade({"symbol": "EURUSD", "family": "zz_unmapped", "mechanism_note": note,
                      "payer": "unknown", "constraint": "none"}, use_registry=False)
        assert g["grade"] == "NONE", note


def test_genome_slots_count_as_the_cells_own_fields() -> None:
    row = {"symbol": "EURZAR", "family": "zz_unmapped", "mechanism_note": "breakout_liquidity",
           "params": {"mechanism_genome": {"actor": "session_participants",
                                           "constraint": "overnight_risk_limits"}}}
    g = RG.grade(row, use_registry=False)
    assert g["grade"] == "B"
    assert g["components"]["mechanism"]["present"] is False


def test_constraint_and_payer_clauses_inside_the_sentence() -> None:
    row = {"symbol": "XAUUSD", "family": "zz_unmapped",
           "mechanism_note": "forced selling from margin calls and stop cascades supplies at "
                             "prices unrelated to value; liquidated holders cannot wait"}
    g = RG.grade(row, use_registry=False)
    assert g["components"]["payer"]["source"] == "cell_text"
    assert g["components"]["constraint"]["source"] == "cell_text"
    assert g["grade"] == "A"


def test_registry_lends_mechanism_and_payer_but_never_a_constraint() -> None:
    row = {"symbol": "EURUSD", "family": "carry", "mechanism_note": "carry"}
    g = RG.grade(row)
    assert g["grade_cell_only"] == "NONE"
    assert g["components"]["constraint"]["present"] is False
    assert g["grade"] in ("B", "C", "NONE")
    for c in ("mechanism", "payer"):
        if g["components"][c]["present"]:
            assert g["components"][c]["source"].startswith("registry:")


def test_nobody_is_compelled_is_not_a_payer() -> None:
    from libs.research import mechanism_census as mc
    compulsion_free = [c for c in mc.TAXONOMY if c.payer.lower().startswith("nobody is compelled")]
    assert compulsion_free, "the census names compulsion-free classes"
    cls = compulsion_free[0]
    row = {"symbol": "EURUSD", "family": "zz_unmapped", "mechanism_note": cls.signatures[0]}
    g = RG.grade(row)
    if g["census_class"] == cls.id:
        assert g["components"]["payer"]["present"] is False


def test_tag_only_adds_keys_and_never_raises_on_junk() -> None:
    row = dict(FULL)
    before = dict(row)
    RG.tag(row)
    assert {k: row[k] for k in before} == before
    assert row["rationale_grade"] == "A"
    assert RG.grade("not a row")["grade"] == "NONE"          # type: ignore[arg-type]
    assert RG.best("C", "A") == "A" and RG.best("NONE", "B") == "B"


def test_fast_admission_admits_exactly_the_same_cells_with_the_tag(monkeypatch) -> None:
    """Mining never shrinks: the tag rides on the spec and no refusal path reads it."""
    from research import fast_admission as fa

    class _Stub:
        @staticmethod
        def timeframe_of(params, family=""):
            return str((params or {}).get("timeframe") or "H1")

        @staticmethod
        def partition_at_economic_prior(specs, meta):
            return [s for s in specs if s["sym"] in meta], [
                {"sym": s["sym"], "terminal_gate": "symbol_eligibility"}
                for s in specs if s["sym"] not in meta]

    monkeypatch.setitem(sys.modules, "external_gauntlet", _Stub)
    meta = {"EURUSD": {}, "XAUUSD": {}}
    rows = [dict(FULL), {"symbol": "XAUUSD", "family": "carry", "params": {"rr": 2}},
            {"symbol": "XAUUSD", "family": "zz_unmapped", "mechanism_note": "unknown"},
            {"symbol": "NOTREAL", "family": "carry"}]
    tagged = fa.screen([dict(r) for r in rows], meta)

    class _Flat:
        GRADES = RG.GRADES
        census = staticmethod(RG.census)
        best = staticmethod(RG.best)

        @staticmethod
        def grade(row):
            return {"grade": "NONE", "grade_cell_only": "NONE"}

    monkeypatch.setitem(sys.modules, "rationale_grade", _Flat)
    flat = fa.screen([dict(r) for r in rows], meta)
    strip = ("rationale_grade", "rationale_grade_cell_only")
    assert [{k: v for k, v in s.items() if k not in strip} for s in tagged["admissible"]] == \
        [{k: v for k, v in s.items() if k not in strip} for s in flat["admissible"]]
    assert tagged["admissible_cells"] == flat["admissible_cells"] == 3
    grades = {s["family"]: s["rationale_grade"] for s in tagged["admissible"]
              if s["sym"] == "EURUSD"}
    assert grades["fx_fixing_reversal"] == "A"
    assert sum(tagged["rationale_grades"]["admissible_cells"].values()) == 3


def test_contract_reports_cert_rate_by_grade_with_wilson(tmp_path: Path) -> None:
    from frontier_identity import cell_id
    good = [dict(FULL, symbol=s) for s in ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD")]
    bare = [{"symbol": s, "family": "zz_unmapped", "params": {"i": i}, "mechanism_note": "x"}
            for i, s in enumerate(["EURUSD"] * 6)]
    ids = [cell_id({"sym": r["symbol"], "family": r["family"], "params": r.get("params") or {}})
           for r in good + bare]
    seen = tmp_path / "seen.json"
    seen.write_text(json.dumps(dict.fromkeys(ids, "2026-09-01")), "utf-8")
    report = tmp_path / "surv.json"
    report.write_text(json.dumps({"survivors": {ids[0]: {"cell": ids[0]},
                                                ids[1]: {"cell": ids[1]}}}), "utf-8")
    doc = RG.contract(rows=good + bare, seen=seen, report=report, canon=tmp_path / "no.json")
    assert doc["status"] == "MEASURED"
    a = doc["cert_rate_by_grade"]["A"]
    assert a == {"judged": 4, "certified": 2, "cert_rate": 0.5, "wilson95": RG.wilson(2, 4)}
    assert doc["cert_rate_by_grade"]["NONE"]["judged"] == 6
    assert doc["cert_rate_by_grade"]["NONE"]["certified"] == 0
    assert isinstance(doc["verdict"], str) and doc["verdict"]


def test_contract_without_history_is_unmeasured(tmp_path: Path) -> None:
    doc = RG.contract(rows=[FULL], seen=tmp_path / "a.json", report=tmp_path / "b.json",
                      canon=tmp_path / "c.json")
    assert doc["status"] == "UNMEASURED"
