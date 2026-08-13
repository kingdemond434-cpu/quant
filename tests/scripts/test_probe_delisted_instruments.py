"""R0313: the venue-side delisted-instrument probe.

The whole value of this probe is a distinction that is easy to collapse and expensive to get
wrong: a venue that measurably has no dead instruments to give (ABSENT -> reconstruct from
archives) versus a venue we simply failed to reach today (UNREACHABLE -> ask again). Recording
the second as the first is how "we checked, there is nothing there" gets written down for a venue
nobody actually asked.

The other guard here is truncation. The first cut of probe_bitmex stopped at the venue's 500-row
page cap and reported "500 dead, 0 live"; paginating turned that into 3077 dead vs 32 live. Past
a page cap every derived total stays plausible and is silently wrong, so a full page must never
be reported as a complete roster.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import scripts.probe_delisted_instruments as p


class TestGrade:
    def test_an_unreachable_venue_is_never_graded_absent(self) -> None:
        """The distinction the probe exists to preserve."""
        assert p.grade({"error": "URLError: timed out"}) == p.UNREACHABLE

    def test_a_reached_venue_with_no_dead_names_is_absent(self) -> None:
        assert p.grade({"states": {"live": 400}, "dead": []}) == p.ABSENT

    def test_dead_names_read_available(self) -> None:
        assert p.grade({"dead": ["XBTZ18", "ETHZ18"]}) == p.AVAILABLE

    def test_partial_is_not_promoted_to_available(self) -> None:
        """Binance's SETTLING rows are dated contracts mid-retirement, not recovered dead perps.

        Grading them AVAILABLE would report the survivorship gap as closed for a venue where it
        is not, which is the one direction of error that stops anyone looking again.
        """
        assert p.grade({"dead": ["BTCUSDT_250101"], "partial": True}) == p.PARTIAL


class TestSplit:
    def test_partitions_on_the_venues_own_state_vocabulary(self) -> None:
        rows = [{"symbol": "A", "state": "Open"}, {"symbol": "B", "state": "Settled"},
                {"symbol": "C", "state": "Settled"}, {"symbol": "D", "state": "Delisted"}]
        r = p._split(rows, "symbol", "state", {"Settled", "Delisted"})
        assert r["dead"] == ["B", "C", "D"]
        assert r["n_live"] == 1
        assert r["states"] == {"Open": 1, "Settled": 2, "Delisted": 1}

    def test_dead_roster_is_deduplicated_and_sorted(self) -> None:
        rows = [{"symbol": "B", "state": "Settled"}, {"symbol": "A", "state": "Settled"},
                {"symbol": "B", "state": "Settled"}]
        assert p._split(rows, "symbol", "state", {"Settled"})["dead"] == ["A", "B"]


class TestRun:
    def test_a_failing_probe_records_a_refusal_not_a_zero(
            self, tmp_path: Path, monkeypatch) -> None:
        """"We could not ask" and "there is nothing there" are different claims."""
        def boom() -> dict:
            raise TimeoutError("venue down")
        monkeypatch.setitem(p.PROBES, "bitmex", boom)
        res = p.run(["bitmex"], root=tmp_path)
        v = res["venues"]["bitmex"]
        assert v["verdict"] == p.UNREACHABLE
        assert "TimeoutError" in v["error"]
        # and it must not be counted as a measured venue
        assert res["n_reached"] == 0
        assert res["n_dead_total"] == 0

    def test_the_roster_is_written_to_disk_not_just_counted(
            self, tmp_path: Path, monkeypatch) -> None:
        """A probe that recorded only counts would be a catalogue; the dead NAMES are the data."""
        monkeypatch.setitem(p.PROBES, "coinbase", lambda: {
            "endpoint": "GET x", "states": {"delisted": 2}, "dead": ["FTT-USD", "LUNA-USD"],
            "n_live": 5})
        res = p.run(["coinbase"], root=tmp_path)
        roster = json.loads((tmp_path / "data/delisted_rosters/coinbase.json").read_text("utf-8"))
        assert sorted(roster["symbols"]) == ["FTT-USD", "LUNA-USD"]
        assert roster["n_dead"] == 2
        assert res["venues"]["coinbase"]["n_dead"] == 2
        assert res["n_available"] == 1


class TestRosterIsPurgeProof:
    def test_a_name_the_venue_stops_reporting_is_not_lost(
            self, tmp_path: Path, monkeypatch) -> None:
        """The whole point of the archive: the venue's dead list is itself venue-controlled.

        Overwriting on each run would let the artifact silently SHRINK, losing exactly the names
        it exists to preserve (the R0303 lesson: archive what the venue deletes).
        """
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["FTTUSDT", "LUNAUSDT"], "n_live": 1})
        p.run(["bybit"], root=tmp_path)
        # the venue now reports only one of them
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["LUNAUSDT"], "n_live": 1})
        p.run(["bybit"], root=tmp_path)
        roster = json.loads((tmp_path / "data/delisted_rosters/bybit.json").read_text("utf-8"))
        assert set(roster["symbols"]) == {"FTTUSDT", "LUNAUSDT"}, "a dropped name was lost"
        assert roster["n_dead"] == 2

    def test_first_seen_is_never_rewritten(self, tmp_path: Path, monkeypatch) -> None:
        """first_seen dates when a name left the venue; last_seen tracks the latest confirmation."""
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["FTTUSDT"], "n_live": 1})
        p.run(["bybit"], root=tmp_path)
        first = json.loads((tmp_path / "data/delisted_rosters/bybit.json").read_text(
            "utf-8"))["symbols"]["FTTUSDT"]["first_seen"]
        p.run(["bybit"], root=tmp_path)
        after = json.loads((tmp_path / "data/delisted_rosters/bybit.json").read_text(
            "utf-8"))["symbols"]["FTTUSDT"]
        assert after["first_seen"] == first

    def test_a_legacy_list_roster_keeps_every_name(self, tmp_path: Path, monkeypatch) -> None:
        """Found by running it: the first cut wrote `symbols` as a LIST, and the dated-dict
        version crashed on it with a TypeError. The names are the irreplaceable part, so they
        carry over -- with first_seen honestly "unknown" rather than back-dated to today, which
        would assert a measurement nobody made."""
        d = tmp_path / "data/delisted_rosters"
        d.mkdir(parents=True)
        (d / "bybit.json").write_text(json.dumps({"venue": "bybit", "symbols": ["OLD1", "OLD2"]}))
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["NEW1"], "n_live": 1})
        p.run(["bybit"], root=tmp_path)
        roster = json.loads((d / "bybit.json").read_text("utf-8"))
        assert set(roster["symbols"]) == {"OLD1", "OLD2", "NEW1"}
        assert roster["symbols"]["OLD1"]["first_seen"] == "unknown"
        assert roster["symbols"]["NEW1"]["first_seen"] != "unknown"

    def test_a_corrupt_roster_refuses_rather_than_overwrites(
            self, tmp_path: Path, monkeypatch) -> None:
        """History we cannot re-earn is never silently replaced by a fresh file."""
        d = tmp_path / "data/delisted_rosters"
        d.mkdir(parents=True)
        (d / "bybit.json").write_text('{"symbols": "not-a-roster"}')
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["NEW1"], "n_live": 1})
        with pytest.raises(ValueError, match="not a roster"):
            p.run(["bybit"], root=tmp_path)

    def test_only_genuinely_new_names_count_as_new(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["A", "B"], "n_live": 1})
        assert p.run(["bybit"], root=tmp_path)["venues"]["bybit"]["n_new_this_run"] == 2
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["A", "B", "C"], "n_live": 1})
        assert p.run(["bybit"], root=tmp_path)["venues"]["bybit"]["n_new_this_run"] == 1

    def test_no_roster_file_for_a_venue_with_nothing_to_give(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setitem(p.PROBES, "upbit", lambda: {
            "endpoint": "GET x", "states": {"live": 800}, "dead": [], "n_live": 800})
        p.run(["upbit"], root=tmp_path)
        assert not (tmp_path / "data/delisted_rosters/upbit.json").exists()

    def test_mixed_run_counts_only_reached_venues(self, tmp_path: Path, monkeypatch) -> None:
        def boom() -> dict:
            raise OSError("no route to host")
        monkeypatch.setitem(p.PROBES, "okx", boom)
        monkeypatch.setitem(p.PROBES, "bybit", lambda: {
            "endpoint": "GET x", "states": {}, "dead": ["FOO"], "n_live": 1})
        res = p.run(["okx", "bybit"], root=tmp_path)
        assert res["n_venues"] == 2
        assert res["n_reached"] == 1        # the denominator excludes what we could not ask
        assert res["n_available"] == 1


class TestMainRefusal:
    def test_an_entirely_unreachable_run_exits_nonzero(self, tmp_path: Path, monkeypatch) -> None:
        """A registry built from zero reachable venues is not a clean result."""
        def boom() -> dict:
            raise TimeoutError("down")
        for name in list(p.PROBES):
            monkeypatch.setitem(p.PROBES, name, boom)
        monkeypatch.setattr(p, "OUT", tmp_path / "data/delisted_instruments.json")
        monkeypatch.setattr(p, "guard", lambda *a, **k: None)
        assert p.main([]) == 1

    def test_a_reachable_run_exits_zero(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setitem(p.PROBES, "upbit", lambda: {
            "endpoint": "GET x", "states": {"live": 3}, "dead": [], "n_live": 3})
        monkeypatch.setattr(p, "OUT", tmp_path / "data/delisted_instruments.json")
        monkeypatch.setattr(p, "guard", lambda *a, **k: None)
        assert p.main(["--venue", "upbit"]) == 0
        assert (tmp_path / "data/delisted_instruments.json").exists()


class TestTruncationIsFlagged:
    @pytest.mark.parametrize("n_rows,expect_note", [(500, True), (12, False)])
    def test_a_full_page_is_never_reported_as_a_complete_roster(
            self, monkeypatch, n_rows: int, expect_note: bool) -> None:
        """The measured instance: count=500 read "500 dead, 0 live" until it was paginated.

        A page returning exactly the cap means there is more behind it; a SHORT page is the only
        honest end-of-data signal.
        """
        rows = [{"symbol": f"S{i}", "state": "Settled"} for i in range(n_rows)]
        monkeypatch.setattr(p, "_get", lambda url, timeout=30: rows)
        r = p.probe_bitmex(page=500, max_pages=1)
        assert ("TRUNCATED" in r.get("note", "")) is expect_note

    def test_pagination_walks_until_a_short_page(self, monkeypatch) -> None:
        """Three pages: two full, one short -- all rows collected, no truncation flag."""
        pages = [[{"symbol": f"A{i}", "state": "Settled"} for i in range(4)],
                 [{"symbol": f"B{i}", "state": "Settled"} for i in range(4)],
                 [{"symbol": "C0", "state": "Open"}]]
        monkeypatch.setattr(p, "_get", lambda url, timeout=30: pages.pop(0))
        r = p.probe_bitmex(page=4, max_pages=10)
        assert len(r["dead"]) == 8
        assert r["n_live"] == 1
        assert "note" not in r
