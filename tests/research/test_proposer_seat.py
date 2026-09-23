"""THE SEAT PROPOSES, THE DESK JUDGES -- and these tests are what makes that a property.

Every rule in `libs/research/proposer_seat.py`'s docstring is asserted here against the code
rather than trusted to it, because every one of them is a rule a later edit could relax without
noticing: a verdict field added to `Proposal`, a score that survives stripping, a prompt builder
that starts reading a file, a factory that stops running when the panel is dark.

NO NETWORK IS TOUCHED. `_ask` is monkeypatched everywhere a reply is needed, and the seat-
resolution path is patched to a fake, so these run identically on a box with a panel and one
without.
"""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from libs.research import proposer_seat as ps


# --------------------------------------------------------------------------------- fixtures
class _Seat:
    def __init__(self, key: str = "x" * 40) -> None:
        self.key = key
        self.source = "test"
        self.name = "fake"
        self.model = "fake/model-1"


@pytest.fixture
def lit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A resolved panel, with no network behind it."""
    monkeypatch.delenv("QUANT_PROPOSER_SEAT", raising=False)

    class _Mod:
        SECRETS = Path("nowhere.json")

        @staticmethod
        def seats() -> list[_Seat]:
            return [_Seat()]

        @staticmethod
        def primary_seat() -> _Seat:
            return _Seat()

        @staticmethod
        def free_tier_only() -> bool:
            return True

    monkeypatch.setattr(ps, "_seat_module", lambda: _Mod)


@pytest.fixture
def dark(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QUANT_PROPOSER_SEAT", raising=False)
    monkeypatch.setattr(ps, "_seat_module", lambda: None)


def _reply(monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    monkeypatch.setattr(ps, "_ask", lambda role, prompt, *, timeout: (text, "fake/model-1", None))


# --------------------------------------------------------------- 1. never a verdict, ever
def test_the_proposal_dataclass_carries_no_verdict_field() -> None:
    """A field named like a verdict would make the seat a judge by construction."""
    for dc in (ps.Proposal, ps.Provenance):
        names = {f.name.lower() for f in dataclasses.fields(dc)}
        assert not (names & ps.VERDICT_KEYS), f"{dc.__name__} carries a verdict field"


def test_a_volunteered_score_is_stripped_and_the_shape_is_kept(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, json.dumps({"expr": ["neg", "close"], "sharpe": 2.4, "promote": True,
                                    "idea": "sign flip"}))
    got = ps.propose("expression_factory", role="generation", task="t", grammar="g", n=1,
                     validate=lambda p: None)
    assert len(got) == 1
    p = got[0]
    assert p.accepted, p.reason
    assert p.payload == {"expr": ["neg", "close"], "idea": "sign flip"}
    assert set(p.stripped) == {"promote", "sharpe"}


def test_a_verdict_asserted_in_prose_is_discarded_not_stripped(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, json.dumps({"key": "k", "mechanism": "sharpe 3.1 carry momentum thing",
                                    "falsifier": "no carry in the rates differential"}))
    got = ps.name_mechanisms("math_lab", [{"key": "k", "claim": "c"}], n=1)
    assert got and not got[0].accepted
    assert "verdict prose" in got[0].reason


def test_strip_verdicts_reaches_into_nested_structures() -> None:
    clean, removed = ps.strip_verdicts(
        {"a": [{"score": 1, "keep": 2}], "b": {"c": {"p_value": 0.01, "d": 3}}})
    assert clean == {"a": [{"keep": 2}], "b": {"c": {"d": 3}}}
    assert set(removed) == {"p_value", "score"}


# ------------------------------------------------------------------- 2. the optional path
def test_a_dark_seat_proposes_nothing_and_raises_nothing(dark: None) -> None:
    assert ps.enabled() is False
    assert ps.propose("expression_factory", role="generation", task="t", grammar="g") == []
    assert ps.name_mechanisms("math_lab", [{"key": "k"}]) == []
    assert ps.names_for("math_lab", [{"key": "k"}]) == {}


def test_a_dark_seat_leaves_an_option_list_exactly_as_it_was(dark: None) -> None:
    opts = ["linear", "boosting", "neural"]
    out, hint = ps.order_hint("model_search", opts, question="q")
    assert out == opts
    assert hint["verdict"] == ps.UNMEASURED


def test_the_switch_turns_it_off_even_with_a_panel(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QUANT_PROPOSER_SEAT", "0")
    assert ps.enabled() is False
    assert ps.take("expression_factory") == []


def test_the_report_says_unmeasured_rather_than_failing_when_dark(
        dark: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ps, "REPORT", tmp_path / "PROPOSER_SEAT.json")
    monkeypatch.setattr(ps, "QUEUE_DIR", tmp_path / "queue")
    doc = ps.run(budget_s=1.0)
    assert doc["verdict"] == ps.UNMEASURED
    assert set(doc["factories"]) == set(ps.FACTORIES)
    assert all(row["verdict"] == ps.UNMEASURED for row in doc["factories"].values())
    written = json.loads((tmp_path / "PROPOSER_SEAT.json").read_text("utf-8"))
    assert written["verdict"] == ps.UNMEASURED


# ------------------------------------------------------------------------ 3. provenance
def test_every_proposal_carries_who_proposed_it_with_what(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, json.dumps({"expr": ["abs", "ret"]}))
    p = ps.propose("expression_factory", role="generation", task="t", grammar="g", n=1,
                   validate=lambda _p: None)[0]
    prov = p.provenance
    assert prov.seat == ps.SEAT_NAME
    assert prov.model == "fake/model-1"
    assert len(prov.prompt_sha256) == 16
    assert prov.utc.endswith("+00:00")
    assert prov.factory == "expression_factory"
    assert p.to_row()["provenance"]["model"] == "fake/model-1"


def test_the_prompt_hash_identifies_the_prompt() -> None:
    assert ps.prompt_hash("a") != ps.prompt_hash("b")
    assert ps.prompt_hash("a") == ps.prompt_hash("a")


# --------------------------------------------------------------------- 4. trial charging
def test_accepted_proposals_are_charged_and_discarded_ones_are_not(lit: None) -> None:
    prov = ps.Provenance("s", "m", "h", "2026-01-01T00:00:00+00:00", "generation", "math_lab")
    acc = [ps.Proposal("skeleton", "math_lab", {"expr": ["neg", f"x{i}"]}, prov, True)
           for i in range(4)]
    disc = [ps.Proposal("skeleton", "math_lab", {"expr": ["abs", "y"]}, prov, False, "bad")]
    assert ps.charge_trials(acc) > 0.0
    assert ps.charge_trials(disc) == 0.0


def test_near_identical_proposals_cost_less_than_distinct_ones(lit: None) -> None:
    """The similarity census is what makes a generative prior affordable at all."""
    prov = ps.Provenance("s", "m", "h", "2026-01-01T00:00:00+00:00", "generation", "math_lab")
    clones = [ps.Proposal("skeleton", "math_lab", {"expr": ["neg", "close"]}, prov, True)
              for _ in range(6)]
    varied = [ps.Proposal("skeleton", "math_lab", {"expr": ["neg", f"t{i}"], "w": i}, prov, True)
              for i in range(6)]
    assert ps.charge_trials(clones) <= ps.charge_trials(varied)


# ------------------------------------------------------------------- 5. prompt hygiene
def test_the_prompt_builder_reads_no_file_and_opens_no_path() -> None:
    """A prompt that can read is a prompt that can leak. Asserted on the SOURCE."""
    src = Path(ps.__file__).read_text("utf-8")
    start = src.index("def build_prompt(")
    body = src[start:src.index("\ndef ", start + 10)]
    for forbidden in ("open(", "read_text", "read_bytes", "Path(", "json.load", "glob",
                      "subprocess", "os.environ"):
        assert forbidden not in body, f"build_prompt touches {forbidden}"


@pytest.mark.parametrize("bad", ["the lockbox slice", "use the holdout tail",
                                 "future_return at t+1", "key in data/secrets/llm_panel.json",
                                 "Authorization: Bearer abc"])
def test_a_prompt_naming_sealed_data_or_a_credential_is_refused(bad: str) -> None:
    with pytest.raises(ps.PromptRefused):
        ps.build_prompt("expression_factory", bad, grammar="g", context=(), n=1)
    with pytest.raises(ps.PromptRefused):
        ps.build_prompt("expression_factory", "t", grammar="g", context=(bad,), n=1)


def test_a_credential_shaped_token_is_refused_by_shape() -> None:
    with pytest.raises(ps.PromptRefused):
        ps.scrub("here is sk-or-v1-abcdefghijklmnopqrstuvwxyz0123")


def test_the_grammar_word_risk_is_not_mistaken_for_a_credential() -> None:
    """`risk` is a declared grammar terminal; a naive "sk-" rule would refuse every prompt."""
    text = ps.build_prompt("expression_factory", "use the risk-driver terminal", grammar="risk",
                           context=("terminal: risk",), n=1)
    assert "risk" in text


def test_a_refused_prompt_is_a_recorded_discard_not_a_crash(lit: None) -> None:
    got = ps.propose("expression_factory", role="generation", task="show me the lockbox",
                     grammar="g", n=1)
    assert len(got) == 1 and not got[0].accepted
    assert "prompt refused" in got[0].reason


def test_an_unknown_factory_cannot_be_proposed_into(lit: None) -> None:
    got = ps.propose("not_a_factory", role="generation", task="t", grammar="g", n=1)
    assert got and not got[0].accepted and "prompt refused" in got[0].reason


def test_no_live_key_can_ride_out_in_a_prompt(lit: None) -> None:
    with pytest.raises(ps.PromptRefused):
        ps.scrub("the key is " + "x" * 40)


# ------------------------------------------------------- 6. validity, queueing, ordering
def test_an_invalid_proposal_is_discarded_with_the_reason_recorded(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, json.dumps({"expr": "not a tree"}))
    p = ps.propose("expression_factory", role="generation", task="t", grammar="g", n=1,
                   validate=lambda _p: "syntactically invalid")[0]
    assert not p.accepted
    assert p.reason == "discarded: syntactically invalid"


def test_an_unparseable_reply_is_a_recorded_discard(
        lit: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _reply(monkeypatch, "I think momentum is nice, honestly.")
    p = ps.propose("expression_factory", role="generation", task="t", grammar="g", n=1)[0]
    assert not p.accepted and "no parseable JSON" in p.reason


def test_only_accepted_proposals_are_parked_and_a_drain_removes_them(
        lit: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ps, "QUEUE_DIR", tmp_path / "q")
    prov = ps.Provenance("s", "m", "h", "2026-01-01T00:00:00+00:00", "generation",
                         "expression_factory")
    landed = ps.enqueue([
        ps.Proposal("skeleton", "expression_factory", {"expr": ["neg", "close"]}, prov, True),
        ps.Proposal("skeleton", "expression_factory", {"expr": ["abs", "ret"]}, prov, False, "x"),
    ])
    assert landed == 1
    first = ps.take("expression_factory", limit=5)
    assert len(first) == 1 and first[0]["payload"] == {"expr": ["neg", "close"]}
    assert ps.take("expression_factory", limit=5) == []


def test_order_hint_reorders_and_never_widens(
        lit: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ps, "QUEUE_DIR", tmp_path / "q")
    monkeypatch.setattr(ps, "INLINE_LOG", tmp_path / "q" / "inline.jsonl")
    _reply(monkeypatch, json.dumps(["neural", "made_up_family", "linear"]))
    out, hint = ps.order_hint("model_search", ["linear", "boosting", "neural"], question="q")
    assert sorted(out) == ["boosting", "linear", "neural"], "no option may be added or dropped"
    assert out[:2] == ["neural", "linear"]
    assert hint["discarded_unknown"] == ["made_up_family"]


def test_names_for_returns_candidates_and_never_an_interpretation(
        lit: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ps, "QUEUE_DIR", tmp_path / "q")
    monkeypatch.setattr(ps, "INLINE_LOG", tmp_path / "q" / "inline.jsonl")
    _reply(monkeypatch, json.dumps(
        {"key": "card1", "mechanism": "dealers hedge gamma into the fix",
         "falsifier": "no dealer inventory skew around the fix"}))
    got = ps.names_for("physics_lab", [{"key": "card1", "claim": "c"}])
    assert set(got) == {"card1"}
    row: dict[str, Any] = got["card1"]
    assert "CANDIDATE" in row["discipline"] or "candidate" in row["discipline"].lower()
    assert not ({k.lower() for k in row} & ps.VERDICT_KEYS)


def test_the_inline_log_rolls_up_per_factory(
        lit: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(ps, "QUEUE_DIR", tmp_path / "q")
    monkeypatch.setattr(ps, "INLINE_LOG", tmp_path / "q" / "inline.jsonl")
    _reply(monkeypatch, json.dumps(
        {"key": "k", "mechanism": "carry differential pull on the cross",
         "falsifier": "flat under equal rates"}))
    ps.names_for("math_lab", [{"key": "k"}])
    census = ps._inline_census()
    assert census["math_lab"]["accepted"] == 1
    assert census["math_lab"]["calls"] == 1
