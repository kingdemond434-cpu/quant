"""Most microstructure vocabulary is defined on a book, and this venue does not have one.

THE MEASUREMENT THE WHOLE MODULE TURNS ON, already in the repo since 2026-08-17:

    desks/mt5/data/tape/depth_probe.json -- 22 symbols probed, levels: 0 on every one,
    "symbols_with_real_depth": []

So queue position, true order-flow imbalance, microprice from sizes, depth convexity, absorption,
iceberg inference and cancel/replenish hazard are not backlog. They are UNBUILDABLE_ON_VENUE, and
building them on a book synthesised from bid/ask would produce a model OF THE SYNTHESIS.

THE THREE PROPERTIES THAT DECIDE WHETHER THIS CENSUS IS WORTH READING:

    IT NEVER COLLAPSES STARVED INTO UNBUILDABLE. They demand opposite work -- one is a clock this
    desk can wire today, the other is a broker limitation no amount of work removes -- and a
    score that averaged them would hide the half that is actionable. The headline scores LIVE
    against REACHABLE, so a venue with no order book costs the desk nothing it could have earned.

    NO PROBE IS NOT NO DEPTH. An absent probe means nobody asked the terminal, which is a
    different state from having asked and been told zero, and only the second justifies
    abandoning a construction class. Absent reads UNMEASURED and depth constructions read STARVED
    (run the probe) rather than UNBUILDABLE.

    ABSENT-AND-TRACKED IS STRONGER EVIDENCE THAN ABSENT. On a two-machine desk an artifact may be
    missing because the box has not shared it. Git settles it: `desks/mt5/data/` is a
    STATE_PREFIX the box commits and pushes, so an absent path there that is NOT gitignored has
    never been produced on ANY machine. An absent path that IS gitignored proves nothing and must
    say so rather than inventing a verdict.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.research import microstructure_census as mc  # noqa: E402


def _probe(root: Path, *, symbols: int = 22, with_depth: list[str] | None = None) -> None:
    p = root / Path(*mc.DEPTH_PROBE_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "at": "2026-08-17T22:54:48+00:00",
        "symbols": {f"S{i}": {"subscribed": True, "levels": 0} for i in range(symbols)},
        "symbols_with_real_depth": list(with_depth or []),
    }), encoding="utf-8")


def test_no_depth_makes_book_constructions_unbuildable_not_backlog(tmp_path):
    _probe(tmp_path)
    by = {r.construction.key: r for r in mc.readings(tmp_path)}
    for key in ("queue_position", "order_flow_imbalance_true", "microprice",
                "depth_curve_convexity", "absorption_vs_fragile_display",
                "cancel_replenish_hazard"):
        assert by[key].verdict == mc.UNBUILDABLE, key
        assert by[key].fixable_here is False
        assert "no resting depth" in by[key].blocker


def test_an_absent_probe_is_unmeasured_and_never_a_verdict(tmp_path):
    """Nobody has asked the terminal. That is not the same as having asked and been told zero."""
    d = mc.depth_verdict(tmp_path)
    assert d["state"] == "UNMEASURED"
    by = {r.construction.key: r for r in mc.readings(tmp_path)}
    assert by["queue_position"].verdict == mc.STARVED
    assert by["queue_position"].fixable_here is True


def test_real_depth_would_reopen_the_whole_class(tmp_path):
    """The census must follow the probe, not a belief about retail CFD venues in general."""
    _probe(tmp_path, with_depth=["XAUUSD"])
    assert mc.depth_verdict(tmp_path)["state"] == "HAS_DEPTH"
    by = {r.construction.key: r for r in mc.readings(tmp_path)}
    assert by["microprice"].verdict != mc.UNBUILDABLE


def test_starved_and_unbuildable_are_never_averaged(tmp_path):
    """One is a clock this desk can wire today; the other is a broker it cannot change."""
    _probe(tmp_path)
    doc = mc.census(tmp_path)
    reachable = doc["n_constructions"] - doc["by_verdict"][mc.UNBUILDABLE]
    assert doc["by_verdict"][mc.UNBUILDABLE] > 0
    assert doc["live_of_reachable"] == round(doc["by_verdict"][mc.LIVE] / reachable, 3)
    assert doc["n_fixable_here"] == len(doc["fixable_here"])
    assert all(k not in doc["fixable_here"] for k in doc["verdicts"][mc.UNBUILDABLE])
    assert "never averaged" in doc["rule"]


def test_an_absent_untracked_artifact_proves_a_producer_never_ran(tmp_path):
    """`desks/mt5/data/` is a STATE_PREFIX the box commits: had any machine written it, the next
    adopt would have carried it here."""
    (tmp_path / ".git").mkdir()                       # no ignore rules -> nothing is ignored
    st = mc.artifact_state(tmp_path, "desks/mt5/data/cost_surface_tick.json")
    assert st["state"] == "NEVER_PRODUCED"
    assert "never run" in st["why"]


def test_an_absent_gitignored_artifact_proves_nothing_and_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "_ignored", lambda root, rel: True)
    st = mc.artifact_state(tmp_path, "desks/mt5/reports/TAPE_FEATURES.json")
    assert st["state"] == "UNKNOWN_BOX_LOCAL"
    assert "not evidence" in st["why"]


def test_a_present_artifact_is_present(tmp_path):
    p = tmp_path / "desks" / "mt5" / "data" / "x.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")
    assert mc.artifact_state(tmp_path, "desks/mt5/data/x.json")["state"] == "PRESENT"


def test_a_never_produced_artifact_outranks_a_missing_input(tmp_path, monkeypatch):
    """Wiring the producer is the work whether or not THIS tree can see the tape."""
    _probe(tmp_path)
    monkeypatch.setattr(mc, "_ignored", lambda root, rel: False)
    by = {r.construction.key: r for r in mc.readings(tmp_path)}
    r = by["effective_spread_at_latency"]
    assert r.verdict == mc.STARVED and r.fixable_here
    assert "never been produced on any machine" in r.blocker


def test_external_feeds_are_a_purchase_not_a_wiring_task(tmp_path):
    """An input nobody has acquired is not a clock this desk forgot to wire."""
    _probe(tmp_path)
    by = {r.construction.key: r for r in mc.readings(tmp_path)}
    assert by["venue_quote_comparison"].verdict == mc.EXTERNAL
    assert by["venue_quote_comparison"].fixable_here is False


def test_an_acquired_feed_stops_being_external(tmp_path):
    """`futures_cfd_lead_lag` was NEEDS_EXTERNAL_FEED until the reference bars were fetched. A
    census that could not notice acquisition would keep a solved problem on the buy list."""
    _probe(tmp_path)
    before = {r.construction.key: r for r in mc.readings(tmp_path)}
    assert before["futures_cfd_lead_lag"].verdict == mc.EXTERNAL
    (tmp_path / "desks" / "mt5" / "data" / "reference" / "futures").mkdir(parents=True)
    art = tmp_path / Path(*["desks", "mt5", "reports", "FUTURES_LEAD_LAG.json"])
    art.parent.mkdir(parents=True, exist_ok=True)
    art.write_text("{}", encoding="utf-8")
    after = {r.construction.key: r for r in mc.readings(tmp_path)}
    assert after["futures_cfd_lead_lag"].verdict == mc.LIVE


def test_every_construction_names_what_a_decision_does_with_it():
    """A construction nothing acts on is a report, and has to be labelled as one on the way in."""
    for c in mc.CONSTRUCTIONS:
        assert c.changes.strip(), c.key
        assert c.module.strip(), c.key
        assert c.needs, c.key
        assert all(n in (mc.TICKS, mc.DEPTH, mc.FILLS, mc.FUTURES, mc.BROKERS) for n in c.needs)


def test_every_named_module_exists():
    """A census that cites a module nobody wrote is the failure it exists to find."""
    for c in mc.CONSTRUCTIONS:
        rel = c.module.split(":")[0]
        path = (_ROOT / rel if rel.startswith(("libs/", "desks/"))
                else _ROOT / "desks" / "mt5" / rel)
        assert path.exists(), f"{c.key} cites {c.module}, which is not in the repo"


def test_construction_keys_are_unique():
    keys = [c.key for c in mc.CONSTRUCTIONS]
    assert len(set(keys)) == len(keys)


def test_the_census_computes_no_microstructure_statistic():
    """It reads the repo and reports what COULD be computed. A census that also computed would
    have to be trusted twice."""
    src = (_ROOT / "libs" / "research" / "microstructure_census.py").read_text(encoding="utf-8")
    for forbidden in ("import numpy", "import pandas", "rolling(", "np."):
        assert forbidden not in src, f"the census reached for {forbidden}"


@pytest.mark.parametrize("verdict", mc.VERDICTS)
def test_every_verdict_is_reachable_by_some_construction(verdict, tmp_path):
    """A verdict no input can produce is dead vocabulary that reads as coverage."""
    _probe(tmp_path)
    doc = mc.census(tmp_path)
    assert verdict in doc["verdicts"]
