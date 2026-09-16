"""The novelty gate convicts clones BEFORE a trial is spent, and never convicts on an absence.

    python -m pytest desks/mt5/tests/test_novelty_gate.py -q -p no:cacheprovider

WHAT IS PINNED HERE, and why each property is the one that decides whether the gate is honest:

  1. A PARAMETER STEP IS A CLONE, AND THE CLONE'S TWIN IS NAMED. `rr=1.50` and `rr=1.55` on one
     instrument are one bet charged to the family-wise error budget twice. The verdict names the
     incumbent rather than rejecting the candidate, because which of a pair survives is the
     caller's decision -- the desk has already lost the better copy to a novelty rule once.
  2. A DIFFERENT INSTRUMENT WITH DIFFERENT INPUTS IS NOVEL. One economically meaningful
     difference is enough; the gate is an anti-homogeneity filter, not a throttle.
  3. AN UNMEASURABLE DIMENSION NEVER CONVICTS AND NEVER ACQUITS (LAWS L1.28a). A pre-test
     candidate has no forward record by construction, so `returns` is usually absent -- and an
     absent correlation must not read as "the same" OR as "different". The same rule refuses a
     series correlated against ITSELF: a candidate with no ledger of its own resolves to its
     incumbent's, which read 1.00 on three of the first three hundred real docket rows before the
     source check was added -- a conviction manufactured out of one file.
  4. A MEASURED DIMENSION OUTRANKS A STRUCTURAL RULE. Where the realised returns disagree, the
     parameter-region conviction is overturned, because a measurement beats a heuristic.
  5. THE ARTIFACT IS WRITTEN, AND --dry-run WRITES NOTHING. Unwired or idle is a defect (III.16):
     a gate that leaves no artifact cannot be audited and did not run.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

DESK = Path(__file__).resolve().parent.parent
RESEARCH = DESK / "research"
if str(RESEARCH) not in sys.path:
    sys.path.insert(0, str(RESEARCH))
if str(DESK.parent.parent) not in sys.path:
    sys.path.insert(0, str(DESK.parent.parent))

import novelty_gate as ng  # noqa: E402

INCUMBENT = {
    "sym": "XAUUSD",
    "cell": "XAUUSD.session_range_breakout.rr=1.5_wb=12",
    "shadow_spec": {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
                    "params": {"rr": 1.5, "wait_bars": 12}},
}
SLEEVE = {"name": "eur_carry_asia", "symbol": "EURNOK", "family": "carry", "session": "asia",
          "params": {"input_symbol": "EURNOK"}, "status": "LIVE"}
JUDGED = {"at": "2026-09-15T04:37:37+00:00", "cell": "AUDCAD.overnight_gap_decay.p=deadbeef0",
          "sym": "AUDCAD", "family": "overnight_gap_decay", "passed": False}


def _library(monkeypatch: Any, tmp_path: Path, *, survivors: Any = None, sleeves: Any = None,
             judged: Any = None) -> Path:
    """Point every path constant at tmp_path and lay down a synthetic library."""
    surv = tmp_path / "UNIVERSAL_SURVIVORS.json"
    slv = tmp_path / "sleeves.json"
    ver = tmp_path / "gate_verdict_ledger.jsonl"
    shadow = tmp_path / "shadow"
    shadow.mkdir(exist_ok=True)
    rows = {f"hunt.{i}": r for i, r in enumerate(survivors if survivors is not None
                                                 else [INCUMBENT])}
    surv.write_text(json.dumps({"n": len(rows), "survivors": rows}), encoding="utf-8")
    slv.write_text(json.dumps({"sleeves": sleeves if sleeves is not None else [SLEEVE]}),
                   encoding="utf-8")
    ver.write_text("\n".join(json.dumps(r) for r in (judged if judged is not None else [JUDGED])),
                   encoding="utf-8")
    monkeypatch.setattr(ng, "SURVIVORS", surv)
    monkeypatch.setattr(ng, "SLEEVES", slv)
    monkeypatch.setattr(ng, "VERDICTS", ver)
    monkeypatch.setattr(ng, "SHADOW_DIR", shadow)
    monkeypatch.setattr(ng, "OUT", tmp_path / "NOVELTY_GATE.json")
    return shadow


def _ledger(shadow: Path, name: str, rs: list[float]) -> Path:
    """A shadow ledger in the desk's own shape: entry_time + r_multiple per trade."""
    path = shadow / name
    path.write_text(json.dumps([
        {"entry_time": f"2026-08-{1 + i // 24:02d} {i % 24:02d}:00:00+00:00", "r_multiple": r}
        for i, r in enumerate(rs)]), encoding="utf-8")
    return path


# ------------------------------------------------------------ 1. the parameter step is a clone

def test_a_parameter_twin_is_redundant_and_the_twin_is_named(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    v = ng.admit({"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
                  "params": {"rr": 1.55, "wait_bars": 12}}, lib)

    assert v.verdict == "REDUNDANT"
    assert v.novel is False
    assert bool(v) is False
    # THE TWIN IS NAMED. A verdict that convicts without saying what it duplicates cannot be
    # acted on: the caller has to be able to choose which of the pair survives.
    assert v.twin == "hunt.0"
    assert "sweep step" in v.why
    assert v.dims["feature"] == 1.0


def test_a_parameter_region_needs_the_same_family_symbol_and_chart(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    # The SAME parameters on a different chart are a different cell: the chart is an input.
    v = ng.admit({"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
                  "params": {"rr": 1.5, "wait_bars": 12, "timeframe": "M5"}}, lib)

    assert v.verdict == "NOVEL"
    assert "chart:M5" in ng.features_of(ng._member(
        {"symbol": "XAUUSD", "family": "x", "params": {"timeframe": "M5"}}))
    # ... and a parameter three times the incumbent's is outside the 10% region.
    assert ng.param_region({"rr": 1.5}, {"rr": 1.55}) is True
    assert ng.param_region({"rr": 1.5}, {"rr": 4.5}) is False
    assert ng.param_region({"rr": 1.5}, {"rr": 1.5, "wait_bars": 12}) is False


# --------------------------------------------- 2. a different instrument with different inputs

def test_a_same_family_different_symbol_cell_with_different_features_is_novel(monkeypatch,
                                                                             tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    v = ng.admit({"symbol": "EURUSD", "family": "session_range_breakout", "selector": "london",
                  "params": {"rr": 1.5, "wait_bars": 12, "peer_symbol": "USDJPY"}}, lib)

    assert v.verdict == "NOVEL"
    assert v.novel is True
    assert bool(v) is True
    assert v.dims["feature"] is not None and v.dims["feature"] < ng.TWIN_AT
    # The nearest member is still NAMED on a novel verdict -- it is the closest thing the library
    # holds, and `why` says why it is nevertheless distant.
    assert v.twin == "hunt.0"
    assert "distant" in v.why


def test_features_are_derived_from_the_family_name_and_its_parameter_keys():
    disc_a = ng._member({"symbol": "AUDCAD", "family": "discovered",
                         "params": {"feature": "atr_percentile", "band": [0.9, 1.0],
                                    "horizon": 12, "side": 1}})
    disc_b = ng._member({"symbol": "AUDCAD", "family": "discovered",
                         "params": {"feature": "spread_zscore", "band": [0.9, 1.0],
                                    "horizon": 12, "side": 1}})
    fa, fb = ng.features_of(disc_a), ng.features_of(disc_b)

    # THE `discovered` FAMILY CARRIES ITS PRIMITIVE IN `params["feature"]`. Without reading it,
    # 17,354 of the docket's 21,099 rows would share one identical feature set on any one
    # instrument and the whole generator would read as a single bet.
    assert "primitive:atr_percentile" in fa
    assert "primitive:spread_zscore" in fb
    assert ng._jaccard(fa, fb) < ng.TWIN_AT
    # The side is a sign, not an input, and neither is the chart's name in the params.
    assert not any(f.startswith("param:side") for f in fa)
    # An exogenous input is named as one, and an unknown key is carried rather than dropped.
    assert "swap_terms" in ng.features_of(ng._member({"symbol": "EURNOK", "family": "carry"}))
    assert "param:mystery_knob" in ng.features_of(
        ng._member({"symbol": "EURUSD", "family": "carry", "params": {"mystery_knob": 3}}))


# ------------------------------------------ 3. an unmeasurable dimension decides nothing at all

def test_an_unmeasured_returns_dimension_never_convicts_and_never_acquits(monkeypatch, tmp_path):
    shadow = _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    # (a) It does not ACQUIT: a parameter twin with no forward record on either side is still
    #     REDUNDANT, and the verdict says the returns were unmeasured rather than hiding it.
    twin = ng.admit({"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
                     "params": {"rr": 1.52, "wait_bars": 12}}, lib)
    assert twin.verdict == "REDUNDANT"
    assert twin.dims["returns"] is None
    assert "UNMEASURED" in twin.why

    # (b) It does not CONVICT: a candidate distant on a measured dimension stays NOVEL with the
    #     returns dimension blank.
    novel = ng.admit({"symbol": "EURUSD", "family": "session_range_breakout",
                      "params": {"entry_z": 2.0}}, lib)
    assert novel.verdict == "NOVEL"
    assert novel.dims["returns"] is None

    # (c) A SERIES AGAINST ITSELF IS NOT A MEASUREMENT. Both sides resolve to the one ledger this
    #     cell has, so the correlation is 1.00 by construction and is refused.
    _ledger(shadow, "ledger_XAUUSD_session_range_breakout_asia.json",
            [float((i % 7) - 3) for i in range(40)])
    ng._SERIES_CACHE.clear()
    same = ng._member({"symbol": "XAUUSD", "family": "session_range_breakout",
                       "session": "asia", "params": {"rr": 1.5}})
    assert ng.returns_similarity(same, same) is None

    # (d) Too few overlapping observations is an absence too, not a small correlation.
    short = ng._member({"symbol": "GBPUSD", "family": "carry", "returns": [0.1] * 5})
    other = ng._member({"symbol": "GBPJPY", "family": "carry", "returns": [0.2] * 5})
    assert ng.returns_similarity(short, other) is None


# ------------------------------------------- 4. a measurement outranks the structural rule

def test_measured_returns_overturn_the_parameter_region_rule(monkeypatch, tmp_path):
    shadow = _library(monkeypatch, tmp_path)
    _ledger(shadow, "ledger_XAUUSD_session_range_breakout_asia.json",
            [float((i % 7) - 3) for i in range(40)])
    _ledger(shadow, "ledger_XAUUSD_session_range_breakout_continuous.json",
            [float(((i * 3 + 2) % 5) - 2) for i in range(40)])
    ng._SERIES_CACHE.clear()
    lib = ng.Library.load()

    v = ng.admit({"symbol": "XAUUSD", "family": "session_range_breakout",
                  "params": {"rr": 1.55, "wait_bars": 12}}, lib)

    assert v.dims["returns"] is not None and v.dims["returns"] < ng.TWIN_AT
    assert v.verdict == "NOVEL"
    assert "outranks the parameter rule" in v.why
    ng._SERIES_CACHE.clear()


# ------------------------------------------------- 5. identity, complexity and alignment

def test_an_exact_cell_identity_is_redundant_without_four_numbers(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    # The same cell id the ledger already carries: this exact question has been judged.
    v = ng.admit({"sym": "AUDCAD", "family": "overnight_gap_decay",
                  "cell": "AUDCAD.overnight_gap_decay.p=deadbeef0"}, lib)

    assert v.verdict == "REDUNDANT"
    assert v.twin == "AUDCAD.overnight_gap_decay.p=deadbeef0"
    assert "exact cell identity" in v.why
    assert "answered question" in v.why


def test_complexity_flags_an_oversized_candidate(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()
    params = {f"k{i}": i + 1 for i in range(8)}

    fat = ng.admit({"symbol": "EURUSD", "family": "carry", "params": params}, lib)
    lean = ng.admit({"symbol": "EURUSD", "family": "carry", "params": {"rr": 1.5}}, lib)

    assert fat.complexity == 8.0
    assert fat.oversized is True
    assert lean.oversized is False
    # An expression counts too, at ten AST nodes to the free parameter, so a short formula with
    # four knobs is inside the threshold and a long one is not.
    src = "signal = px > px.rolling(20).max()\nstop = atr * 2.0\ntarget = atr * 3.0\n"
    wordy = ng.admit({"symbol": "EURUSD", "family": "carry", "expression": src,
                      "params": {f"k{i}": i for i in range(4)}}, lib)
    assert wordy.complexity > ng.OVERSIZED_AT
    assert wordy.oversized is True
    # The flag rides on the verdict; it is a regularisation reading, never a veto of its own.
    assert fat.verdict in ("NOVEL", "REDUNDANT", "UNMEASURED")


def test_the_alignment_flag_reads_the_story_against_the_implementation(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    lib = ng.Library.load()

    misaligned = ng.admit({"symbol": "XAUUSD", "family": "fx_fixing_reversal",
                           "hypothesis": "the London fix causes a temporary imbalance",
                           "expression": "signal = rsi(close, 14) < 30"}, lib)
    aligned = ng.admit({"symbol": "EURUSD", "family": "momentum",
                        "hypothesis": "prior momentum continues after a breakout",
                        "expression": "signal = px > px.rolling(20).max()"}, lib)
    silent = ng.admit({"symbol": "EURUSD", "family": "momentum"}, lib)

    assert misaligned.aligned is False
    assert aligned.aligned is True
    # No story and no implementation is UNMEASURABLE, which is None -- never False.
    assert silent.aligned is None


# ---------------------------------------------------------- 6. the batch, and the artifact

def test_screen_judges_a_batch_against_one_library(monkeypatch, tmp_path):
    _library(monkeypatch, tmp_path)
    rows: list[Any] = [
        {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
         "params": {"rr": 1.5, "wait_bars": 12}},                       # exact identity
        {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
         "params": {"rr": 1.56, "wait_bars": 12}},                      # parameter step
        {"symbol": "USDCAD", "family": "session_range_breakout", "selector": "london",
         "params": {"entry_z": 2.0, "peer_symbol": "WTI"}},             # different bet
        "not a row",                                                    # junk never raises
    ]

    verdicts = ng.screen(rows)

    assert len(verdicts) == len(rows)
    assert [v.verdict for v in verdicts[:3]] == ["REDUNDANT", "REDUNDANT", "NOVEL"]
    assert all(v.twin for v in verdicts[:3])
    assert verdicts[3].verdict in ("NOVEL", "UNMEASURED")


def test_an_absent_library_is_reported_as_empty_not_as_agreement(monkeypatch, tmp_path):
    missing = tmp_path / "gone"
    for name in ("SURVIVORS", "SLEEVES", "VERDICTS"):
        monkeypatch.setattr(ng, name, missing / f"{name}.json")
    monkeypatch.setattr(ng, "SHADOW_DIR", missing)

    lib = ng.Library.load()
    v = ng.admit({"symbol": "XAUUSD", "family": "session_range_breakout"}, lib)

    assert lib.members == []
    assert lib.counts == {"survivors": 0, "sleeves": 0, "judged": 0}
    # An unreadable library must never read as "nothing objected", so the verdict SAYS it was
    # empty rather than quietly passing the candidate as measured-and-different.
    assert v.verdict == "NOVEL"
    assert "library is empty" in v.why
    assert all(x is None for x in v.dims.values())


def test_the_cli_writes_the_artifact_and_dry_run_writes_nothing(monkeypatch, tmp_path, capsys):
    _library(monkeypatch, tmp_path)
    docket = tmp_path / "docket.json"
    docket.write_text(json.dumps([
        {"symbol": "XAUUSD", "family": "session_range_breakout", "selector": "asia",
         "params": {"rr": 1.55, "wait_bars": 12}},
        {"symbol": "USDCAD", "family": "session_range_breakout", "selector": "london",
         "params": {"entry_z": 2.0}},
    ]), encoding="utf-8")
    out = tmp_path / "NOVELTY_GATE.json"

    rc = ng.main(["--docket", str(docket), "--out", str(out), "--dry-run"])
    dry = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert not out.exists()
    assert len(dry) == 6
    assert dry[-1].startswith("dry run")

    rc = ng.main(["--docket", str(docket), "--out", str(out), "--limit", "2"])
    wet = capsys.readouterr().out.strip().splitlines()
    payload = json.loads(out.read_text(encoding="utf-8"))

    assert rc == 0
    assert len(wet) == 6
    assert payload["n_screened"] == 2
    assert payload["n_novel"] + payload["n_redundant"] + payload["n_unmeasured"] == 2
    assert payload["n_redundant"] >= 1
    assert set(payload) >= {"at", "n_screened", "n_novel", "n_redundant", "by_dimension",
                            "twins_named", "oversized", "sample", "rule"}
    assert payload["by_dimension"]["feature"]["establishes_novelty"] is True
    # AST CAN NEVER ESTABLISH NOVELTY. A clone rewritten in different syntax is still a clone.
    assert payload["by_dimension"]["ast"]["establishes_novelty"] is False
    assert len(payload["sample"]) <= 20
    assert all(row["twin"] for row in payload["sample"])
    assert payload["threshold"] == ng.TWIN_AT

    # An absent docket is screened as nothing, not as a crash: absence is never permission, and
    # it is never an exception either.
    rc = ng.main(["--docket", str(tmp_path / "nope.json"), "--out", str(out), "--dry-run"])
    assert rc == 0
    assert "0 of 0 rows screened" in capsys.readouterr().out
