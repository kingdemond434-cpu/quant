"""The prop account is sized by the prop venue's rules; the main book keeps its own.

(principal, 2026-09-09: "we tune only our prop firm side for the prop firm n keep 20 percent heat
rule fr the main only". The standing constraint on the main book -- never reduce risk, never
reduce the heat floor -- is unchanged, and the first two tests here are what hold that.)

WHAT WAS WRONG. `mt5desk/account_profile.py` has existed since 2026-08-29 and had ONE consumer:
`scripts/check_promotion_readiness.py`, a report. The money path never read it. So the gateway
sized every account from the same global constants, and connecting a funded E8 account would have
traded someone else's capital on the live 3% envelope -- which that module's own arithmetic calls
catastrophic, not merely large: 2.5% daily x 0.6 utilisation / 5.5 effective bets is 0.27%, a
TWELFTH of the live figure.

THE DIRECTION OF THE DEFAULT IS THE DESIGN. `profile_for` fails closed to the tightest envelope
because it answers "how should an account I am about to FUND be sized". `envelope_for_connected`
answers a different question -- "may I keep sizing the book I am already trading" -- and there
the tightest envelope is not caution, it is an unrequested 12x cut to a running live book. The
same word, "conservative", points opposite ways in the two, and the tests below pin both.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from mt5desk import account_profile as ap        # noqa: E402
from mt5desk import decision_core as core        # noqa: E402

LIVE_ACC = {"login": 520144, "server": "FusionMarkets-Live", "kind": "LIVE"}
PROP_ACC = {"login": 900001, "server": "E8-Server-01", "kind": "LIVE"}


def _declare(root: Path, accounts: dict[str, str]) -> None:
    p = root / Path(*ap.DECLARATIONS_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"accounts": accounts}, indent=1), "utf-8")


def _book(n: int, q: float) -> list[dict]:
    return [{"name": f"s{i}", "q": q} for i in range(n)]


# --------------------------------------------------------- THE MAIN BOOK IS NOT TOUCHED
def test_a_box_with_no_declarations_gets_no_bar_at_all(tmp_path: Path) -> None:
    """The state of the live box today. No file, no bar, nothing changes -- and this is the
    assertion that would fail first if someone made the resolver fail closed like `profile_for`.
    """
    cap, why = ap.venue_heat_cap(LIVE_ACC, tmp_path)
    assert cap is None
    assert "unchanged from the desk's own" in why


def test_the_live_account_has_no_bar_even_once_it_is_declared(tmp_path: Path) -> None:
    """Belt and braces, and they are independent: the bar is absent because `fusion-live` has no
    daily loss limit, not merely because nobody wrote the file down. Declaring the live account
    must not become a way to shrink it."""
    _declare(tmp_path, {"520144@FusionMarkets-Live": "fusion-live"})
    cap, why = ap.venue_heat_cap(LIVE_ACC, tmp_path)
    assert cap is None
    assert "imposes no daily loss limit" in why


def test_the_heat_cap_admits_the_identical_book_with_and_without_the_new_argument() -> None:
    """THE REGRESSION THAT MATTERS TO THE PRINCIPAL'S STANDING CONSTRAINT. A 20% book must be
    admitted exactly as it was before this parameter existed."""
    book = _book(4, 0.05)
    was, note_a = core.cap_by_heat(book, 10_000.0, per_sleeve_q=0.05,
                                   allocation=(0.20, "measured"))
    now, note_b = core.cap_by_heat(book, 10_000.0, per_sleeve_q=0.05,
                                   allocation=(0.20, "measured"), venue_cap=(None, "no venue"))
    assert [s["name"] for s in was] == [s["name"] for s in now] == ["s0", "s1", "s2", "s3"]
    assert note_a is None and note_b is None


# ------------------------------------------------------------ THE PROP BOOK IS BOUND
def test_a_declared_prop_account_is_capped_by_its_daily_loss_rule(tmp_path: Path) -> None:
    _declare(tmp_path, {"900001@E8-Server-01": "e8-pro-v2"})
    cap, why = ap.venue_heat_cap(PROP_ACC, tmp_path)
    assert cap == pytest.approx(0.025 * ap.LIMIT_UTILISATION)      # 1.5%
    assert "e8-pro-v2" in why and "concurrent risk" in why


def test_the_venue_bar_actually_trims_a_book_the_growth_budget_would_have_admitted() -> None:
    """The wiring, not the arithmetic: a 20% budget and a 1.5% venue bar must yield the 1.5%
    book. A cap that read the profile and admitted twenty percent anyway is the defect."""
    book = _book(4, 0.05)
    admitted, note = core.cap_by_heat(book, 10_000.0, per_sleeve_q=0.05,
                                      allocation=(0.20, "measured"),
                                      venue_cap=(0.015, "e8-pro-v2 daily bar"))
    assert len(admitted) == 0, "a 5% leg does not fit inside a 1.5% venue bar"
    assert note and "VENUE bar 1.50%" in note, (
        "the note blames the growth budget for a trim the VENUE caused; the operator's next move "
        "differs completely between those two and the note is where they find out which it was")
    smaller, note2 = core.cap_by_heat(_book(4, 0.004), 10_000.0, per_sleeve_q=0.004,
                                      allocation=(0.20, "measured"),
                                      venue_cap=(0.015, "e8-pro-v2 daily bar"))
    assert len(smaller) == 3 and note2 and "VENUE bar" in note2


def test_a_venue_bar_above_the_budget_never_raises_the_book() -> None:
    """It is a bar, not a budget. A generous venue cannot lift heat past what the desk solved."""
    book = _book(10, 0.05)
    admitted, _ = core.cap_by_heat(book, 10_000.0, per_sleeve_q=0.05,
                                   allocation=(0.10, "measured"),
                                   venue_cap=(0.90, "a venue with almost no rules"))
    assert sum(s["q"] for s in admitted) <= 0.12 + 1e-9, (
        "the venue cap was used as a budget; it may only ever narrow")


# ------------------------------------------------------- undeclared accounts fail closed
def test_an_account_missing_from_an_existing_declaration_gets_the_tightest_envelope(
        tmp_path: Path) -> None:
    """Once the box has been told it runs more than one account, an account nobody named is an
    account nobody vouched for -- and the funding asymmetry applies again in full."""
    _declare(tmp_path, {"520144@FusionMarkets-Live": "fusion-live"})
    cap, why = ap.venue_heat_cap(PROP_ACC, tmp_path)
    assert cap == pytest.approx(0.015)
    assert "is not declared" in why and "declared in" in why, (
        "the reason must distinguish an account absent from a file that read fine from one "
        "absent because the file did not read at all -- see the torn-write test below")


def test_a_declarations_file_that_cannot_be_read_fails_closed_rather_than_open(
        tmp_path: Path) -> None:
    """A TORN WRITE MUST NOT HAND A PROP ACCOUNT THE LIVE ENVELOPE. `read_declarations` returns
    an empty mapping rather than None here precisely so this case cannot collapse into "no
    declarations exist"."""
    p = tmp_path / Path(*ap.DECLARATIONS_REL.split("/"))
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text('{"accounts": {"900001@E8-Ser', "utf-8")
    cap, why = ap.venue_heat_cap(PROP_ACC, tmp_path)
    assert cap == pytest.approx(0.015), "an unreadable declaration file read as no declarations"
    assert "unreadable" in why


def test_an_unidentified_account_fails_closed_only_when_declarations_exist(
        tmp_path: Path) -> None:
    """An unreachable terminal is an UNKNOWN account, not an absent one. With declarations it is
    undeclared and bound; without them there is nothing to bind and nothing to change."""
    assert ap.venue_heat_cap(None, tmp_path)[0] is None
    _declare(tmp_path, {"520144@FusionMarkets-Live": "fusion-live"})
    cap, why = ap.venue_heat_cap(None, tmp_path)
    assert cap == pytest.approx(0.015) and "did not name the connected account" in why


def test_a_declared_profile_name_that_does_not_exist_fails_closed(tmp_path: Path) -> None:
    _declare(tmp_path, {"900001@E8-Server-01": "e8-platinum-deluxe"})
    cap, why = ap.venue_heat_cap(PROP_ACC, tmp_path)
    assert cap == pytest.approx(0.015)
    assert "not a known profile" in why


def test_the_key_needs_both_login_and_server() -> None:
    """`provenance.same_account`'s reason, restated where the key is built: a broker reusing
    logins across servers would collide, and one broker's demo and live sides differ by exactly
    this pair."""
    assert ap.account_key({"login": 1, "server": "S"}) == "1@S"
    assert ap.account_key({"login": 1, "server": None}) is None
    assert ap.account_key({"login": None, "server": "S"}) is None
    assert ap.account_key(None) is None


# ------------------------------------------------------------------- and it must be wired
def test_the_gateway_asks_for_the_venue_bar_when_it_caps() -> None:
    """The whole defect was a correct module nobody called. Source-pinned because gateway.py
    imports MetaTrader5 and cannot be imported here."""
    src = (BASE / "mt5desk" / "gateway.py").read_text("utf-8")
    assert "venue_cap=venue_heat_cap()" in src, (
        "the gateway caps heat without consulting the connected account's venue")
    assert "_acct.venue_heat_cap(acc, BASE.parent.parent)" in src
