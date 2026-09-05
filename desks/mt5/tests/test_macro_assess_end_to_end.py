"""The whole path, and the property that decides whether this is intelligence or a momentum bot:
THE SYSTEM MUST BE ABLE TO CONCLUDE "DO NOTHING".

A headline that sounds bullish for gold while the metal has not moved, the exposure is unmeasured
and the category has no sample must produce no increase. If the design can only ever add risk on
news, it is a momentum-chasing bot wearing an intelligence label. Here that outcome is
ARITHMETIC -- importance is a product and every term can veto -- rather than a rule someone
remembered to write.

Also pinned: the coverage map names its blind spots, because a named gap is a purchasing decision
and an unnamed one is a silent failure.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from macro.assess import assess  # noqa: E402
from macro.credibility import Claim, CredibilityModel  # noqa: E402
from macro.expression import Exposure, load_aliases, load_universe  # noqa: E402
from macro.factors import FactorBasis  # noqa: E402
from macro.ledger import MIN_CATEGORY_N, EventLedger  # noqa: E402
from macro.prices import FakePriceReader, synthetic_series  # noqa: E402
from macro.schema import EventRecord, Status  # noqa: E402
from macro.sources import DOMAINS, FakeSource, RawItem, coverage, default_sources  # noqa: E402
from macro.taxonomy import Taxonomy  # noqa: E402

SPAN = 60.0
T0 = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)
START = T0 - timedelta(seconds=SPAN * 400)
UNIVERSE = load_universe()
ALIASES = load_aliases(UNIVERSE)

BASIS = FactorBasis(("XAUUSD", "XAGUSD"),
                    {"F1[+XAUUSD,+XAGUSD]": {"XAUUSD": 0.7, "XAGUSD": 0.7}},
                    {"F1[+XAUUSD,+XAGUSD]": 0.6}, 2000, Status.MEASURED, "")


def _reader(jump: float = 0.0, jump_at: int = 402) -> FakePriceReader:
    kw = {"jump_at": jump_at, "jump": jump} if jump else {}
    return FakePriceReader(
        {"XAUUSD": synthetic_series(START, 900, SPAN, step=0.001, **kw),
         "XAGUSD": synthetic_series(START, 900, SPAN, step=0.0012, **kw)},
        {"XAUUSD": SPAN, "XAGUSD": SPAN})


def _item(title: str, *, published: datetime, received: datetime) -> RawItem:
    return RawItem(source_id="REUTERS", title=title, url="http://example/1",
                   published_at=published.isoformat(), received_at=received.isoformat())


def _kit(led: EventLedger, reader, exposures=()):
    cred = CredibilityModel()
    cred.tier_of["REUTERS"] = "WIRE"
    return {"taxonomy": Taxonomy(), "credibility": cred, "ledger": led, "reader": reader,
            "basis": BASIS, "exposures": list(exposures), "universe": UNIVERSE,
            "aliases": ALIASES, "source_tier": "WIRE", "source_licence": "licensed:test",
            "retrieval": "fixture", "robots_ok": True}


def test_a_bullish_sounding_headline_with_no_evidence_produces_nothing(tmp_path: Path) -> None:
    """THE PROPERTY. Not a rule -- a product with a zero in it."""
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Middle East escalation reported, analysts see safe-haven demand",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    assert a.record.importance == 0.0
    assert a.record.capital_authority is False
    assert a.actionable is False
    # And the refusal names every gate that failed, so the desk can act on the reason.
    assert "replay" in a.record.authority_reason
    assert "measured reactions" in a.record.authority_reason


def test_the_event_is_still_RECORDED_and_still_visible(tmp_path: Path) -> None:
    """Refusing to trade is not refusing to look. The row is the asset."""
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Zorblatt lattice resonance anomaly in orbital manifold telemetry",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    assert led.append(a.record) is True
    assert a.record.category == "UNCLASSIFIED"
    assert a.record.novelty is not None and a.record.novelty > 0.5
    # The monitoring score survives the unmeasured inputs so a novel event is not invisible...
    assert a.record.extra["triage_score"] > 0.0
    # ...and carries no authority whatsoever.
    assert "NO capital authority" in a.record.extra["triage_note"]
    assert a.record.capital_authority is False


def test_a_fully_priced_event_scores_zero_however_credible(tmp_path: Path) -> None:
    """High credibility, zero opportunity. The arithmetic, again."""
    led = EventLedger(tmp_path / "l.jsonl")
    cred = CredibilityModel()
    cred.tier_of.update({"REUTERS": "WIRE", "AP": "WIRE", "AFP": "WIRE"})
    # The jump lands at bar 395 -- between publication (bar 390) and arrival (bar 400). The desk
    # was ten minutes late and the move happened while it was blind.
    kit = _kit(led, _reader(jump=0.06, jump_at=395))
    kit["credibility"] = cred
    a = assess(_item("Central bank announces emergency rate decision",
                     published=T0 - timedelta(seconds=600), received=T0),
               corroborations=[Claim("AP"), Claim("AFP")], **kit)
    assert a.record.credibility["p_true"] > 0.9, "three wires agree -- highly credible"
    assert a.priced.pre_move_sigma is not None and a.priced.pre_move_sigma > 3.0
    assert a.record.importance == 0.0
    assert a.record.capital_authority is False
    assert "abstain" in a.record.authority_reason or "priced" in a.record.authority_reason


def test_a_contested_report_never_produces_a_confident_direction(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    cred = CredibilityModel()
    cred.tier_of.update({"REUTERS": "WIRE", "DENIAL": "WIRE"})
    kit = _kit(led, _reader())
    kit["credibility"] = cred
    a = assess(_item("Pipeline outage reported at major terminal",
                     published=T0 - timedelta(seconds=120), received=T0),
               corroborations=[Claim("DENIAL", supports=False)], **kit)
    c = a.record.credibility
    assert c["contested"] is True
    assert c["uncertainty_mult"] > 1.0
    assert len(c["branches"]) == 2
    assert abs(c["branches"][0]["p"] + c["branches"][1]["p"] - 1.0) < 1e-9
    assert a.record.contradicted_by == ("DENIAL",)


def test_capital_authority_is_a_conjunction_and_every_missing_gate_is_named(
        tmp_path: Path) -> None:
    """A record earns authority only when EVERY gate is measured. The reason string is the
    desk's to-do list."""
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Consumer price index above consensus, core firm",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    reason = a.record.authority_reason
    assert a.record.capital_authority is False
    for gate in ("category", "replay"):
        assert gate in reason


def test_the_record_carries_its_licence_and_retrieval_method(tmp_path: Path) -> None:
    """Public and licensed information only, recorded per row rather than assumed."""
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Statistics office publishes quarterly output",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    assert a.record.licence == "licensed:test"
    assert a.record.retrieval == "fixture"
    assert a.record.robots_ok is True
    assert a.record.source_tier == "WIRE"


def test_a_commodity_headline_names_its_driver_and_its_expression(tmp_path: Path) -> None:
    """The expression step runs even when nothing can be authorised -- the blind spot is the
    output that matters when the forecast cannot be."""
    led = EventLedger(tmp_path / "l.jsonl")
    exposures = [Exposure("AUDUSD", "SOYBEAN", 0.4, 0.05, 0.3, 0.5, 900, 50, True,
                          Status.MEASURED)]
    a = assess(_item("Export tax raised on soybean shipments, cargo backlog grows",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader(), exposures))
    assert "SOYBEAN" in a.record.extra["drivers_named"]
    # No SOYBEAN series in this fake reader, so nothing measured -- and it SAYS so rather than
    # guessing a move.
    assert isinstance(a.record.extra["blind_spots"], list)
    assert a.record.capital_authority is False


def test_the_four_clocks_are_all_recorded(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Rate decision published",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    assert a.record.published_at and a.record.received_at and a.record.processed_at
    assert a.record.priced["lag_s"] == 120.0


def test_the_ledger_round_trips_a_full_assessment(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    a = assess(_item("Rate decision published",
                     published=T0 - timedelta(seconds=120), received=T0),
               **_kit(led, _reader()))
    led.append(a.record)
    back = EventLedger(tmp_path / "l.jsonl").records()[0]
    assert isinstance(back, EventRecord)
    assert back.event_id == a.record.event_id
    assert back.priced["status"] == a.record.priced["status"]
    assert back.extra["triage_score"] == a.record.extra["triage_score"]


def test_a_second_poll_of_the_same_item_writes_no_second_row(tmp_path: Path) -> None:
    led = EventLedger(tmp_path / "l.jsonl")
    item = _item("Rate decision published", published=T0 - timedelta(seconds=120), received=T0)
    a1 = assess(item, **_kit(led, _reader()))
    assert led.append(a1.record) is True
    a2 = assess(item, **_kit(led, _reader()))
    assert led.append(a2.record) is False
    assert len(led.records()) == 1


def test_authority_becomes_possible_only_when_every_gate_is_satisfied(tmp_path: Path) -> None:
    """The positive control: with sample, replay clearance, measured credibility, a measured
    unpriced fraction and a measured expression, the desk CAN act. Without any one of them it
    cannot. Both directions matter -- a gate that never opens is not a gate."""
    led = EventLedger(tmp_path / "l.jsonl")
    cred = CredibilityModel()
    cred.fit({"REUTERS": {"verified": 90, "falsified": 10}}, tier_of={"REUTERS": "WIRE"})

    tax = Taxonomy()
    tax.fit(("central_bank_policy", t) for t in [
        "Federal Reserve raises policy rate by 25 basis points at committee meeting",
        "Bank of England holds bank rate, committee statement published",
        "ECB governing council raises policy rate by 50 basis points",
        "Federal Reserve committee statement leaves policy rate unchanged",
        "Reserve Bank raises cash rate 25 basis points, statement follows",
    ])
    # Give the category real measured reactions so its denominator exists.
    for i in range(MIN_CATEGORY_N):
        led.append(EventRecord(
            event_id=f"seed{i}", category="central_bank_policy",
            received_at=(T0 - timedelta(days=i + 1)).isoformat(),
            processed_at=(T0 - timedelta(days=i + 1)).isoformat(),
            priced={"status": Status.MEASURED, "total_move_sigma": 4.0},
            decay_half_life_s=20.0))

    a = assess(_item("Federal Reserve raises policy rate by 25 basis points, committee statement",
                     published=T0 - timedelta(seconds=120), received=T0),
               taxonomy=tax, credibility=cred, ledger=led, reader=_reader(),
               basis=BASIS, exposures=[], universe=UNIVERSE, aliases=ALIASES,
               source_tier="WIRE", source_licence="licensed:test", retrieval="fixture",
               robots_ok=True, replayed_categories=["central_bank_policy"])

    assert a.record.category == "central_bank_policy"
    assert a.record.capital_authority is True, a.record.authority_reason
    assert a.record.importance > 0.0
    assert a.record.importance_status == Status.MEASURED
    assert a.record.decay_half_life_s == 20.0

    # NEGATIVE CONTROL on the same inputs: remove replay clearance and nothing may be sized.
    denied = assess(
        _item("Federal Reserve raises policy rate by 25 basis points, committee statement",
              published=T0 - timedelta(seconds=120), received=T0),
        taxonomy=tax, credibility=cred, ledger=led, reader=_reader(), basis=BASIS,
        exposures=[], universe=UNIVERSE, aliases=ALIASES, source_tier="WIRE",
        source_licence="licensed:test", retrieval="fixture", robots_ok=True,
        replayed_categories=[])
    assert denied.record.capital_authority is False
    assert denied.record.importance == 0.0
    assert "replay" in denied.record.authority_reason


def test_a_measured_zero_is_not_spelled_like_an_unknown(tmp_path: Path) -> None:
    """"Everything was measured and the answer is do nothing" and "we could not tell" are
    opposite instructions to the allocator. Only the first is a finding, and the schema forbids
    giving them the same value."""
    led = EventLedger(tmp_path / "l.jsonl")
    # Nothing measured at all -> the zero is an UNKNOWN.
    unknown = assess(_item("Some headline", published=T0 - timedelta(seconds=120), received=T0),
                     **_kit(led, _reader()))
    assert unknown.record.importance == 0.0
    assert unknown.record.importance_status == Status.UNMEASURED


# ------------------------------------------------------------------------ sources ----

def test_the_coverage_map_names_its_blind_spots() -> None:
    """A named blind spot is a purchasing decision; an unnamed one is a silent failure."""
    cov = coverage()
    assert cov["domains_total"] == len(DOMAINS)
    assert cov["coverage_fraction"] < 0.4, "the desk sees a narrow slice and must say so"
    blind = set(cov["domains_blind"])
    for expected in ("opec_decisions", "shipping_chokepoints", "equity_earnings_guidance",
                     "trade_policy_tariffs", "conflict_escalation", "index_reconstitution"):
        assert expected in blind


def test_the_licensed_gaps_are_named_with_their_consequence() -> None:
    gaps = {g["gap"]: g for g in coverage()["licensed_gaps"]}
    cal = gaps["economic calendar with consensus AND actuals"]
    assert "no surprise z" in cal["consequence"]
    assert "licensed calendar" in cal["remedy"]
    assert any("sub-minute" in g for g in gaps)
    assert any("wire" in g for g in gaps)


def test_the_domain_list_is_a_coverage_checklist_not_the_taxonomy() -> None:
    """Two lists, on purpose: what we went looking for is knowable in advance; what will happen
    is not."""
    assert "COVERAGE checklist" in coverage()["note"]
    assert "NOT the event taxonomy" in coverage()["note"]


def test_every_source_declares_a_licence_and_a_tier() -> None:
    for s in default_sources():
        assert s.licence and s.licence != ""
        assert s.tier in ("OFFICIAL", "WIRE", "SPECIALIST", "SOCIAL_OSINT", "UNKNOWN")
        assert s.domains, f"{s.source_id} claims no coverage domain"


def test_a_fake_source_satisfies_the_same_protocol() -> None:
    """What makes the whole package testable offline."""
    src = FakeSource(items=[_item("x", published=T0, received=T0)])
    cov = coverage([src])
    assert cov["n_sources"] == 1
    assert len(src.fetch()) == 1
