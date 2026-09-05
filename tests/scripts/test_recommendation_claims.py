"""TWO SESSIONS CANNOT SEE EACH OTHER PICK THE SAME ROW (R0553).

R0403's dangerous half is closed -- brain_mutex serialises organ brains desk-wide and agent
sessions run in git worktrees -- and the owed-work worker itself holds an flock for its whole
life, so two CRON workers cannot overlap. What survives is narrow and real: a worker run and any
other live session (another brain, a human, a sibling agent) can independently pick the same
ledger row and discover it at merge. Measured 2026-08-05: two sessions produced the same two mypy
fixes, the same flock diagnosis and the same try/finally structure within one hour.

THE DESIGN CONSTRAINT THAT KILLED R0403'S OWN PROPOSAL AND BINDS THIS ONE: a claims FILE read by
convention is a recall-based control, and check_mine_gate already retired data/mining_suspended
for exactly that reason ("a file is something rm defeats"). So the claim attaches to the UNIT OF
ASSIGNMENT -- the ledger row -- and its consumer is the batch BUILDER, which already reads the
ledger to assemble a brief. It fires without anyone remembering it.

THE TESTS THAT MATTER MOST ARE THE ONES PINNING WHAT A CLAIM IS NOT. A claim prevents duplicated
effort, which is cheap. A LEAKED claim -- dead session, compaction, SIGKILL -- would make a row
invisible to the queue, which is the disappearance the ledger exists to prevent and is strictly
worse than the problem being solved. So: it expires, an unparseable stamp expires, it changes no
`status`, and no fence can be quieted by it.
"""
from __future__ import annotations

import json
from argparse import Namespace
from datetime import UTC, datetime, timedelta

import pytest

from scripts import recommendations as rec


def _row(rid: str = "R0001", **over) -> dict:
    r = {"id": rid, "source": "cycle", "summary": "a row", "roi_bps": 0.0,
         "raised": "2026-08-01T00:00:00+00:00", "status": "open",
         "reason": None, "commit": None, "due": None, "disposed": None}
    r.update(over)
    return r


def _ago(hours: float) -> str:
    return (datetime.now(tz=UTC) - timedelta(hours=hours)).isoformat()


class TestClaimState:
    def test_an_unclaimed_row_is_free(self) -> None:
        assert rec.claim_state(_row()) == "FREE"

    def test_a_fresh_claim_is_held(self) -> None:
        assert rec.claim_state(_row(claimed_by="s", claimed_at=_ago(0.1))) == "HELD"

    def test_a_claim_past_the_ttl_expires(self) -> None:
        stale = _row(claimed_by="s", claimed_at=_ago(rec.CLAIM_TTL_H + 0.5))
        assert rec.claim_state(stale) == "EXPIRED"

    @pytest.mark.parametrize("bad", ["", "not-a-date", "2026-13-45", None])
    def test_an_unreadable_stamp_expires_rather_than_holding_forever(self, bad) -> None:
        """A corrupt claim must not be able to retire a row permanently -- that is the leak this
        whole design is arranged to make impossible."""
        assert rec.claim_state(_row(claimed_by="s", claimed_at=bad)) in ("EXPIRED", "FREE")

    @pytest.mark.parametrize("status", ["implemented", "rejected", "scheduled"])
    def test_a_disposed_row_is_never_held(self, status: str) -> None:
        assert rec.claim_state(_row(status=status, claimed_by="s",
                                    claimed_at=_ago(0.1))) == "FREE"

    def test_the_ttl_outlives_the_workers_own_timeout(self) -> None:
        """Sized past `timeout 3000` in run_recommendation_worker.sh: a run killed at its ceiling
        must not have its rows re-handed while its final commits are still landing."""
        assert rec.CLAIM_TTL_H * 3600 > 3000


class TestAClaimHidesNothingFromAnyFence:
    """The whole safety argument. A claim is a hint to the batch builder and nothing else."""

    def test_it_does_not_change_status(self) -> None:
        r = _row(claimed_by="s", claimed_at=_ago(0.1))
        assert r["status"] == "open"

    def test_a_claimed_row_is_still_owed(self) -> None:
        """`owed()` is what check_conversion and repair-mode read. A row quietly dropping out of
        it would let a session silence the backlog by claiming rows and walking away."""
        d = {"recommendations": [_row(raised="2026-07-01T00:00:00+00:00",
                                      claimed_by="s", claimed_at=_ago(0.1))]}
        orphans, _ = rec.owed(d)
        assert [r["id"] for r in orphans] == ["R0001"]


class TestTheBatchBuilderSkipsHeldRowsAndSaysSo:
    """The consumer. Held rows come out of THIS batch, never out of the queue."""

    def _batch(self, rows: list[dict], batch: int = 2) -> tuple[list[str], list[str]]:
        open_rows = [r for r in rows if r.get("status") == "open"]
        held = [r for r in open_rows if rec.claim_state(r) == "HELD"]
        free = [r for r in open_rows if rec.claim_state(r) != "HELD"]
        return [r["id"] for r in free[:batch]], [r["id"] for r in held]

    def test_a_held_row_is_not_offered(self) -> None:
        taken, held = self._batch([
            _row("R0001", claimed_by="other", claimed_at=_ago(0.1)),
            _row("R0002"), _row("R0003")])
        assert taken == ["R0002", "R0003"] and held == ["R0001"]

    def test_an_expired_claim_is_offered_again(self) -> None:
        taken, held = self._batch([
            _row("R0001", claimed_by="dead", claimed_at=_ago(rec.CLAIM_TTL_H + 1)),
            _row("R0002")])
        assert taken == ["R0001", "R0002"] and held == []

    def test_the_batch_stays_full_when_rows_are_held(self) -> None:
        """Skipping must not SHRINK the batch -- a session that claims rows would otherwise
        starve the next worker, turning a de-duplication control into a throughput cut."""
        rows = [_row("R0001", claimed_by="o", claimed_at=_ago(0.1)),
                _row("R0002"), _row("R0003"), _row("R0004")]
        taken, _ = self._batch(rows, batch=3)
        assert len(taken) == 3


class TestTheClaimVerb:
    @pytest.fixture
    def ledger(self, tmp_path, monkeypatch):
        path = tmp_path / "ledger.json"
        path.write_text(json.dumps({"recommendations": [_row("R0001"), _row("R0002")]}), "utf-8")
        monkeypatch.setattr(rec, "LEDGER", path)
        monkeypatch.setattr(rec, "_LOCK", tmp_path / "lock")
        return path

    def _rows(self, path):
        return {r["id"]: r for r in json.loads(path.read_text("utf-8"))["recommendations"]}

    def test_it_stamps_who_and_when(self, ledger) -> None:
        rec.claim(Namespace(by="sess-a", ids=["R0001"]))
        row = self._rows(ledger)["R0001"]
        assert row["claimed_by"] == "sess-a" and rec.claim_state(row) == "HELD"
        assert "claimed_by" not in self._rows(ledger)["R0002"]

    def test_it_refuses_an_unknown_id_rather_than_claiming_nothing(self, ledger) -> None:
        """A typo that silently claims nothing leaves the caller believing it holds a row."""
        with pytest.raises(SystemExit):
            rec.claim(Namespace(by="sess-a", ids=["R9999"]))

    def test_it_refuses_an_empty_holder(self, ledger) -> None:
        with pytest.raises(SystemExit):
            rec.claim(Namespace(by="   ", ids=["R0001"]))

    def test_it_does_not_steal_a_live_claim(self, ledger) -> None:
        rec.claim(Namespace(by="sess-a", ids=["R0001"]))
        rec.claim(Namespace(by="sess-b", ids=["R0001"]))
        assert self._rows(ledger)["R0001"]["claimed_by"] == "sess-a"

    def test_it_does_take_over_an_expired_claim(self, ledger) -> None:
        d = json.loads(ledger.read_text("utf-8"))
        d["recommendations"][0].update(claimed_by="dead", claimed_at=_ago(rec.CLAIM_TTL_H + 2))
        ledger.write_text(json.dumps(d), "utf-8")
        rec.claim(Namespace(by="sess-b", ids=["R0001"]))
        assert self._rows(ledger)["R0001"]["claimed_by"] == "sess-b"

    def test_reclaiming_your_own_row_refreshes_it(self, ledger) -> None:
        """A long session must be able to keep its rows without another one stealing them."""
        d = json.loads(ledger.read_text("utf-8"))
        d["recommendations"][0].update(claimed_by="sess-a", claimed_at=_ago(rec.CLAIM_TTL_H + 2))
        ledger.write_text(json.dumps(d), "utf-8")
        rec.claim(Namespace(by="sess-a", ids=["R0001"]))
        assert rec.claim_state(self._rows(ledger)["R0001"]) == "HELD"


# --------------------------------------------------- a merge must not mint a phantom row (R0739)


def test_NO_TWO_OPEN_ROWS_ARE_THE_SAME_RECOMMENDATION_TWICE() -> None:
    """A DUPLICATE ROW IS A PHANTOM OBLIGATION AND IT DEFEATS THE CLAIM LOCK ABOVE.

    Measured 2026-08-20: the 2026-08-19 re-merge minted THREE rows (R0684, R0685, R0686) whose
    summaries are sha1-identical to R0639/R0640/R0641 and which carry the SAME `raised` timestamp
    to the microsecond. Each was minted on the recorded assertion that the colliding id held "a
    DIFFERENT recommendation on this branch"; for all three pairs that assertion was false.

    THE COST IS NOT COSMETIC, AND IT LANDED ON THIS FILE'S OWN CONTROL. The claim above attaches
    to the ROW, so two ids for one recommendation are two independently claimable rows: on
    2026-08-20 a live sibling held R0639 while its byte-identical twin R0684 was handed to another
    worker in the same batch. The lock was intact and irrelevant -- the queue routed around it.
    It also inflates the open-backlog denominator that decides repair-mode (L1.28b(d)).

    Disposed duplicates are fine and deliberately allowed: the repair is to reject the
    later-minted id with a reason, which preserves every citation of the surviving id. Only two
    OPEN rows saying the same thing are a defect.
    """
    rows = json.loads(rec.LEDGER.read_text("utf-8"))["recommendations"]
    live: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        if r.get("status") != "open":
            continue
        live.setdefault((r["summary"], r.get("raised", "")), []).append(r["id"])
    dupes = {k[1]: v for k, v in live.items() if len(v) > 1}
    assert not dupes, (
        "open rows duplicated -- reject the later-minted id citing the survivor, do not delete "
        f"it (deleting a row does not delete the obligation): {dupes}"
    )
