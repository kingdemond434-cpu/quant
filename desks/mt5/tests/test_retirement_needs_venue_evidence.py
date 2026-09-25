"""A missing chart must never retire a certificate -- at EVERY pen, not just the sealed one.

MEASURED 2026-09-24 on the trading box. `data/UNIVERSAL_SURVIVORS.canon.json` fell from 58 rows
to 28 on 2026-09-20/21. Thirty rows moved to `retired_certificates`; twenty-four of them carry

    "symbol 'EURCHF' has no EURCHF_H1.parquet; no forward clock can replay it"

against nine FX majors and crosses whose hourly parquets are 1.0-1.4 MB, none byte-empty, all
present in `data/universe/universe.json`: AUDCAD, AUDNZD, AUDUSD, EURCHF, EURGBP, EURUSD, NZDCAD,
USDCAD, USDCHF. AUDCHF took the identical retirement on the 21st and `certificate_truth` restored
it on the 23rd -- a round trip that proves the predicate was false when it fired.

`external_gauntlet.certificate_retirement_reason` had already been corrected away from that rule
("eligibility for a NEW test is not proof for revoking an EXISTING result"), and
`test_certificates_cannot_be_lost_to_an_outage` pins the correction -- at ONE pen.
`desks/mt5/scripts/retire_uncashable_certs.py`, on the battery clock, kept a private copy of the
old rule. These tests pin the second pen to the first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
for _p in (str(_DESK / "scripts"), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import retire_uncashable_certs as ruc  # noqa: E402

SRC = (_DESK / "scripts" / "retire_uncashable_certs.py").read_text("utf-8")
#: THE CODE, with the module docstring and every comment stripped. The prose is where the rule
#: and its history are written down, so a check over the prose would forbid documenting the very
#: thing it is enforcing -- the same trap `test_certificates_cannot_be_lost_to_an_outage` hit
#: with `ADOPT_CODE` and `git add -A`.
CODE = "\n".join(ln for ln in SRC.split('"""', 2)[2].splitlines()
                 if not ln.lstrip().startswith("#"))


def _judge(sym: str, meta: dict) -> str | None:
    """A stand-in for the sealed predicate: venue evidence only."""
    row = meta.get(sym)
    if isinstance(row, dict) and row.get("tradeable") is False:
        return f"symbol {sym!r} explicitly disallows new trades"
    return None


META = {"EURCHF": {"tradeable": True}, "AFG": {"tradeable": False}}


def test_the_file_no_longer_carries_a_parquet_predicate() -> None:
    assert "_H1.parquet" not in CODE, "a missing chart must never retire a certificate"
    assert "no forward clock can replay it" not in CODE
    assert "BARS /" not in CODE


def test_the_venue_question_has_exactly_one_owner() -> None:
    assert "certificate_retirement_reason" in CODE
    assert "why = judge(sym, meta)" in CODE
    # and nothing re-decides it locally
    fn = CODE[CODE.index("def _reason("):CODE.index("\n\ndef retire(")]
    for local in ("sym not in meta", ".exists()", 'get("tradeable")'):
        assert local not in fn, local


def test_a_missing_parquet_no_longer_retires_anything(tmp_path: Path) -> None:
    """The exact shape of the 2026-09-20/21 cut: a symbol in the registry, tradeable, whose bar
    file the retirer could not see at that instant."""
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps({
        "n": 1, "survivors": {"external.EURCHF.discovered.p=abc": {"sym": "EURCHF"}}}), "utf-8")
    n, names = ruc.retire(path, META, "2026-09-24T00:00:00+00:00", _judge)
    assert (n, names) == (0, [])
    assert json.loads(path.read_text("utf-8"))["survivors"]


def test_explicit_venue_refusal_still_retires(tmp_path: Path) -> None:
    """The correction is not a licence to keep everything: a symbol the broker will not open a
    new position in can never be cashed, and that IS venue evidence."""
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps({
        "n": 1, "survivors": {"external.AFG.discovered.p=abc": {"sym": "AFG"}}}), "utf-8")
    n, names = ruc.retire(path, META, "2026-09-24T00:00:00+00:00", _judge)
    assert n == 1 and names == ["external.AFG.discovered.p=abc"]
    doc = json.loads(path.read_text("utf-8"))
    assert doc["survivors"] == {}
    row = doc["retired_certificates"]["external.AFG.discovered.p=abc"]
    assert "disallows new trades" in row["retired_reason"]
    assert row["retired_at"] == "2026-09-24T00:00:00+00:00"


def test_an_unreachable_predicate_retires_nothing(tmp_path: Path) -> None:
    """UNMEASURED is never a revocation (L1.28a). Falling back to a local copy is exactly how
    this file came to hold a rule the sealed writer had already retracted."""
    path = tmp_path / "UNIVERSAL_SURVIVORS.json"
    path.write_text(json.dumps({
        "n": 1, "survivors": {"external.AFG.discovered.p=abc": {"sym": "AFG"}}}), "utf-8")
    assert ruc.retire(path, META, "2026-09-24T00:00:00+00:00", None) == (0, [])
    assert ruc._reason("AFG", META, None) == ""
    # ... and a judge that raises is UNMEASURED too, never a guess
    def _boom(sym: str, meta: dict) -> str | None:
        raise RuntimeError("no registry")
    assert ruc._reason("AFG", META, _boom) == ""


def test_main_refuses_the_whole_pass_when_the_judge_cannot_be_imported() -> None:
    blk = CODE[CODE.index("def main("):]
    assert "judge = _venue_judge()" in blk
    assert "if judge is None:" in blk
    assert "UNMEASURED is not a revocation" in blk
    assert blk.index("if judge is None:") < blk.index("for path in (AUTHORITY, CANON)")


def test_a_row_with_no_symbol_is_still_refused() -> None:
    assert ruc._reason("", META, _judge) == "certificate carries no symbol"
