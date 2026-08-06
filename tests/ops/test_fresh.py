"""CONSUMPTION-TIME FRESHNESS (L1.44) -- 95 statements, and 32 files reference it untested.

THE CLASS THIS CLOSES. Five producer-side max-age registries exist (max_audit, check_ratchets,
check_miner_runway, check_exploration, data_health), all hand-enumerated, all answering "did the
producer run?" -- and NONE knowing who READS what. So a dead producer surfaces as one idleness line
among 25 while its frozen artifact keeps steering live decisions as if current. The desk's record
holds five hand-found instances: a max_push queue consumed 2h stale by every brain slot, an idle
Holm slot fed by a stale snapshot, panel_verdicts 189h old pinning a payload at its floor, an ADL
force-order window firing after its condition passed, and the 13,155/4,500 equity split.

SEVERITY IS SET BY THE CONSUMER, which is why producer-side registries could never see it.

The three design rules each close a way this class hid, and each is one line from inverting:

  CONTENT `generated` OUTRANKS MTIME. The 10-minute auto-deploy rewrites files, so mtime lies
  FRESH after a deploy -- the DANGEROUS direction. All five existing registries are mtime-based and
  share that hole. Asserted directly: an old stamp in a just-written file must read STALE.

  kind='state' MEANS GUARDIAN-LIVENESS, NEVER OWN-AGE. A valid-until-changed file is legitimately
  old; its read is fresh iff the named GUARDIAN organ is alive. Without this the fence cries wolf
  on healthy state, and a gate that cries wolf gets switched off (L1.43).

  THE CALLER NAMES ITS DEGRADE DIRECTION. 'fallback' returns the data with fresh=False so the read
  site decides -- a stale denylist still DENIES, a stale cost may only TIGHTEN. 'strict' raises,
  for reads where acting on frozen input is worse than not acting.

And the fourth property, which is about this module's own bug of its own class: the root is CWD,
never a guessed install path. Guessing made read_fresh the only reader in its process consuming a
DIFFERENT install's artifacts -- two roots in one process, which is the two-sources-of-truth class
the module exists to close.
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from libs.ops import fresh as F


def _write(root: Path, rel: str, *, generated: datetime | None = None,
           mtime_age_h: float | None = None, payload: dict | None = None) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    doc = dict(payload or {"value": 1})
    if generated is not None:
        doc["generated"] = generated.isoformat()
    p.write_text(json.dumps(doc), "utf-8")
    if mtime_age_h is not None:
        t = time.time() - mtime_age_h * 3600.0
        os.utime(p, (t, t))
    return p


# ============================================================ generated outranks mtime

def test_a_JUST_WRITTEN_file_with_an_OLD_STAMP_reads_STALE(tmp_path: Path) -> None:
    """THE DANGEROUS DIRECTION, and the hole all five producer-side registries share. The
    10-minute auto-deploy and the puller's revert path rewrite files, so mtime lies FRESH after a
    deploy -- a frozen artifact would pass an mtime check on the day it stopped being produced."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC) - timedelta(hours=100))
    fr = F.read_fresh("data/cost.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.source == "generated"
    assert fr.fresh is False and fr.age_h is not None and fr.age_h > 99
    assert "STALE" in fr.why


def test_a_fresh_stamp_reads_FRESH_and_says_which_clock_it_used(tmp_path: Path) -> None:
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC) - timedelta(hours=1))
    fr = F.read_fresh("data/cost.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.fresh is True and fr.source == "generated"
    assert "via generated" in fr.why


def test_MTIME_is_the_FALLBACK_when_no_stamp_exists(tmp_path: Path) -> None:
    """Not a preference -- a fallback. An artifact with no stamp is still measurable, and refusing
    to measure it would make every legacy producer permanently unreadable."""
    _write(tmp_path, "data/legacy.json", mtime_age_h=2.0)
    fr = F.read_fresh("data/legacy.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.source == "mtime" and fr.fresh is True
    assert fr.age_h == pytest.approx(2.0, abs=0.05)


def test_a_MALFORMED_stamp_falls_back_to_mtime_and_never_hides_the_artifact(
        tmp_path: Path) -> None:
    """Dropping the read entirely because a stamp was unparseable would make one bad field look
    exactly like a missing file, and the consumer would degrade for the wrong reason."""
    p = tmp_path / "data/bad_stamp.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"generated": "not-a-date", "value": 1}), "utf-8")
    fr = F.read_fresh("data/bad_stamp.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.source == "mtime" and fr.data == {"generated": "not-a-date", "value": 1}


def test_a_NAIVE_generated_stamp_is_read_as_UTC(tmp_path: Path) -> None:
    """A naive stamp interpreted in local time is the KST/UTC class of bug, and here it would make
    an artifact read hours fresher or staler than it is depending on the box's zone."""
    p = tmp_path / "data/naive.json"
    p.parent.mkdir(parents=True)
    stamp = (datetime.now(tz=UTC) - timedelta(hours=2)).replace(tzinfo=None).isoformat()
    p.write_text(json.dumps({"generated": stamp}), "utf-8")
    fr = F.read_fresh("data/naive.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.age_h == pytest.approx(2.0, abs=0.1)


def test_a_FUTURE_stamp_is_clamped_to_zero_rather_than_going_negative(tmp_path: Path) -> None:
    """Clock skew on a fresh box. A negative age passes any `<= max_age` check, so clamping at
    zero is the same answer -- but it keeps the reported number honest."""
    _write(tmp_path, "data/future.json", generated=datetime.now(tz=UTC) + timedelta(hours=5))
    fr = F.read_fresh("data/future.json", max_age_h=1.0, caller="t", root=tmp_path)
    assert fr.age_h == 0.0 and fr.fresh is True


# ============================================================ missing and unreadable

def test_a_MISSING_file_has_NO_MEASURABLE_AGE_and_is_not_fresh(tmp_path: Path) -> None:
    """`age_h=None` is distinct from a large age: one says the artifact is absent, the other says
    it is old. A consumer choosing a fallback wants to know which."""
    fr = F.read_fresh("data/absent.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.source == "missing" and fr.age_h is None and fr.fresh is False
    assert fr.data is None and "no age measurable" in fr.why


def test_an_UNPARSEABLE_file_is_distinguished_from_a_missing_one(tmp_path: Path) -> None:
    """A truncated write and an absent producer are different failures with different fixes."""
    p = tmp_path / "data/torn.json"
    p.parent.mkdir(parents=True)
    p.write_text("{not json", "utf-8")
    fr = F.read_fresh("data/torn.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.source == "unreadable" and fr.data is None and fr.fresh is False


def test_a_non_dict_payload_is_still_returned_and_aged_by_mtime(tmp_path: Path) -> None:
    """A JSON list is a legitimate artifact. Refusing it would make the helper unusable for every
    producer that writes an array."""
    p = tmp_path / "data/list.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps([1, 2, 3]), "utf-8")
    fr = F.read_fresh("data/list.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.data == [1, 2, 3] and fr.source == "mtime" and fr.fresh is True


# ============================================================ guardian-backed state

def test_STATE_is_judged_by_its_GUARDIAN_not_by_its_own_age(tmp_path: Path) -> None:
    """A valid-until-changed file is LEGITIMATELY old. Judging it on its own age is how a fence
    cries wolf on healthy state -- and a gate that cries wolf gets switched off (L1.43)."""
    _write(tmp_path, "data/stage_state.json", mtime_age_h=1_000.0)      # ancient, and fine
    _write(tmp_path, "data/live_guard.json", generated=datetime.now(tz=UTC))
    fr = F.read_fresh("data/stage_state.json", max_age_h=2.0, caller="t", kind="state",
                      guardian="data/live_guard.json", root=tmp_path)
    assert fr.fresh is True
    assert fr.source.startswith("guardian:")
    assert fr.data is not None, "the STATE's own contents are still returned"


def test_a_DEAD_GUARDIAN_makes_even_a_new_state_file_stale(tmp_path: Path) -> None:
    """The other half. A state file rewritten a second ago means nothing if the organ that keeps
    it true stopped running a week ago."""
    _write(tmp_path, "data/stage_state.json", generated=datetime.now(tz=UTC))
    _write(tmp_path, "data/live_guard.json", generated=datetime.now(tz=UTC) - timedelta(hours=50))
    fr = F.read_fresh("data/stage_state.json", max_age_h=2.0, caller="t", kind="state",
                      guardian="data/live_guard.json", root=tmp_path)
    assert fr.fresh is False and "STALE" in fr.why


def test_state_with_an_UNREADABLE_OWN_FILE_is_not_fresh_however_alive_the_guardian(
        tmp_path: Path) -> None:
    """A live guardian over an unparseable state file is not a usable read -- the consumer would
    get `data=None` and a fresh=True telling it to act on it."""
    p = tmp_path / "data/stage_state.json"
    p.parent.mkdir(parents=True)
    p.write_text("{torn", "utf-8")
    _write(tmp_path, "data/live_guard.json", generated=datetime.now(tz=UTC))
    fr = F.read_fresh("data/stage_state.json", max_age_h=2.0, caller="t", kind="state",
                      guardian="data/live_guard.json", root=tmp_path)
    assert fr.fresh is False and fr.data is None


def test_kind_state_WITHOUT_a_guardian_RAISES_at_the_call_site(tmp_path: Path) -> None:
    """Loudly, and at the read site rather than silently defaulting to own-age. A state read with
    no guardian has no definition of freshness at all, and picking one for the caller would be
    inventing the contract this module exists to make explicit."""
    _write(tmp_path, "data/stage_state.json")
    with pytest.raises(ValueError, match="requires guardian"):
        F.read_fresh("data/stage_state.json", max_age_h=2.0, caller="t", kind="state",
                     root=tmp_path)


def test_a_MISSING_guardian_is_stale_not_an_error(tmp_path: Path) -> None:
    """A guardian that has never run is exactly as untrustworthy as one that stopped."""
    _write(tmp_path, "data/stage_state.json")
    fr = F.read_fresh("data/stage_state.json", max_age_h=2.0, caller="t", kind="state",
                      guardian="data/never_ran.json", root=tmp_path)
    assert fr.fresh is False and fr.age_h is None


# ============================================================ the degrade direction

def test_FALLBACK_returns_the_data_so_the_READ_SITE_decides(tmp_path: Path) -> None:
    """A stale denylist still DENIES; a stale cost estimate may only TIGHTEN a gate. Only the read
    site knows which, so the helper hands back the data and the verdict separately."""
    _write(tmp_path, "data/denylist.json", generated=datetime.now(tz=UTC) - timedelta(hours=100),
           payload={"symbols": ["DOGEUSDT"]})
    fr = F.read_fresh("data/denylist.json", max_age_h=1.0, caller="t", root=tmp_path)
    assert fr.fresh is False
    assert fr.data["symbols"] == ["DOGEUSDT"], "the caller can still deny on a stale denylist"


def test_STRICT_RAISES_because_acting_on_frozen_input_is_worse_than_not_acting(
        tmp_path: Path) -> None:
    """The executor-grade direction, mirroring lawful.guard(strict=True)."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC) - timedelta(hours=100))
    with pytest.raises(F.StaleRead, match=r"L1\.44 strict"):
        F.read_fresh("data/cost.json", max_age_h=1.0, caller="executor._rt_bps",
                     mode="strict", root=tmp_path)


def test_the_strict_error_NAMES_the_caller_and_the_artifact(tmp_path: Path) -> None:
    """A raised StaleRead with no caller is one nobody can route. The read site is the whole point
    of consumption-time freshness."""
    with pytest.raises(F.StaleRead) as ei:
        F.read_fresh("data/absent.json", max_age_h=1.0, caller="executor._rt_bps",
                     mode="strict", root=tmp_path)
    assert "executor._rt_bps" in str(ei.value) and "absent.json" in str(ei.value)


def test_strict_does_NOT_raise_on_a_fresh_read(tmp_path: Path) -> None:
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    assert F.read_fresh("data/cost.json", max_age_h=1.0, caller="t", mode="strict",
                        root=tmp_path).fresh is True


# ============================================================ the self-building registry

def test_THE_REGISTRY_BUILDS_ITSELF_FROM_ACTUAL_READS(tmp_path: Path) -> None:
    """No sixth hand list to rot. The registry is simultaneously the producer->consumer edge list
    that L1.28c's event-driven end state requires -- which a hand-kept list could never be, because
    it records what the code CLAIMS rather than what it DOES."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    F.read_fresh("data/cost.json", max_age_h=48.0, caller="executor._rt_bps", root=tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()]
    contract = next(r for r in rows if r["event"] == "contract")
    assert contract["caller"] == "executor._rt_bps"
    assert contract["path"] == "data/cost.json"
    assert contract["max_age_h"] == 48.0 and contract["kind"] == "measurement"


def test_the_contract_is_TTL_THROTTLED_so_a_hot_loop_cannot_flood_the_registry(
        tmp_path: Path) -> None:
    """A read on every executor tick would write millions of identical lines and fill the disk --
    and a full disk takes the desk down, which is a worse outcome than the staleness being tracked.
    """
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    for _ in range(25):
        F.read_fresh("data/cost.json", max_age_h=48.0, caller="hot.loop", root=tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()]
    assert len([r for r in rows if r["caller"] == "hot.loop"]) == 1


def test_DIFFERENT_callers_of_the_same_path_are_recorded_separately(tmp_path: Path) -> None:
    """Severity is set by the CONSUMER. One line per artifact would collapse a 2h-tolerant reader
    and a 200h-tolerant one into a single contract, losing the number that matters."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    F.read_fresh("data/cost.json", max_age_h=2.0, caller="executor", root=tmp_path)
    F.read_fresh("data/cost.json", max_age_h=200.0, caller="dashboard", root=tmp_path)
    rows = [json.loads(x) for x in
            (tmp_path / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()]
    by_caller = {r["caller"]: r["max_age_h"] for r in rows if r["event"] == "contract"}
    assert by_caller == {"executor": 2.0, "dashboard": 200.0}


def test_a_STALE_READ_is_recorded_as_its_own_event(tmp_path: Path) -> None:
    """The contract says who consumes what; the stale event says when it was consumed frozen. Only
    the second answers 'was a decision actually made on dead input'."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC) - timedelta(hours=100))
    F.read_fresh("data/cost.json", max_age_h=1.0, caller="executor", root=tmp_path)
    events = {json.loads(x)["event"] for x in
              (tmp_path / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()}
    assert events == {"contract", "stale_read"}


def test_an_UNREADABLE_read_is_a_DIFFERENT_event_from_a_stale_one(tmp_path: Path) -> None:
    F.read_fresh("data/absent.json", max_age_h=1.0, caller="executor", root=tmp_path)
    events = {json.loads(x)["event"] for x in
              (tmp_path / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()}
    assert "unreadable_read" in events and "stale_read" not in events


def test_recording_is_BEST_EFFORT_and_never_breaks_the_read(tmp_path: Path,
                                                            monkeypatch) -> None:
    """Failure to journal must never break the decision path. The fence reports a silent registry
    separately -- a helper that raised while writing its own telemetry would take down every
    consumer it was meant to protect."""
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))

    def boom(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(Path, "mkdir", boom)
    fr = F.read_fresh("data/cost.json", max_age_h=48.0, caller="t", root=tmp_path)
    assert fr.fresh is True and fr.data is not None


# ============================================================ the root, and this module's own bug

def test_the_root_is_CWD_and_never_a_GUESSED_install_path(tmp_path: Path, monkeypatch) -> None:
    """A BUG OF THIS MODULE'S OWN CLASS. The first version guessed an install path, which made
    read_fresh the only reader in its process consuming a DIFFERENT install's artifacts -- a
    checkout under /home/user marking against the live box's /home/quant/quant-platform/data. Two
    roots inside one process is precisely the two-sources-of-truth class this module closes."""
    monkeypatch.delenv("QUANT_FRESH_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    assert F._root() == Path.cwd()
    _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    assert F.read_fresh("data/cost.json", max_age_h=48.0, caller="t").fresh is True


def test_QUANT_FRESH_ROOT_pins_a_root_without_moving_cwd(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QUANT_FRESH_ROOT", str(tmp_path))
    assert F._root() == tmp_path


def test_an_ABSOLUTE_path_is_read_as_given(tmp_path: Path) -> None:
    p = _write(tmp_path, "data/cost.json", generated=datetime.now(tz=UTC))
    assert F.read_fresh(p, max_age_h=48.0, caller="t", root=tmp_path).fresh is True


def test_a_path_OUTSIDE_the_root_is_recorded_by_its_absolute_name(tmp_path: Path) -> None:
    """`relative_to` raises for a path outside the root, and losing the record would make an
    off-root read invisible to the very registry that exists to find them."""
    outside = tmp_path / "elsewhere/cost.json"
    outside.parent.mkdir(parents=True)
    outside.write_text(json.dumps({"generated": datetime.now(tz=UTC).isoformat()}), "utf-8")
    root = tmp_path / "root"
    root.mkdir()
    F.read_fresh(outside, max_age_h=48.0, caller="t", root=root)
    rows = [json.loads(x) for x in
            (root / F.REGISTRY_REL).read_text("utf-8").splitlines() if x.strip()]
    assert rows[0]["path"] == str(outside)
