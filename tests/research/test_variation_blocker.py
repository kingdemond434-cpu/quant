"""A re-parameterisation must be blocked; a genuinely new question must not be.

Both directions carry real cost and they are not symmetric in the way caution assumes. Letting a
duplicate through charges multiplicity budget for a question already asked and inflates the trial
count DSR corrects against. Blocking a NEW idea silently narrows the search space -- and this desk
has a measured, expensive instance of an over-tight funnel (420 candidates, 0 survivors, behind
campaign-constant gates and a $100k capacity floor). Under L1.21a the timid error is the more
expensive one, so the near-duplicate bar is set high and these tests pin both sides of it.
"""

from __future__ import annotations

from libs.research import variation_blocker as VB


class _H:
    def __init__(self, family="carry", subtype="funding_carry", symbol="BTCUSDT",
                 edge_source="funding/carry", mechanism="risk_premium", params=None,
                 failure_modes=()):
        self.family, self.subtype, self.symbol = family, subtype, symbol
        self.edge_source, self.mechanism = edge_source, mechanism
        self.params = params or {"horizon_days": 7}
        self.failure_modes = list(failure_modes)


class TestTheDuplicateIsBlocked:
    def test_a_lookback_tweak_is_blocked_as_the_same_idea(self, tmp_path):
        p = tmp_path / "led.jsonl"
        first = _H(params={"horizon_days": 20})
        VB.record(first, VB.screen(first, path=p), path=p)
        again = _H(params={"horizon_days": 21})       # same idea, one knob turned
        v = VB.screen(again, path=p)
        assert not v.allowed
        assert "multiplicity" in v.reason

    def test_the_same_mechanism_on_another_symbol_is_blocked(self, tmp_path):
        p = tmp_path / "led.jsonl"
        a = _H(symbol="BTCUSDT")
        VB.record(a, VB.screen(a, path=p), path=p)
        assert not VB.screen(_H(symbol="ETHUSDT"), path=p).allowed

    def test_a_block_records_WHAT_it_duplicated(self, tmp_path):
        """A block that does not name its duplicate is unauditable, and the ledger is supposed to
        be the map of the space already searched."""
        p = tmp_path / "led.jsonl"
        first = _H()
        row = VB.record(first, VB.screen(first, path=p), hyp_id="H-001", path=p)
        v = VB.screen(_H(params={"horizon_days": 8}), path=p)
        assert v.duplicate_of == row["id"] == "H-001"
        assert v.similarity == 1.0


class TestTheNewIdeaIsNotBlocked:
    def test_a_different_mechanism_passes(self, tmp_path):
        p = tmp_path / "led.jsonl"
        a = _H(family="carry", subtype="funding_carry", edge_source="funding/carry")
        VB.record(a, VB.screen(a, path=p), path=p)
        b = _H(family="flow", subtype="netflow_momentum", edge_source="onchain/netflow",
               mechanism="flow_imbalance", params={"horizon_days": 5})
        assert VB.screen(b, path=p).allowed

    def test_the_same_family_at_a_different_horizon_BUCKET_passes(self, tmp_path):
        """A 7-day and a 90-day carry signal are genuinely different questions -- the bucketing is
        coarse to collapse knob-turning, not to collapse the horizon dimension itself."""
        p = tmp_path / "led.jsonl"
        a = _H(params={"horizon_days": 7})
        VB.record(a, VB.screen(a, path=p), path=p)
        assert VB.screen(_H(params={"horizon_days": 90}), path=p).allowed

    def test_an_empty_ledger_blocks_nothing(self, tmp_path):
        assert VB.screen(_H(), path=tmp_path / "none.jsonl").allowed

    def test_a_previously_BLOCKED_idea_does_not_itself_become_a_blocker(self, tmp_path):
        """Only ACCEPTED ideas define the searched space. If blocks blocked, one false block would
        propagate into a permanent hole in the search space."""
        p = tmp_path / "led.jsonl"
        a = _H()
        VB.record(a, VB.screen(a, path=p), hyp_id="A", path=p)
        dup = _H(params={"horizon_days": 8})
        VB.record(dup, VB.screen(dup, path=p), hyp_id="B", path=p)
        v = VB.screen(_H(params={"horizon_days": 9}), path=p)
        assert v.duplicate_of == "A", "the block must cite the ACCEPTED original, not the block"


class TestTelemetryAnswersWhyIdeasDie:
    def test_novel_rate_is_the_honest_yield(self, tmp_path):
        p = tmp_path / "led.jsonl"
        for i, h in enumerate([
            _H(),
            _H(params={"horizon_days": 8}),                       # dup
            _H(family="vol", subtype="vol_dispersion", edge_source="vol/dispersion",
               params={"horizon_days": 5}),
            _H(params={"horizon_days": 9}),                       # dup
        ]):
            VB.record(h, VB.screen(h, path=p), hyp_id=f"H{i}", generator="seat_a", path=p)
        t = VB.telemetry(path=p)
        assert t["n"] == 4
        assert t["n_blocked"] == 2
        assert t["novel_rate"] == 0.5, (
            "four ideas produced, two genuinely new questions -- volume without this is "
            "throughput, not information")

    def test_it_names_the_saturated_fingerprint(self, tmp_path):
        p = tmp_path / "led.jsonl"
        for i in range(5):
            h = _H(params={"horizon_days": 7 + i})
            VB.record(h, VB.screen(h, path=p), hyp_id=f"H{i}", path=p)
        top = VB.telemetry(path=p)["most_attempted_fingerprints"][0]
        assert top[1] == 5, "five attempts at one fingerprint must be visible as such"

    def test_empty_ledger_reports_honestly(self, tmp_path):
        assert VB.telemetry(path=tmp_path / "none.jsonl")["n"] == 0


def test_the_near_duplicate_bar_is_high_on_purpose():
    """A regression fence on the REASONING. Lowering this bar trades a cheap wasted trial for the
    risk of silently deleting a genuinely new question -- the more expensive error (L1.21a)."""
    assert VB.NEAR_DUP_JACCARD >= 0.85
