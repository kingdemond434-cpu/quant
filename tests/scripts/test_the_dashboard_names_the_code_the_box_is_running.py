"""A DASHBOARD THAT CANNOT NAME ITS OWN COMMIT CANNOT SAY WHETHER A FIX IS LIVE.

MEASURED 2026-09-09. The box had failed to adopt for a day -- ten paths out of 15,146 carried an
ACL its account could not write, `Adopt-Release` reported them, and `Adopt-And-Seal` correctly
refused to seal a tree that only half-matches the branch. Every tile on dash.quanttt.xyz went on
rendering: account fresh to the second, research counts moving, the stall watchdog reporting.
`generated_at` was five minutes old and every number in the file was true. And the one question
being asked of it -- "is the new code live?" -- had no field to answer from, because
`build_zentech_state` published no commit, no seal and no verdict.

So a box running yesterday's money path and a box running today's are PIXEL-IDENTICAL here, which
is the same defect class as `test_dashboard_says_when_the_box_went_silent` (ten-day-old numbers in
the present tense) and, before that, as a partition that cannot fail.

WHAT MAKES IT CHEAP: nothing needed computing. `release_identity.verdict()` -- the gateway's own
refuse-or-allow decision, taken every pass -- already writes `desks/mt5/data/release_identity.json`
next to the state the dashboard was already reading. Only the last two feet were missing.

THE ASSERTIONS THAT MATTER are the two that would be false for a page that merely looks informed:
an ABSENT verdict must read UNMEASURED and refuse (a dashboard that says OK because it found no
file is the failure it exists to expose), and the block must arrive through the REAL `build()`,
because a correct helper nobody calls is indistinguishable from no helper -- which is exactly how
the ten-day outage survived.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent

RUNNING = "85aa73f4a9a20e9c32c1b50e81e1c7f8d13396a6"
SEALED = "b3ccb14baff6a89bb45e04ea808fa903ca4ebf5c"


def _load():
    spec = importlib.util.spec_from_file_location(
        "_bzs_release", _ROOT / "scripts" / "build_zentech_state.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bzs():
    return _load()


def _tree(bzs, tmp_path, monkeypatch, verdict: dict | None):
    """A desk tree carrying `verdict` as the gateway's last release decision, or none at all."""
    desk = tmp_path / "desks" / "mt5"
    (desk / "data").mkdir(parents=True)
    (desk / "reports" / "shadow").mkdir(parents=True)
    if verdict is not None:
        (desk / "data" / "release_identity.json").write_text(json.dumps(verdict), "utf-8")
    monkeypatch.setattr(bzs, "ROOT", tmp_path)
    monkeypatch.setattr(bzs, "DESK", desk)
    return desk


def _verdict(**over) -> dict:
    base = {"ok": False, "verdict": "REFUSED", "allows_new_risk": False,
            "running_sha": RUNNING, "release_sha": SEALED,
            "reason": f"running {RUNNING[:12]} carries 272 path(s) the sealed release "
                      f"{SEALED[:12]} never named",
            "age_h": 37.5, "stale": False, "measured": True,
            "at": "2026-09-09T15:39:06+00:00"}
    base.update(over)
    return base


# ---------------------------------------------------------------- the two shas, and the gap
def test_the_block_names_the_running_commit_and_the_sealed_one(bzs, tmp_path, monkeypatch):
    """Both, never one. `running` alone cannot show a failed seal; `sealed` alone cannot show a
    failed adopt -- and those are the two ways the box goes quietly stale."""
    _tree(bzs, tmp_path, monkeypatch, _verdict())
    got = bzs._release_block()
    assert got["running_sha"] == RUNNING[:12]
    assert got["sealed_sha"] == SEALED[:12]
    assert got["adopted"] is False
    assert got["verdict"] == "REFUSED"
    assert got["allows_new_risk"] is False


def test_a_sealed_tree_reads_adopted_and_may_take_new_risk(bzs, tmp_path, monkeypatch):
    _tree(bzs, tmp_path, monkeypatch,
          _verdict(ok=True, verdict="OK", allows_new_risk=True, release_sha=RUNNING,
                   reason="running matches the sealed release"))
    got = bzs._release_block()
    assert got["adopted"] is True
    assert got["allows_new_risk"] is True
    assert got["running_sha"] == got["sealed_sha"] == RUNNING[:12]


def test_the_permission_to_trade_is_republished_and_never_re_derived(bzs, tmp_path, monkeypatch):
    """THE FIELD THE PAGE AND THE MONEY PATH MUST NOT DISAGREE ON.

    `allows_new_risk` is the gateway's own answer. If the dashboard recomputed it from the shas
    it would drift the day the rule gains a term -- staleness already binds it, and does not
    appear in a sha comparison at all. So a verdict whose shas MATCH but which still refuses must
    still be published as refusing.
    """
    _tree(bzs, tmp_path, monkeypatch,
          _verdict(ok=True, verdict="OK", allows_new_risk=False, release_sha=RUNNING,
                   stale=True, reason="verdict is 40h old and staleness refuses"))
    got = bzs._release_block()
    assert got["adopted"] is True, "the shas match"
    assert got["allows_new_risk"] is False, (
        "the dashboard re-derived the trading permission from the shas instead of reading the "
        "gateway's answer; they are now free to disagree")
    assert got["stale"] is True


# ------------------------------------------------------- absent evidence is not good evidence
def test_no_verdict_on_disk_reads_unmeasured_and_refuses(bzs, tmp_path, monkeypatch):
    """The failure this block exists to expose must not be able to render as health."""
    _tree(bzs, tmp_path, monkeypatch, None)
    got = bzs._release_block()
    assert got["verdict"] == "UNMEASURED"
    assert got["allows_new_risk"] is False
    assert "unknown" in got["why"], (
        "the payload states a status but not its consequence -- a reader who does not already "
        "know what UNMEASURED means cannot act on it")


def test_an_unreadable_verdict_is_unmeasured_rather_than_an_exception(bzs, tmp_path, monkeypatch):
    desk = _tree(bzs, tmp_path, monkeypatch, None)
    (desk / "data" / "release_identity.json").write_text("{ truncated", "utf-8")
    assert bzs._release_block()["verdict"] == "UNMEASURED"


def test_a_long_refusal_reason_is_trimmed_but_still_says_what_refused(bzs, tmp_path, monkeypatch):
    """The real reason lists every drifted path and ran past 600 characters on the box. The
    dashboard needs the sentence; the inventory belongs in the log."""
    long = "money path drifted on disk: " + ", ".join(f"desks/mt5/mt5desk/f{i}.py"
                                                      for i in range(200))
    _tree(bzs, tmp_path, monkeypatch, _verdict(reason=long))
    why = bzs._release_block()["why"]
    assert len(why) <= bzs.RELEASE_REASON_CHARS + 8
    assert why.startswith("money path drifted on disk:")
    assert why.endswith("[...]"), "a trimmed reason must show that it was trimmed"


# ------------------------------------------------------------- and it must reach the payload
def test_the_release_block_reaches_the_published_payload(bzs, tmp_path, monkeypatch):
    """THE HALF THAT WAS ACTUALLY BROKEN, in both outages: the verdict existed and nothing
    carried it. So this drives the real builder, not the helper."""
    _tree(bzs, tmp_path, monkeypatch, _verdict())
    monkeypatch.setattr(bzs, "_mt5_snapshot", lambda: {})
    rel = bzs.build()["release"]
    assert rel["running_sha"] == RUNNING[:12]
    assert rel["adopted"] is False
    assert rel["allows_new_risk"] is False
