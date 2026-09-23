from __future__ import annotations

import json
import sys
from pathlib import Path

DESK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DESK / "research"))

import forward_reconcile  # noqa: E402


def test_qquant_certificate_identity_is_not_parsed_as_symbol_selector(
    tmp_path: Path, monkeypatch,
) -> None:
    reports = tmp_path / "reports"
    shadow = reports / "shadow"
    shadow.mkdir(parents=True)
    key = "qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY"
    state_path = shadow / "qquant_shadow_state.json"
    state_path.write_text(json.dumps({
        key: {"certificate": key, "status": "ACTIVE", "n": 0},
    }), encoding="utf-8")

    monkeypatch.setattr(forward_reconcile, "BASE", tmp_path)
    monkeypatch.setattr(forward_reconcile, "SHADOW", shadow)
    monkeypatch.setattr(forward_reconcile, "OUT", tmp_path / "forward_reconcile.json")
    monkeypatch.setattr(forward_reconcile, "enrolled_keys", lambda: {key})
    monkeypatch.setattr(forward_reconcile, "certified_pairs", lambda: {("AUDNZD", "afternoon")})
    monkeypatch.setattr(forward_reconcile, "certified_ids", lambda: {key})

    assert forward_reconcile.main() == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]


def test_frequent_shadow_owner_does_not_freeze_after_first_daily_run() -> None:
    source = (DESK / "research" / "shadow_forward.py").read_text(encoding="utf-8")
    assert "shadow already ran today; skip" not in source
    assert 'state["configured_sleeves"] = len(enrolled)' in source


def test_enrolment_reader_survives_certified_sleeves_arity(monkeypatch) -> None:
    """The exact defect: `certified_sleeves()` was widened to 4-tuples and this reader still
    destructured 3, so it raised on every pass and the reconciler ran blind for a full day with
    orphan retirement silently disabled. A positional unpack must never be what decides that."""
    import types

    fake = types.SimpleNamespace(
        SLEEVES=[],
        WINDOWS={"asia": {"rr": 2.0}},
        certified_sleeves=lambda: [
            ("EURZAR", "asia", {"rr": 2.0}, "overnight_gap_decay"),
            ("XAUUSD", "asia", {"rr": 1.5}, "session_range_breakout"),
        ],
        sleeve_key=lambda sym, win, params, family="session_range_breakout": (
            f"{sym}.{win}" if family == "session_range_breakout" else f"{sym}.{family}.{win}"
        ),
    )
    monkeypatch.setitem(sys.modules, "shadow_forward", fake)
    keys = forward_reconcile.enrolled_keys()
    assert keys is not None, "an arity change must not be reported as 'nothing is enrolled'"
    assert "EURZAR.overnight_gap_decay.asia" in keys
    assert "XAUUSD.asia" in keys


def test_unreadable_enrolment_is_unknown_not_empty(monkeypatch) -> None:
    """UNKNOWN must never read as 'no engine enrols anything' -- that is a licence to retire the
    entire forward book on an import error."""
    import types

    def _boom() -> list:
        raise RuntimeError("too many values to unpack (expected 3)")

    monkeypatch.setitem(sys.modules, "shadow_forward", types.SimpleNamespace(
        SLEEVES=[], WINDOWS={}, certified_sleeves=_boom, sleeve_key=lambda *a, **k: ""))
    assert forward_reconcile.enrolled_keys() is None
    assert forward_reconcile.certified_clock_keys() is None


def _reconcile_tmp(tmp_path: Path, monkeypatch, state: dict, *, enrolled, cert_keys) -> dict:
    shadow = tmp_path / "reports" / "shadow"
    shadow.mkdir(parents=True)
    path = shadow / "shadow_state.json"
    path.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setattr(forward_reconcile, "BASE", tmp_path)
    monkeypatch.setattr(forward_reconcile, "SHADOW", shadow)
    monkeypatch.setattr(forward_reconcile, "OUT", tmp_path / "forward_reconcile.json")
    monkeypatch.setattr(forward_reconcile, "enrolled_keys", lambda: enrolled)
    monkeypatch.setattr(forward_reconcile, "certified_clock_keys", lambda: cert_keys)
    monkeypatch.setattr(forward_reconcile, "certified_pairs", lambda: {("ZZZ", "never")})
    monkeypatch.setattr(forward_reconcile, "certified_ids", lambda: set())
    monkeypatch.setattr(forward_reconcile, "gauntlet", lambda specs: {})
    assert forward_reconcile.main() == 0
    return json.loads(path.read_text(encoding="utf-8"))


def test_family_shaped_key_is_not_retired_as_unreconstructible(tmp_path, monkeypatch) -> None:
    """`EURZAR.overnight_gap_decay.asia` parses to selector='overnight_gap_decay', which matches
    no window -- so the certified, running clock was retired. Membership in the engine's own
    certified-key set must settle it before any dot-splitting is consulted."""
    key = "EURZAR.overnight_gap_decay.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 0}},
        enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]


def test_unknown_enrolment_retires_nothing(tmp_path, monkeypatch) -> None:
    key = "GBPJPY.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 4}},
        enrolled=None, cert_keys=None)
    assert state[key]["status"] == "ACTIVE"


def test_certified_row_retired_by_key_shape_is_revived_with_a_fresh_clock(
    tmp_path, monkeypatch,
) -> None:
    key = "USDZAR.overnight_gap_decay.asia"
    stale = "2026-08-01T00:00:00+00:00"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "RETIRED_UNRECONSTRUCTIBLE", "n": 0, "forward_start": stale,
               "retired_at": stale, "retire_reason": "wrong"}},
        enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "ACTIVE"
    assert "retired_at" not in state[key]
    assert state[key]["forward_start"] != stale, "a revived clock must never inherit its window"


def test_gauntlet_failure_is_never_revived(tmp_path, monkeypatch) -> None:
    """RETIRED_GATE_FAIL is a measured ten-gate verdict, not a key-shape inference. Reviving it
    would be the reconciler overturning the one door."""
    key = "XAUUSD.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "RETIRED_GATE_FAIL", "n": 9}}, enrolled={key}, cert_keys={key})
    assert state[key]["status"] == "RETIRED_GATE_FAIL"


def test_retirement_revokes_promotion_authority(tmp_path, monkeypatch) -> None:
    """A retired row that keeps `promotion_authority: true` can still reach capital on frozen
    evidence -- measured live on EURZAR at 04:01 2026-08-27."""
    key = "OLDSYM.dead_family.asia"
    state = _reconcile_tmp(
        tmp_path, monkeypatch,
        {key: {"status": "ACTIVE", "n": 3, "promotion_authority": True}},
        enrolled={"SOMETHING.else"}, cert_keys=set())
    assert state[key]["status"].startswith("RETIRED")
    assert state[key]["promotion_authority"] is False


def test_running_clock_without_a_frozen_identity_is_reported(tmp_path, monkeypatch) -> None:
    """`sleeve_registry.json` is idempotent, so its FILE AGE says nothing -- an unchanged registry
    is the healthy state. The property that matters is that no clock runs unfrozen."""
    key = "GBPJPY.asia"
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"sleeves": {}}), encoding="utf-8")
    import sleeve_registry
    monkeypatch.setattr(sleeve_registry, "REGISTRY", reg)
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    _reconcile_tmp(tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 2}},
                   enrolled={key}, cert_keys={key})
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["identity_unfrozen"] == 1
    assert any(a["action"] == "IDENTITY_UNFROZEN" and a["key"] == key for a in doc["actions"])


def test_family_budget_is_published_per_enrolled_clock_beside_the_flat_cohort(
    tmp_path, monkeypatch,
) -> None:
    """Each enrolled clock carries the census family the engine's own family name resolves to
    and that family's own BH bar; the flat cohort's cap and bar sit beside them, unchanged."""
    from libs.research.slot_registry import MAX_FORWARD_SLOTS
    from libs.validation import family_multiplicity as fm
    from libs.validation.forward_stats import holm_bar

    gap, brk = "EURZAR.overnight_gap_decay.asia", "GBPJPY.asia"
    monkeypatch.setattr(forward_reconcile, "engine_clock_families",
                        lambda: {gap: "overnight_gap_decay", brk: "session_range_breakout"})
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    _reconcile_tmp(tmp_path, monkeypatch,
                   {gap: {"status": "ACTIVE", "n": 3}, brk: {"status": "ACTIVE", "n": 5}},
                   enrolled={gap, brk}, cert_keys={gap, brk})
    doc = json.loads(out.read_text(encoding="utf-8"))
    fb = doc["family_budget"]
    assert fb["status"] == "MEASURED"
    assert fb["flat_cohort"]["max_forward_slots"] == MAX_FORWARD_SLOTS == 12
    assert fb["flat_cohort"]["holm_bar_rank1_at_cap"] == holm_bar(12, 1)
    assert fb["clocks"][gap]["family"] == fm.family_of("overnight_gap_decay")
    assert fb["clocks"][gap]["declared_via"] == "engine"
    assert fb["clocks"][brk]["family"] == fm.family_of("session_range_breakout")
    for key in (gap, brk):
        fam = fb["clocks"][key]["family"]
        m = fb["families"][fam]["effective_m"]
        assert fb["clocks"][key]["family_m"] == m
        assert fb["clocks"][key]["bh_bar"] == fm.bh_bar(m, 1) == fb["families"][fam]["bh_bar_rank1"]
    assert fb["error_budget"]["n_families"] == len(fb["families"])
    # THE BUDGET DECIDES NOTHING AGAIN, AND THAT IS THE POINT (principal 2026-09-23: "no quota or
    # scarcity ever on forward evidence slots"). The alpha arithmetic below is unchanged and still
    # asserted in full -- it is EVIDENCE about what each family has spent -- but no enrolment is
    # refused, deferred or queued on it. A forward clock deploys no capital, so the cap bought no
    # safety and cost hypotheses the desk could never rule on.
    assert fb["decides"] == "NOTHING__ENROLMENT_IS_UNCAPPED"
    assert fb["gates_enrolment"] is False
    assert set(fb["caps"]) == set(fb["families"])
    for fam, n in fb["caps"].items():
        d = fb["cap_detail"][fam]
        # the identity the artifact's own basis names, exact in integers
        assert n == max(0, d["seats_at_this_charge"] - d["charged_m"])
        assert d["seats_at_this_charge"] == MAX_FORWARD_SLOTS
        # one clock of the cap's worth of alpha spent: the rest are still affordable
        assert n == MAX_FORWARD_SLOTS - 1 and d["n_enrolled"] == 1
    assert doc["missed_growth_lines"] == [], "no family is capped, so nothing is forgone"


def test_an_over_enrolled_family_is_capped_and_carries_a_missed_growth_line(
    tmp_path, monkeypatch,
) -> None:
    """A family that has already spent its own error budget may take no NEW enrolment -- and a cap
    without its missed-growth line is exactly what the growth governance forbids, so the line is
    written whether or not anything is waiting."""
    from libs.research.slot_registry import MAX_FORWARD_SLOTS

    keys = {f"SYM{i}.overnight_gap_decay.asia": "overnight_gap_decay"
            for i in range(MAX_FORWARD_SLOTS + 3)}
    keys["LONE.carry.asia"] = "carry"
    monkeypatch.setattr(forward_reconcile, "engine_clock_families", lambda: dict(keys))
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    _reconcile_tmp(tmp_path, monkeypatch, {k: {"status": "ACTIVE", "n": 1} for k in keys},
                   enrolled=set(keys), cert_keys=set(keys))
    doc = json.loads(out.read_text(encoding="utf-8"))
    fb = doc["family_budget"]
    gap_fam = fb["clocks"]["SYM0.overnight_gap_decay.asia"]["family"]
    lone_fam = fb["clocks"]["LONE.carry.asia"]["family"]
    assert fb["caps"][gap_fam] == 0, "15 clocks have spent more than the family's own alpha"
    assert fb["caps"][lone_fam] == MAX_FORWARD_SLOTS - 1, "a family under budget still has seats"
    lines = {ln["family"]: ln for ln in doc["missed_growth_lines"]}
    assert set(lines) == {gap_fam}
    line = lines[gap_fam]
    assert line["rail"] == f"forward_enrolment_cap:{gap_fam}" and line["cap"] == 0
    # no forward ranker on this tmp box: UNMEASURED, never a silent zero
    assert line["value"] is None and line["verdict"] == "UNMEASURED"
    assert "FORWARD_SLOT_RANKER" in line["unmeasured"]


def test_a_capped_family_is_priced_from_the_rankers_waiting_queue(tmp_path, monkeypatch) -> None:
    """With the ranker readable the line is MEASURED: an empty queue is a real zero, and a waiting
    candidate of that family prices the cap in the ranker's own units."""
    from libs.research.slot_registry import MAX_FORWARD_SLOTS

    keys = {f"SYM{i}.overnight_gap_decay.asia": "overnight_gap_decay"
            for i in range(MAX_FORWARD_SLOTS + 3)}
    monkeypatch.setattr(forward_reconcile, "engine_clock_families", lambda: dict(keys))
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    reports = tmp_path / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "FORWARD_SLOT_RANKER.json").write_text(json.dumps(
        {"waiting": [{"cell": "A", "family": "overnight_gap_decay", "slot_value": 4e-5},
                     {"cell": "B", "family": "overnight_gap_decay", "slot_value": 1e-5},
                     {"cell": "C", "family": "carry", "slot_value": 9.0}]}), encoding="utf-8")
    _reconcile_tmp(tmp_path, monkeypatch, {k: {"status": "ACTIVE", "n": 1} for k in keys},
                   enrolled=set(keys), cert_keys=set(keys))
    doc = json.loads(out.read_text(encoding="utf-8"))
    line = doc["missed_growth_lines"][0]
    assert line["verdict"] == "COSTS_GROWTH" and line["n_blocked"] == 2
    assert line["value"] == -5e-05 and line["best_blocked"] == 4e-05
    assert "carry" not in json.dumps(line), "another family's queue never prices this cap"


def test_family_budget_is_UNMEASURED_when_enrolment_is_unknown(tmp_path, monkeypatch) -> None:
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    monkeypatch.setattr(forward_reconcile, "engine_clock_families", lambda: None)
    _reconcile_tmp(tmp_path, monkeypatch, {"GBPJPY.asia": {"status": "ACTIVE", "n": 4}},
                   enrolled=None, cert_keys=None)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["family_budget"]["status"] == "UNMEASURED"


def test_family_name_resolution_prefers_exact_sources_over_the_key() -> None:
    engine = {"XAUUSD.asia": "session_range_breakout"}
    certs = {"qquant.hunt16.json.AUDNZD x": "dav_range_filter_adx"}
    assert forward_reconcile._family_name("XAUUSD.asia", {"family": "other"}, engine, certs) == (
        "session_range_breakout", "engine")
    assert forward_reconcile._family_name("k", {"family": "vwap_trend"}, {}, certs) == (
        "vwap_trend", "row.family")
    assert forward_reconcile._family_name("k", {"choice": {"family": "anti_breakout"}}, {},
                                          certs) == ("anti_breakout", "row.choice.family")
    assert forward_reconcile._family_name(
        "qquant.hunt16.json.AUDNZD x", {"certificate": "qquant.hunt16.json.AUDNZD x"}, {},
        certs) == ("dav_range_filter_adx", "certificate.shadow_spec.family")
    assert forward_reconcile._family_name("k", {"cell": "AUDNZD dav SHORT"}, {}, {}) == (
        "AUDNZD dav SHORT", "row.cell")
    assert forward_reconcile._family_name("k", None, {}, {}) == ("k", "key")


def test_an_undeclared_mechanism_buys_no_more_seats_than_a_declared_one() -> None:
    """The floor that makes declaring never the cheaper path, carried through to the ENROLMENT
    CAP. Charged on raw member counts, a lone undeclared clock would be handed eleven new seats
    while a declared family of four got eight -- the partition would become opt-out on seats
    exactly as it would have on bars."""
    from libs.validation import family_multiplicity as fm

    engine = {f"SYM{i}.overnight_gap_decay.asia": "overnight_gap_decay" for i in range(4)}
    engine["MYSTERY.zzz"] = "zzz_no_such_mechanism"
    fb = forward_reconcile.family_budget(set(engine), {}, engine)
    declared = fb["clocks"]["SYM0.overnight_gap_decay.asia"]["family"]
    assert fb["cap_detail"][fm.UNCLASSIFIED]["n_enrolled"] == 1
    assert fb["cap_detail"][fm.UNCLASSIFIED]["charged_m"] == 4
    assert fb["caps"][fm.UNCLASSIFIED] == fb["caps"][declared] == 8


def test_an_undeclared_mechanism_pays_the_largest_declared_family_bar() -> None:
    """The floor that makes declaring the mechanism never the cheaper path, carried through to
    the published row rather than lost in the census."""
    from libs.validation import family_multiplicity as fm

    engine = {f"SYM{i}.overnight_gap_decay.asia": "overnight_gap_decay" for i in range(4)}
    engine["MYSTERY.zzz"] = "zzz_no_such_mechanism"
    fb = forward_reconcile.family_budget(set(engine), {}, engine)
    assert fb["status"] == "MEASURED"
    unk = fb["clocks"]["MYSTERY.zzz"]
    assert unk["family"] == fm.UNCLASSIFIED
    assert unk["family_m"] == 4 and fb["families"][fm.UNCLASSIFIED]["floored_to_largest_declared"]
    assert unk["bh_bar"] == fb["clocks"]["SYM0.overnight_gap_decay.asia"]["bh_bar"]


def test_frozen_clock_raises_no_identity_finding(tmp_path, monkeypatch) -> None:
    key = "GBPJPY.asia"
    reg = tmp_path / "reg.json"
    reg.write_text(json.dumps({"sleeves": {key: {"identity": {"a": 1}}}}), encoding="utf-8")
    import sleeve_registry
    monkeypatch.setattr(sleeve_registry, "REGISTRY", reg)
    out = tmp_path / "forward_reconcile.json"
    monkeypatch.setattr(forward_reconcile, "OUT", out)
    _reconcile_tmp(tmp_path, monkeypatch, {key: {"status": "ACTIVE", "n": 2}},
                   enrolled={key}, cert_keys={key})
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["identity_unfrozen"] == 0
