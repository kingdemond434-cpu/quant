"""L1.102: EVERY CERTIFICATE HOLDS AN ACCUMULATING FORWARD CLOCK, AND THE FENCE SAYS SO.

The principal, 2026-09-24: "They must all automatically be on forward clocks live immediate upon
certification, in future all -- this not happening is a breach."

THE TWO HALVES PULL AGAINST EACH OTHER ON PURPOSE, the way `test_certificate_clocks_accrue` does.
One half asserts that an absent, blocked, late or FROZEN clock is LOUD. The other asserts that a
young clock with no observation yet is NOT slandered as a defect -- forward time passing is the
entire mechanism, and a fence that fired on every newly certified cell would be switched off
within a day and the law with it.

THE THIRD HALF IS THE ONE THE DESK KEPT GETTING WRONG: the fence must be UNSATISFIABLE BY A
STATUS STRING. `forward_enrolment.census` decides `accruing` from the status alone, so on
2026-09-24 it called 171 clocks accruing while 116 of them held zero observations. The test named
`test_a_fresh_status_over_a_frozen_row_count_is_still_a_breach` is the one that pins that, and it
is the reason this file exists rather than another clause in an existing fence.

AND THE FOURTH: FAMILY-AGNOSTIC CLOCKING. Five of the desk's seven certificate families have
never had a live sleeve, so their routing has almost certainly never been exercised. A registry
of known families IS the bug, so these tests hand the machinery a family name that appears
nowhere in this repository and require it to be clocked and judged exactly like the rest.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import check_certificate_clock_law as law  # noqa: E402

NOW = datetime(2026, 9, 24, 23, 0, tzinfo=UTC)
#: A family the repository has never heard of. If anything anywhere keys behaviour off a family
#: NAME, this is what catches it.
NOVEL = "quenched_basis_torsion"


def _cert(name="c1", family=NOVEL, symbol="EURNOK", selector="asia",
          certified_at="2026-09-24T21:00:00+00:00", params=None):
    return {"name": name, "symbol": symbol, "family": family, "selector": selector,
            "side": "LONG", "params": params or {}, "certified_at": certified_at}


def _row(n=0, status="ACTIVE", enrolled_at="2026-09-24T21:00:10+00:00",
         forward_start="2026-09-24T21:00:10+00:00", **extra):
    return {"n": n, "status": status, "enrolled_at": enrolled_at,
            "forward_start": forward_start, "lane": "shadow_state.json", **extra}


def _samples(*pairs):
    """(hours_ago, n) -> the history shape the fence diffs against."""
    return [{"at": (NOW - timedelta(hours=h)).isoformat(), "counts": {"K": n}}
            for h, n in pairs]


# --------------------------------------------------------------- BREACH: the clock is absent
def test_a_certificate_with_no_clock_is_a_breach() -> None:
    e = law.judge(_cert(), "K", None, [], 100.0, "why", NOW)
    assert e["breach"] is True and e["verdict"] == "NO_CLOCK"
    assert "can never mature" in e["why"]
    # The remedy must be in the text: a breach is never repaired by withdrawing a certificate.
    assert "never withdraw" in e["why"].lower()


def test_a_blocked_clock_is_a_breach_and_names_its_blocker() -> None:
    """The live defect on the box 2026-09-24: one clock IDENTITY_BROKEN for 168h."""
    row = _row(n=0, status="IDENTITY_BROKEN",
               last_error="params changed after the clock froze")
    e = law.judge(_cert(), "K", row, [], 100.0, "why", NOW)
    assert e["breach"] is True and e["verdict"] == "BLOCKED"
    assert "params changed" in e["blocker"]


def test_a_late_clock_is_a_breach_because_immediate_is_the_word() -> None:
    e = law.judge(_cert(certified_at="2026-09-24T12:00:00+00:00"), "K",
                  _row(enrolled_at="2026-09-24T20:00:00+00:00"), [], 100.0, "why", NOW)
    assert e["late"] is True and e["breach"] is True
    assert e["latency_h"] == pytest.approx(8.0)
    assert "immediately, no waiting" in e["latency_breach"]


def test_latency_never_masks_the_accumulation_verdict() -> None:
    """A LATE CLOCK THAT IS NOW TICKING MUST STILL SAY IT IS TICKING.

    The first cut of this fence returned early on latency, and against the live box that reported
    174 LATE_CLOCKs and not one word about whether a single clock was accumulating -- which is
    the only question the law exists to answer. The two conditions are independent.
    """
    e = law.judge(_cert(certified_at="2026-09-01T00:00:00+00:00"), "K",
                  _row(n=9, forward_start="2026-09-20T00:00:00+00:00"),
                  _samples((200, 3)), 100.0, "why", NOW)
    assert e["verdict"] == "ACCUMULATING", "the accumulation verdict must survive the latency flag"
    assert e["late"] is True, "and the late clock must still be reported as a breach"
    assert e["breach"] is True


def test_latency_is_measured_from_the_earliest_clock_evidence_not_enrolled_at() -> None:
    """`enrolled_at` IS REWRITTEN EVERY PASS, and reading latency off it alone is libel.

    Measured on the box 2026-09-24: canon was republished at 20:06Z and the enrolment leg ran at
    21:00Z, so all 174 certificates carried `enrolled_at` 21:00 whatever their clocks had been
    doing -- charging `external.XAUUSD.session_range_breakout` 679 hours for a clock whose
    `forward_start` proves it had been running since 2026-08-27.
    """
    row = _row(n=3, forward_start="2026-08-27T00:00:00+00:00",
               enrolled_at="2026-09-24T21:00:00+00:00")
    e = law.judge(_cert(certified_at="2026-08-26T23:00:00+00:00"), "K", row,
                  [], 100.0, "why", NOW)
    assert e["latency_h"] == pytest.approx(1.0), (
        "latency is certification -> the clock actually starting, not -> the row being rewritten")
    assert e["late"] is False, "1.0h is not past a 1.0h cycle"
    assert e["clock_began_at"].startswith("2026-08-27")


def test_a_clock_that_predates_its_certificate_has_zero_latency() -> None:
    """A recertified cell whose clock never stopped was never late. Latency clamps at zero rather
    than going negative and flattering (or slandering) anything."""
    e = law.judge(_cert(certified_at="2026-09-24T18:30:00+00:00"), "K",
                  _row(n=3, forward_start="2026-09-17T22:57:00+00:00"), [], 100.0, "why", NOW)
    assert e["latency_h"] == 0.0 and e["late"] is False


def test_a_clock_inside_one_promoter_cycle_is_not_late() -> None:
    e = law.judge(_cert(certified_at="2026-09-24T21:00:00+00:00"), "K",
                  _row(enrolled_at="2026-09-24T21:00:10+00:00"), [], 100.0, "why", NOW)
    assert e["verdict"] != "LATE_CLOCK"
    assert e["latency_h"] < law.LATENCY_BREACH_H


# ------------------------------------------- BREACH: the row count, not the label, is the test
def test_a_frozen_row_count_is_a_breach() -> None:
    e = law.judge(_cert(), "K", _row(n=4, forward_start="2026-09-01T00:00:00+00:00"),
                  _samples((200, 4), (10, 4)), 100.0, "why", NOW)
    assert e["breach"] is True and e["verdict"] == "FROZEN_ROWS"
    assert e["prior_n"] == 4


def test_a_fresh_status_over_a_frozen_row_count_is_still_a_breach() -> None:
    """THE ANTI-FABRICATION TEST, and the reason this fence exists.

    Everything a re-run of the engine can move is healthy here: the status reads ACTIVE, the
    row was attempted seconds ago, and the state file's mtime is current. Only the OBSERVATION
    COUNT is frozen, and only the observation count is evidence.
    """
    row = _row(n=7, status="ACTIVE", forward_start="2026-09-01T00:00:00+00:00",
               last_attempt_at=NOW.isoformat(), last_entry="2026-09-02T00:00:00+00:00",
               bar_source_stale=False)
    e = law.judge(_cert(), "K", row, _samples((200, 7), (1, 7)), 100.0, "why", NOW)
    assert e["breach"] is True and e["verdict"] == "FROZEN_ROWS", (
        "a fresh status over a frozen row count is this desk's signature deception; the fence "
        "must read the rows")
    assert "not evidence" in e["why"]


# ------------------------------------------------- COMPLIANT: do not slander an honest clock
def test_a_young_clock_with_no_observation_yet_is_compliant() -> None:
    """115 of the 116 zero-observation clocks on the box were 2.3h old. Firing on those would
    convict every newly certified cell the desk will ever mint."""
    e = law.judge(_cert(), "K", _row(n=0, forward_start="2026-09-24T21:00:00+00:00"),
                  [], 100.0, "why", NOW)
    assert e["breach"] is False and e["verdict"] == "WARMING"
    assert "mechanism, not a delay" in e["why"]


def test_an_accumulating_clock_is_compliant_and_shows_its_movement() -> None:
    e = law.judge(_cert(), "K", _row(n=9, forward_start="2026-09-01T00:00:00+00:00"),
                  _samples((200, 3)), 100.0, "why", NOW)
    assert e["breach"] is False and e["verdict"] == "ACCUMULATING"
    assert e["prior_n"] == 3 and e["n"] == 9


def test_a_decided_clock_is_not_a_defect() -> None:
    for status in ("PROMOTED", "KILL", "RETIRED", "PROMOTION_CANDIDATE",
                   "QUARANTINED_FORWARD_CLOCK_BREACH"):
        e = law.judge(_cert(), "K", _row(status=status), [], 100.0, "why", NOW)
        assert e["breach"] is False, f"{status} is a verdict, not a wiring defect"
        assert e["verdict"] == "DECIDED"


def test_an_unmeasured_threshold_is_reported_never_breached() -> None:
    """L1.28a: a family with no two-observation clock yet cannot convict its own certificates."""
    e = law.judge(_cert(), "K", _row(n=0, forward_start="2026-01-01T00:00:00+00:00"),
                  [], None, "no gap yet", NOW)
    assert e["breach"] is False and e["verdict"] == "UNMEASURED_THRESHOLD"


def test_an_unmeasured_key_is_reported_never_breached() -> None:
    e = law.judge(_cert(), None, None, [], 100.0, "why", NOW)
    assert e["breach"] is False and e["verdict"] == "UNMEASURED_KEY"


# ----------------------------------------------------------------- FAMILY-AGNOSTIC CLOCKING
def test_a_never_traded_family_is_judged_exactly_like_every_other() -> None:
    """THE TEST THE BRIEF ASKED FOR: a certificate in a family with no live sleeve, ever, must
    still be able to hold a ticking clock and must be convicted when it cannot."""
    absent = law.judge(_cert(family=NOVEL), "K", None, [], 100.0, "why", NOW)
    assert absent["verdict"] == "NO_CLOCK" and absent["breach"] is True

    ticking = law.judge(_cert(family=NOVEL), "K", _row(n=5), _samples((200, 1)),
                        100.0, "why", NOW)
    assert ticking["verdict"] == "ACCUMULATING" and ticking["breach"] is False
    assert ticking["family"] == NOVEL


def test_the_warming_threshold_is_derived_per_family_from_measured_rows() -> None:
    """Not a lookup table: the number comes from that family's own forward evidence."""
    rows = {"a": {"n": 3, "first_entry": "2026-09-01T00:00:00+00:00",
                  "last_entry": "2026-09-01T20:00:00+00:00"},
            "b": {"n": 0}}
    gaps = law.family_gap_hours(rows, {"a": NOVEL, "b": NOVEL})
    assert gaps[NOVEL] == pytest.approx(10.0), "20h across n-1=2 intervals"
    thr, why = law._threshold_h(NOVEL, gaps)
    assert thr == pytest.approx(max(law.MIN_FROZEN_H, 10.0 * law.FROZEN_MULTIPLE))
    assert "measured gap" in why
    missing, why2 = law._threshold_h("a_family_with_no_evidence", gaps)
    assert missing is None and "UNMEASURED" in why2


def test_the_fence_hardcodes_no_family_name() -> None:
    """A REGISTRY OF KNOWN FAMILIES IS THE BUG. Five of seven families have never traded; if the
    fence knew their names it would be the thing that has to be edited for the sixth."""
    src = (ROOT / "scripts" / "check_certificate_clock_law.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines()
                     if not line.lstrip().startswith("#"))
    body = code.split('"""', 2)[-1]  # drop the module docstring, which may cite families
    for family in ("session_range_breakout", "overnight_gap_decay", "cross_asset_residual",
                   "macro_conditional", "pca_residual", "carry", "formula"):
        assert family not in body, (
            f"`{family}` is named in the fence's code: that is a per-family special case, and "
            f"the next family the desk mints will be invisible to it")


def test_the_fence_acts_on_nothing() -> None:
    """IT MEASURES AND NAMES. It must never enrol, promote, retire or size a clock -- a fence
    that repairs what it judges can always be made to pass by repairing louder, and `discovered`
    (permanently banned) must be reportable here without anything mistaking that for a cue to
    give it a clock."""
    src = (ROOT / "scripts" / "check_certificate_clock_law.py").read_text(encoding="utf-8")
    for verb in ("def enrol", "def promote", "def retire", "def size", "def repair"):
        assert verb not in src, "this fence measures and names; it must never act on a clock"


# --------------------------------------------- ONE CLOCK PER IDENTITY (the generic repair)
def _sf():
    """`shadow_forward` or a skip: it needs the desk on the path and pandas present."""
    desk = ROOT / "desks" / "mt5"
    for p in (str(desk), str(desk / "research")):
        if p not in sys.path:
            sys.path.insert(0, p)
    return pytest.importorskip("shadow_forward")


def test_two_rows_the_engine_cannot_separate_become_one_sleeve() -> None:
    """THE LIVE DEFECT, PINNED. Canon held 174 certificates against 172 distinct keys: two pairs
    of CHFNOK carry rows differing only by a default written out explicitly. Two owners of one
    clock overwrite each other's params every pass, which is exactly what the identity guard
    freezes at IDENTITY_BROKEN -- and one of them had been stuck there 168.5h with 0
    observations.
    """
    sf = _sf()
    rows = [("CHFNOK", "asia", {}, "carry", "LONG", "", (), True),
            ("CHFNOK", "asia", {"timeframe": "H1"}, "carry", "LONG", "", (), True)]
    assert sf.sleeve_key(*rows[0][:2], rows[0][2], rows[0][3], "LONG") == \
           sf.sleeve_key(*rows[1][:2], rows[1][2], rows[1][3], "LONG"), (
        "premise of this test: these two collide")
    out = sf._one_clock_per_identity(rows)
    assert len(out) == 1, "two rows the engine cannot tell apart are ONE sleeve, not two"
    assert out[0][2] == {"timeframe": "H1"}, "the more explicit row wins, deterministically"


def test_the_collapse_is_stable_across_passes() -> None:
    """An arbitrary winner that varies by pass IS the flip-flop that broke the clock."""
    sf = _sf()
    rows = [("CHFNOK", "asia", {"input_symbol": "CHFNOK"}, "carry", "LONG", "", (), True),
            ("CHFNOK", "asia", {"input_symbol": "CHFNOK", "timeframe": "H1"}, "carry", "LONG",
             "", (), True)]
    first = sf._one_clock_per_identity(rows)
    assert first == sf._one_clock_per_identity(list(reversed(rows))), (
        "the same certified set must always produce the same clock identity, whatever order "
        "canon happens to yield it in")


def test_distinct_strategies_are_never_collapsed() -> None:
    """THE OTHER HALF, and the one that matters more: rr=1.5 and rr=2.5 are two strategies and
    each owes its own forward evidence. A dedupe that merged them would silently delete a
    certificate's clock, which is the opposite of the law."""
    sf = _sf()
    rows = [("XAUUSD", "asia", {"rr": 1.5}, "session_range_breakout", "LONG", "", (), True),
            ("XAUUSD", "asia", {"rr": 2.5}, "session_range_breakout", "LONG", "", (), True),
            ("XAUUSD", "asia", {"rr": 1.5}, "overnight_gap_decay", "LONG", "", (), True)]
    assert len(sf._one_clock_per_identity(rows)) == 3


def test_the_repair_names_no_family_and_no_param() -> None:
    """A fix that special-cased `timeframe` would be silent the next time two rows collide on a
    window default or a param the desk has not invented yet."""
    sf = _sf()
    src = sf._one_clock_per_identity.__doc__ or ""
    assert "GENERIC" in src.upper()
    import inspect
    code = inspect.getsource(sf._one_clock_per_identity)
    body = code.split('"""', 2)[-1]
    for token in ('"timeframe"', "'timeframe'", '"carry"', '"H1"'):
        assert token not in body, (
            f"{token} appears in the repair's CODE: that is the special case this must not be")


# ------------------------------------------------------------------------------- THE WIRING
def test_the_fence_is_registered_in_the_law_gate() -> None:
    """AN UNWIRED FENCE IS A DEFECT (III.16). This is the test that fails if anyone unwires it."""
    from scripts.run_law_gate import _LAW_FENCES, _STATE_FENCES
    registered = {f for f, _a in _LAW_FENCES} | {f for f, _a in _STATE_FENCES}
    assert "check_certificate_clock_law.py" in registered, (
        "L1.102's fence is not in _LAW_FENCES or _STATE_FENCES -- an unwired fence enforces "
        "nothing, and the law it carries becomes a claim the desk cannot cash (L1.49)")
    assert "check_certificate_clock_law.py" in {f for f, _a in _STATE_FENCES}, (
        "it reads live clock state no clean checkout has, so it belongs in the state half")


def test_the_fence_runs_on_a_clock() -> None:
    """DONE MEANS RUNS ON A SCHEDULE AND LEAVES AN ARTIFACT. Without an hourly leg the history
    file never gains a second sample, and the accumulation test can never rule on anything."""
    src = (ROOT / "desks" / "mt5" / "research" / "hourly_cycle.py").read_text(encoding="utf-8")
    assert "check_certificate_clock_law.py" in src, (
        "the fence is on no clock, so its row-count history never accumulates and every "
        "certificate reads UNMEASURED_HISTORY for ever")
    assert "certificate_clock_law" in src


def test_an_absent_artifact_reads_unmeasured_not_pass(tmp_path) -> None:
    """A host with nothing scheduled to advance a clock cannot have a stalled one."""
    doc = law.scan(root=tmp_path, now=NOW, record=False)
    assert doc["ok"] is True
    assert doc["verdict"] in ("NOT_APPLICABLE", law.UNMEASURED)
    assert doc["problems"] == []


def test_the_history_records_row_counts_and_nothing_else(tmp_path) -> None:
    """The history is the evidence base; it must hold counts, not statuses."""
    p = tmp_path / "certificate_clock_history.json"
    law.save_history([{"at": NOW.isoformat(), "counts": {"K": 3}}], p)
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["samples"][0]["counts"] == {"K": 3}
    assert "row counts" in doc["rule"] or "observation COUNT" in doc["rule"]
    assert law.load_history(p)[0]["counts"]["K"] == 3


def test_the_prior_sample_is_the_oldest_inside_the_window() -> None:
    """Most-recent would be minutes old on an hourly cadence and could never show a freeze."""
    n, at = law._prior_sample(_samples((300, 1), (200, 2), (1, 9)), "K", NOW, 100.0)
    assert n == 1 and at is not None and at < NOW - timedelta(hours=200)
