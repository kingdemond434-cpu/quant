"""THE SECOND FAMILY (L1.33) -- 53 statements, untested, and the LABEL is the entire product.

The capability hunt proved the pattern: two model families propose INDEPENDENTLY, and cross-family
agreement is EVIDENCE while agreement within one family is STYLE. A model cannot see its own blind
spot, so asking Claude twice returns the first answer with more confidence.

Every other exploration organ on the desk was single-family -- blindspot_max, the prober,
blindrediscovery and the sweep's meta seat all think in exactly one model's priors, which is
precisely the failure mode they exist to detect, applied to themselves.

SO THE ONE THING THAT MUST NEVER BREAK IS THE HONESTY OF THE LABEL. The GPT seat is currently
unfunded (402), which means every call today returns unavailable -- and if that degraded to
CONFIRMED, or to anything a reader could mistake for corroboration, the desk would spend the credit
gap citing one model's opinion as cross-family agreement. SOLO exists to make that impossible, and
it is the assertion this file leads with.

The second property: `ask_second_family` NEVER RAISES. An organ whose exploration pass dies because
a partner seat is unfunded produces nothing at all, which is worse than producing a single-family
result that says so.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from libs.research import second_family as SF


def _op(**over) -> SF.SecondOpinion:
    base = {"available": True, "text": "MISSED: the funding clock is unmeasured on bybit",
            "model": "gpt-9", "context": "blindspot_max"}
    base.update(over)
    return SF.SecondOpinion(**base)


# ============================================================ the label

def test_an_UNAVAILABLE_partner_is_SOLO_and_says_it_is_NOT_corroboration() -> None:
    """THE ASSERTION THE MODULE EXISTS FOR. The seat is unfunded today, so this is the path every
    call takes right now. If it degraded to CONFIRMED the desk would spend the whole credit gap
    citing one model's opinion as cross-family agreement -- and the citation would outlive the
    gap."""
    v = SF.merge_verdict("I found three things", _op(available=False, reason="402 no credit"))
    assert v["verdict"] == "SOLO"
    assert v["reason"] == "402 no credit"
    assert "NOT cross-family corroboration" in v["note"]


def test_SOLO_carries_the_REASON_so_a_credit_gap_is_distinguishable_from_a_crash() -> None:
    """"The partner did not run" is one fact; "the partner is unfunded" is another, and only the
    second can be fixed with a payment."""
    for reason in ("402 no credit", "second family unimportable: ModuleNotFoundError",
                   "empty response"):
        assert SF.merge_verdict("x", _op(available=False, reason=reason))["reason"] == reason


def test_BOTH_families_producing_findings_is_CONFIRMED() -> None:
    """The strongest signal this desk can generate without live evidence."""
    v = SF.merge_verdict("I found three things", _op())
    assert v["verdict"] == "CONFIRMED"
    assert v["partner_chars"] > 0


def test_CONFIRMED_tells_the_reader_to_READ_THE_DELTA_not_average_it() -> None:
    """The delta between two families IS the blind spot each could not see alone. Averaging them
    -- the natural instinct when two reports disagree -- destroys exactly the information the
    second family was funded to produce."""
    note = SF.merge_verdict("x", _op())["note"]
    assert "DELTA" in note and "do not" in note and "average" in note


def test_a_PARTNER_ONLY_finding_is_CONTESTED_not_confirmed() -> None:
    """The first family found nothing and the partner did. That is the second-strongest signal
    available, because the delta is a MEASURED blind spot -- and calling it CONFIRMED would claim
    an agreement that did not happen."""
    v = SF.merge_verdict("", _op())
    assert v["verdict"] == "CONTESTED"
    assert "candidate blind spot" in v["note"]


def test_a_partner_that_ran_and_found_NOTHING_is_also_CONTESTED() -> None:
    """An honest null from an independent family is a real result, and it is NOT agreement. The
    verdict has to be distinguishable from CONFIRMED or a null would read as corroboration."""
    v = SF.merge_verdict("I found three things", _op(text="   "))
    assert v["verdict"] == "CONTESTED"


@pytest.mark.parametrize("own", [None, "", "   ", 0])
def test_a_falsy_own_finding_never_produces_CONFIRMED(own) -> None:
    """CONFIRMED requires BOTH sides to have said something. A None from the calling organ must
    not be coerced into a finding."""
    assert SF.merge_verdict(own, _op())["verdict"] != "CONFIRMED"


def test_UNAVAILABILITY_OUTRANKS_everything_else() -> None:
    """Checked first, and it has to be: a partner that could not run has no text, so any later
    branch would classify it on emptiness rather than on absence -- and CONTESTED reads as 'the
    partner disagreed', which is a claim about an opinion nobody obtained."""
    assert SF.merge_verdict("", _op(available=False, reason="down"))["verdict"] == "SOLO"
    assert SF.merge_verdict("x", _op(available=False, reason="down"))["verdict"] == "SOLO"


def test_the_three_verdicts_are_the_only_three() -> None:
    """A fourth label added later without a stated meaning is how SOLO quietly becomes a synonym
    for CONFIRMED in someone's summary."""
    seen = {SF.merge_verdict(o, p)["verdict"]
            for o in ("x", "")
            for p in (_op(), _op(text=""), _op(available=False, reason="r"))}
    assert seen == {"CONFIRMED", "CONTESTED", "SOLO"}


# ============================================================ it never raises

def test_an_UNIMPORTABLE_partner_degrades_rather_than_raising(monkeypatch) -> None:
    """An organ whose exploration pass DIES because a partner seat is unfunded produces nothing at
    all -- strictly worse than a single-family result that says so."""
    import builtins
    real = builtins.__import__

    def boom(name, *a, **k):
        if "run_strategic_director" in name:
            raise ImportError("no such module")
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", boom)
    op = SF.ask_second_family("prompt", context="blindspot_max")
    assert op.available is False
    assert "unimportable" in op.reason
    assert op.context == "blindspot_max"


def test_an_ERROR_from_the_seat_degrades_with_the_error_recorded(monkeypatch,
                                                                 tmp_path: Path) -> None:
    monkeypatch.setattr(SF, "_LEDGER", tmp_path / "log.json")
    import scripts.run_strategic_director as RSD
    monkeypatch.setattr(RSD, "_ask", lambda p, m, timeout=0: ("", "402 payment required"))
    op = SF.ask_second_family("prompt", context="prober")
    assert op.available is False and op.reason == "402 payment required"


def test_an_EMPTY_response_is_UNAVAILABLE_not_an_honest_null(monkeypatch,
                                                             tmp_path: Path) -> None:
    """A blank completion is a failed call, not a partner saying 'nothing missed'. Recording it as
    available would produce a CONTESTED verdict from a request that never landed."""
    monkeypatch.setattr(SF, "_LEDGER", tmp_path / "log.json")
    import scripts.run_strategic_director as RSD
    monkeypatch.setattr(RSD, "_ask", lambda p, m, timeout=0: ("   ", ""))
    op = SF.ask_second_family("prompt", context="prober")
    assert op.available is False and op.reason == "empty response"


def test_a_SUCCESSFUL_call_is_available_and_carries_the_model(monkeypatch,
                                                              tmp_path: Path) -> None:
    """The positive control: a module that always returned unavailable would satisfy every
    degradation test above and never actually consult anyone."""
    monkeypatch.setattr(SF, "_LEDGER", tmp_path / "log.json")
    import scripts.run_strategic_director as RSD
    monkeypatch.setattr(RSD, "_ask", lambda p, m, timeout=0: ("MISSED: the bybit clock", ""))
    op = SF.ask_second_family("prompt", context="sweep")
    assert op.available is True
    assert op.text.startswith("MISSED:") and op.model == RSD.MODEL
    assert SF.merge_verdict("own findings", op)["verdict"] == "CONFIRMED"


# ============================================================ the ledger

def test_EVERY_CALL_IS_LOGGED_so_a_dead_partner_is_a_MEASURED_fact(monkeypatch,
                                                                   tmp_path: Path) -> None:
    """"The partner is dead" has to be a fact with a date, not an impression -- funding the seat
    is a spending decision, and it should be justified with evidence."""
    ledger = tmp_path / "log.json"
    monkeypatch.setattr(SF, "_LEDGER", ledger)
    import scripts.run_strategic_director as RSD
    monkeypatch.setattr(RSD, "_ask", lambda p, m, timeout=0: ("", "402"))
    SF.ask_second_family("p", context="blindspot_max")
    SF.ask_second_family("p", context="prober")
    calls = json.loads(ledger.read_text("utf-8"))["calls"]
    assert len(calls) == 2
    assert [c["context"] for c in calls] == ["blindspot_max", "prober"]
    assert all(c["available"] is False and c["at"] for c in calls)


def test_the_ledger_records_a_CHAR_COUNT_and_NEVER_THE_TEXT() -> None:
    """The partner's output can name positions and internal artifact paths. A call log is not a
    place to keep it, and the length is what the availability question actually needs."""
    d = _op(text="a very long finding about the book").to_dict()
    assert d["chars"] == len("a very long finding about the book")
    assert "text" not in d
    assert "long finding" not in json.dumps(d)


def test_the_ledger_is_BOUNDED_so_it_cannot_fill_the_disk(monkeypatch,
                                                          tmp_path: Path) -> None:
    """Every exploration pass on every organ calls this. Unbounded, it grows without limit -- and
    a full disk takes down the recorders, which costs tape that cannot be re-acquired."""
    ledger = tmp_path / "log.json"
    ledger.write_text(json.dumps({"calls": [{"available": False} for _ in range(1500)]}), "utf-8")
    monkeypatch.setattr(SF, "_LEDGER", ledger)
    SF._log(_op(available=False, reason="402"))
    assert len(json.loads(ledger.read_text("utf-8"))["calls"]) == 1000


def test_a_CORRUPT_ledger_starts_a_fresh_one_rather_than_losing_the_call(
        monkeypatch, tmp_path: Path) -> None:
    ledger = tmp_path / "log.json"
    ledger.write_text("{not json", "utf-8")
    monkeypatch.setattr(SF, "_LEDGER", ledger)
    SF._log(_op())
    assert len(json.loads(ledger.read_text("utf-8"))["calls"]) == 1


def test_an_UNWRITABLE_ledger_never_breaks_the_call(monkeypatch, tmp_path: Path) -> None:
    """Telemetry must not take down the thing it observes. An organ losing its exploration pass
    because a log file was read-only is the tail wagging the dog."""
    monkeypatch.setattr(SF, "_LEDGER", tmp_path / "nope" / "log.json")
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("ro")))
    SF._log(_op())          # must not raise


# ============================================================ the brief

def test_the_brief_forbids_REVIEWING_or_RE_RANKING_the_first_familys_list() -> None:
    """A partner that reviews is a second opinion on the same framing, which is exactly what a
    single family already gives you. The value is in the region the first family's priors could
    not see."""
    p = " ".join(SF.blindspot_prompt("blindspot_max", "we found A, B, C").split())
    assert "NOT TO REVIEW OR RE-RANK" in p
    assert "MISSED" in p


def test_the_brief_states_WHY_a_second_family_exists() -> None:
    """Without the reason, the seat re-derives the first family's answer and reports agreement --
    which reads as the strongest possible signal and is the weakest."""
    p = " ".join(SF.blindspot_prompt("prober", "findings").split())
    assert "cannot see its own blind spot" in p
    assert "different ones" in p


def test_the_brief_demands_AN_EVIDENCE_CHECK_for_whatever_it_names() -> None:
    """A named blind spot with no way to confirm it is another unfalsifiable finding, and the desk
    has enough of those."""
    p = SF.blindspot_prompt("sweep", "findings")
    assert "EVIDENCE:" in p and "confirm or kill" in p


def test_the_brief_makes_AN_HONEST_NULL_a_legitimate_answer() -> None:
    """Padding is a defect. Without this line the partner invents a blind spot on every call,
    because 'NOTHING MISSED' feels like a failure to deliver."""
    p = " ".join(SF.blindspot_prompt("sweep", "findings").split())
    assert "NOTHING MISSED" in p
    assert "honest null" in p and "padding is a defect" in p


def test_the_first_familys_findings_are_TRUNCATED_so_one_organ_cannot_blow_the_context() -> None:
    """A sweep can produce megabytes. Sent whole it costs the call, and the truncation point is
    where the brief itself would fall out of the window."""
    huge = "x" * 50_000
    p = SF.blindspot_prompt("sweep", huge)
    # Measured on the findings SECTION, not on the whole prompt: the surrounding template contains
    # its own 'x' characters, so a global count is off by however many the wording happens to have
    # and would break the next time somebody rephrased a sentence.
    findings = p.split("--- THEIR FINDINGS ---")[1].split("--- YOUR OUTPUT ---")[0]
    assert findings.count("x") == 6_000
    assert "YOUR OUTPUT" in p, "the instructions must survive the truncation"


def test_the_brief_names_the_CALLING_ORGAN() -> None:
    """The same partner serves blindspot_max, the prober, blindrediscovery and the sweep. Without
    the context it answers a generic question and the answer fits none of them."""
    assert "blindrediscovery" in SF.blindspot_prompt("blindrediscovery", "findings")
