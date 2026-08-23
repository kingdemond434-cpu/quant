"""THE BRAIN HUNTER -- a dedicated organ, because this ground has cost the desk twice in two days.

2026-08-06: `combination_engine` combined RAW features and had no unary transforms at all -- the
entire transform axis missing. 2026-08-07: one forwarded screenshot named group_rank, group_zscore,
ts_backfill and trade_when, none of which existed, and the group operators mattered most because
the desk's rank/zscore are universe-wide -- so 179,712 cross-sectional cells in the declared sweep
asked "extreme against ALL coins?" and not one asked "against its PEERS?".

A generic miner that touches this corpus occasionally keeps producing findings of that size, one
screenshot at a time. These tests fence the things a dedicated organ must not drift on: the
recursive expansion (or it stays trapped inside what the platform labels an alpha), the crypto
translation (or it returns equity factors that cannot be traded), the bar refusal, and the
legitimacy boundary.
"""

from __future__ import annotations

from pathlib import Path

PROMPT = Path("ops/brain_hunter_prompt.txt")
RUNNER = Path("ops/run_brain_hunter.sh")
ROTATION = Path("ops/run_frontier_rotation.sh")


def _prompt() -> str:
    """Prompt text with WHITESPACE NORMALISED, so assertions are about content rather than about
    where a line happened to wrap. Matching raw text made three of these tests fail on phrases the
    prompt genuinely contained -- a fence that fails on formatting trains people to weaken it."""
    return " ".join(PROMPT.read_text("utf-8", errors="ignore").split())


def test_THE_ORGAN_EXISTS_AND_IS_WIRED_INTO_THE_DAILY_ROTATION() -> None:
    """An organ nobody schedules is a document. The desk has already found that shape three times
    -- a generator with no executor, a ladder with no consumer, a fence looking for the wrong
    string -- so the wiring is checked, not assumed."""
    assert PROMPT.exists() and RUNNER.exists()
    rot = ROTATION.read_text("utf-8")
    assert "run_brain_hunter.sh" in rot, "the hunter exists but nothing runs it daily"
    assert "brain_hunter_${TODAY}" in rot, "the hunter has no resume check and will re-dig"


def test_THE_RUNNER_FOLLOWS_THE_RESUMABLE_PATTERN_THE_OTHER_MINERS_USE() -> None:
    """A dig that dies mid-run must cost a log, not a day. The rotation skips only on a REAL log
    (>1500b), so a stub does not count as a completed dig."""
    rot = ROTATION.read_text("utf-8")
    assert "-size +1500c" in rot
    src = RUNNER.read_text("utf-8")
    assert "brain_auth_check" in src and "dig_dry_run" in src
    # THE ROUTING IS INHERITED, AND ASSERTING THE LITERAL DEMANDED THE OPPOSITE. This required
    # `_BRAIN_MODEL_CHAIN` to appear in the runner -- which is precisely the pin the single-source
    # fence exists to prevent. This organ carried a literal copy from 2026-08-11 (d48c6408) until
    # it was removed a day later, and with it the hunter would keep running yesterday's models the
    # first time run_model_upgrade.py adopts a newer flagship, silently. So the assertion is that
    # the chain ARRIVES from the one place that generates it, not that it is restated here.
    assert "source ops/brain_env.sh" in src, (
        "the hunter does not inherit the dual-pool routing from brain_env.sh")
    assert "_BRAIN_MODEL_CHAIN=" not in src, (
        "the hunter re-declares the model chain -- a local copy goes stale the moment "
        "run_model_upgrade.py adopts a newer flagship, and nothing would report it")


def test_CLAUDE_AUTH_FAILURE_FAILS_OVER_TO_THE_SAME_CODEX_MINER() -> None:
    src = RUNNER.read_text("utf-8")
    assert 'CONTROLLER="codex"' in src
    assert "Codex fallback" in src
    assert "--ask-for-approval never" in src
    assert "--sandbox danger-full-access" in src
    assert "dig_prompt ops/brain_hunter_prompt.txt" in src
    assert "all controller auth unavailable" in src


def test_IT_HUNTS_RECURSIVELY_RATHER_THAN_SEARCHING_ONE_LABEL() -> None:
    """Searching the platform's own label traps the organ inside what the platform CALLS an alpha.
    The alternative-implementation node is usually the highest-yield one: someone who reimplemented
    an operator set had to understand it, and their README says what the official docs assume."""
    src = _prompt()
    for node in ("AUTHOR", "CITED papers", "ALTERNATIVE", "MECHANISMS"):
        assert node in src, f"the expansion chain is missing the {node} node"
    assert "do NOT search only for" in src


def test_PUBLIC_COMPETITIONS_ARE_MINED_AS_MT5_ORE_NOT_EVIDENCE() -> None:
    src = _prompt()
    for source in ("MQL5", "Myfxbook", "Darwinex/DarwinIA", "broker contests"):
        assert source in src
    assert "complete histories and failure cohorts" in src
    assert "selection-biased ore" in src
    assert "Fusion-native point-in-time data" in src


def test_IT_EXTRACTS_MECHANISMS_AND_DEMANDS_AN_MT5_ANALOGUE() -> None:
    """A copied formula is a crowded expression over a universe the desk does not trade. The
    platform is primarily an EQUITIES venue, so a factor rarely transfers while its transformation,
    neutralization idea or methodology often does."""
    src = _prompt()
    assert "EXTRACT MECHANISMS, NOT FORMULAS" in src
    assert "MT5 ANALOGUE" in src and "translate_to_mt5" in src
    assert "CURRENT VENUE OVERRIDE — MT5/FUSION" in src
    assert "PRIMARILY AN EQUITIES VENUE" in src.upper()


def test_AN_OPERATOR_WITH_NO_MT5_ANALOGUE_IS_STILL_LOGGED() -> None:
    """It names data the desk does not have, which is the information-frontier axis. Discarding it
    would silently narrow the search to what the desk can already measure."""
    src = _prompt()
    assert "STILL worth logging" in src
    assert "data_axis_watchlist.md" in src


def test_IT_NAMES_THE_BLOCKING_INPUT_RATHER_THAN_HUNTING_MORE_OPERATORS() -> None:
    """group_rank and group_zscore both REFUSE without a group map, so two of the four operators
    just adopted are inert. A grouping the desk can build is worth more than another operator it
    cannot apply -- and an organ not told that will keep returning operators."""
    src = _prompt()
    assert "NO GROUPING MAP AT ALL" in src
    assert "worth more right now than another operator" in src


def test_THE_SUBMISSION_BAR_IS_REFUSED_HERE_TOO() -> None:
    """The organ closest to the source is the one most likely to import its thresholds. Their
    in-sample bar is rational for an operator that runs its own out-of-sample stage and pays per
    accepted alpha; this desk bears that cost itself."""
    src = _prompt()
    assert "NEVER AS GATES FOR OURS" in src
    assert "L1.6" in src and "5.236" in src
    assert "Do not add one." in src, "the fitness diagnostic could still grow a pass/fail path"


def test_THE_LEGITIMACY_BOUNDARY_IS_EXPLICIT_AND_NAMES_THE_TEMPTATION() -> None:
    """'Every WorldQuant thing' can only mean everything PUBLICLY and LEGALLY accessible. The
    specific temptation on this ground is an account: a credentialed account's contents are not
    public merely because an account exists."""
    src = _prompt()
    assert "PUBLICLY AND LEGALLY ACCESSIBLE" in src
    for forbidden in ("private BRAIN data", "other users' private alphas", "proprietary datasets",
                      "restricted platform internals", "account-gated"):
        assert forbidden in src, f"the boundary does not name {forbidden!r}"
    assert "not public merely because an account exists" in src
    assert "naming what is behind the wall is legitimate; going behind" in src


def test_THE_GROUND_IS_NEVER_MARKED_EXHAUSTED() -> None:
    """Artifacts exhaust; the ground does not, because the platform keeps publishing. An organ
    allowed to close the ground would close it and stop."""
    src = _prompt()
    assert "Never mark this ground EXHAUSTED" in src
    assert "Mark individual ARTIFACTS exhausted" in src


def test_THE_STANDING_MANDATES_CARRY_OVER_TO_THIS_ORGAN() -> None:
    """A new organ that does not inherit provenance, claimed-vs-verified and the tier ladder is a
    hole in every layer built on top of them."""
    src = _prompt()
    for mandate in ("PROCESS MANDATE", "PROVENANCE", "CLAIMED IS NOT VERIFIED",
                    "COST OF REFUTATION", "VIDEO IS FIRST-CLASS"):
        assert mandate in src, f"{mandate} did not carry over to the BRAIN hunter"
    assert "fetch_video_transcript.py" in src


def test_IT_IS_RESEARCH_ONLY_AND_TOUCHES_NO_CODE_OR_MONEY_PATH() -> None:
    src = _prompt()
    assert "RESEARCH ONLY" in src
    assert "NEVER touch scripts/" in src and "risk rails" in src
    assert "No installs, no trades" in src
