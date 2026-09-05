"""Tests for check_swap_reliability (R0595).

The three refusals are the load-bearing part of this organ, so most of what is pinned here is
what it declines to say. A reliability number published from three runs, or across the unfunded
roster collapse, or over two seats wearing one name, is a number a reader would act on.
"""

from __future__ import annotations

import json

from scripts import check_swap_reliability as csr


def _row(ts: str, provider: str, model: str, *, ok: bool = True) -> dict[str, object]:
    r: dict[str, object] = {"ts": ts, "provider": provider, "model": model}
    if ok:
        r["response"] = "### RECOMMENDATION 1: something substantive"
    else:
        r["error"] = "<HTTPError 400: 'Bad Request'>"
    return r


def _log(tmp_path, rows):
    p = tmp_path / "panel.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", "utf-8")
    return p


def _runs(seat, model, n, *, ok, start=0, size=1, other_seats=0):
    """`n` runs of one seat on one model, optionally padded to a given panel size."""
    out = []
    for i in range(start, start + n):
        ts = f"2026-07-{i + 1:02d}T00:00:00+00:00"
        out.append(_row(ts, seat, model, ok=ok))
        for j in range(other_seats):
            out.append(_row(ts, f"filler{j}", "vendor/filler"))
    assert size >= 1
    return out


# ------------------------------------------------------------------------ the positive control

def test_A_REAL_REGRESSION_IS_CAUGHT(tmp_path) -> None:
    """POSITIVE CONTROL, and it comes first for the reason the desk keeps re-learning: a detector
    never shown to FIND a known-present defect has not been validated, only its silences observed.
    Same seat, same panel size, four runs either side -- only the model and the outcome move."""
    rows = (_runs("qwen", "vendor/old", 4, ok=True, start=0)
            + _runs("qwen", "vendor/new", 4, ok=False, start=4))
    rep = csr.report(_log(tmp_path, rows))
    assert rep["status"] == "REGRESSED"
    assert rep["swaps"][0]["rate_before"] == 1.0
    assert rep["swaps"][0]["rate_after"] == 0.0
    assert "rollback" in rep["next_action"]


def test_AN_IMPROVEMENT_IS_NOT_A_REGRESSION(tmp_path) -> None:
    """The other half of the control. This organ must be able to return both answers, or its OK
    carries no information (L1.63: a certificate whose partition cannot fail is welded open)."""
    rows = (_runs("qwen", "vendor/old", 4, ok=False, start=0)
            + _runs("qwen", "vendor/new", 4, ok=True, start=4))
    rep = csr.report(_log(tmp_path, rows))
    assert rep["status"] == "OK"
    assert rep["swaps"][0]["verdict"] == "MEASURED"
    assert rep["swaps"][0]["delta"] == 1.0


# ----------------------------------------------------------------------------- the three refusals

def test_TOO_FEW_RUNS_IS_UNDERPOWERED_NOT_A_RATE(tmp_path) -> None:
    """Two runs against four is not a rate. The old model's two runs happen to be 0/2, which would
    read as a catastrophic 0% -> 100% improvement if the organ published everything it could
    compute."""
    rows = (_runs("qwen", "vendor/old", 2, ok=False, start=0)
            + _runs("qwen", "vendor/new", 4, ok=True, start=2))
    rep = csr.report(_log(tmp_path, rows))
    assert rep["swaps"][0]["verdict"] == "UNDERPOWERED"
    assert "rate_before" not in rep["swaps"][0], "a refused swap published a rate anyway"


def test_THE_UNFUNDED_ROSTER_COLLAPSE_IS_CONFOUNDED_NOT_A_MODEL_FAILURE(tmp_path) -> None:
    """THE REAL EVENT THIS EXISTS FOR. On 2026-07-28 the panel fell 13 seats -> 4 when credits ran
    out, and seats either side of it were also moved onto `:free` model ids. A naive before/after
    reads cohere 100% -> 18% and blames the model for an unpaid invoice."""
    rows = (_runs("cohere", "vendor/paid", 4, ok=True, start=0, other_seats=12)
            + _runs("cohere", "vendor/paid:free", 4, ok=False, start=4, other_seats=3))
    rep = csr.report(_log(tmp_path, rows))
    swap = next(s for s in rep["swaps"] if s["seat"] == "cohere")
    assert swap["verdict"] == "CONFOUNDED"
    assert "rate_before" not in swap
    assert rep["status"] != "REGRESSED", "an unpaid invoice was reported as a model regression"


def test_TWO_SEATS_SHARING_A_NAME_YIELD_ONE_REFUSAL_NOT_FIFTEEN_FAKE_SWAPS(tmp_path) -> None:
    """The roster really does carry two `ai` seats and two `openai` seats. Their rows alternate, so
    every run looks like a model change: on the real log the first draft emitted FIFTEEN swaps for
    `ai`, none of which were swaps. Reporting an artifact fifteen times is how a detector gets
    acked into silence, and counting them inflates the denominator with non-events."""
    rows = []
    for i in range(6):
        ts = f"2026-07-{i + 1:02d}T00:00:00+00:00"
        rows += [_row(ts, "ai", "x-ai/grok"), _row(ts, "ai", "z-ai/glm")]
    rep = csr.report(_log(tmp_path, rows))
    assert [s["verdict"] for s in rep["swaps"]] == ["AMBIGUOUS-SEAT"]
    assert rep["n_swaps"] == 1
    assert rep["ambiguous_seats"] == ["ai"]


# --------------------------------------------------------------------------- absence and vacuity

def test_AN_ABSENT_LOG_IS_UNMEASURED_NOT_CLEAN(tmp_path) -> None:
    """WS-005. "No swap hurt a seat" and "nobody looked" must never be byte-identical (L1.28a)."""
    rep = csr.report(tmp_path / "nope.jsonl")
    assert rep["status"] == "UNMEASURED"
    assert rep["measured"] is False
    assert any(r["status"] == "ABSENT" for r in rep["provenance"])


def test_AN_UNREADABLE_LOG_IS_DISTINCT_FROM_AN_ABSENT_ONE(tmp_path) -> None:
    """L1.55: "no producer has ever run" and "one ran and wrote garbage" demand opposite repairs,
    and a desk that cannot tell them apart debugs the wrong organ."""
    p = tmp_path / "panel.jsonl"
    p.write_text("{not json\n{\"ts\": 1}\n", "utf-8")
    rep = csr.report(p)
    assert [r["status"] for r in rep["provenance"]] == ["READ"]
    assert rep["malformed_rows"] == 2, "torn rows vanished instead of being counted (L1.60)"


def test_OK_IS_UNREACHABLE_WITHOUT_A_MEASURED_SWAP(tmp_path) -> None:
    """L1.57, and the first draft of this organ failed it on real data: it printed OK over 38
    swaps of which ZERO were gradeable. A verdict about swaps needs a denominator of swaps."""
    rows = (_runs("qwen", "vendor/old", 2, ok=True, start=0)
            + _runs("qwen", "vendor/new", 2, ok=True, start=2))
    rep = csr.report(_log(tmp_path, rows))
    assert rep["n_swaps"] >= 1
    assert rep["tally"].get("MEASURED") is None
    assert rep["status"] == "ALL-REFUSED", "a verdict was earned over zero measured swaps"
    assert "coverage gap, not a clean bill" in rep["next_action"]


def test_NO_SWAPS_AT_ALL_IS_ITS_OWN_ANSWER(tmp_path) -> None:
    """model_upgrade.py has never applied a panel swap. An empty result is the correct measurement
    of an upgrade path that has not fired -- and it is not the same claim as ALL-REFUSED."""
    rep = csr.report(_log(tmp_path, _runs("qwen", "vendor/only", 6, ok=True)))
    assert rep["status"] == "NO-SWAPS-YET"
    assert rep["n_swaps"] == 0


def test_completed_matches_the_panels_own_definition_of_a_lost_seat(tmp_path) -> None:
    """run_external_panel records a loss as `"response" not in r`. Reading it any other way here
    would let this organ and the panel's own telemetry disagree about the same run (L1.61)."""
    assert csr._completed({"response": "text"})
    assert not csr._completed({"error": "boom"})
    assert not csr._completed({})
    assert not csr._completed({"response": "   "})
