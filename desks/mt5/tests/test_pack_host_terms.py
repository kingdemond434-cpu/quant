"""Every raw-pack host has a terms row, and only a quoted clause mints (#229 stacked).

The raw-pack lane mints on `confirmed` only. These tests pin the properties that make that
lawful rather than merely closed: every pack host is governed (nothing reads `ungoverned`), every
confirmed row carries a verbatim quote and the URL it was read on, a row the container could not
read says so and names the box action, the rows live in alt_proxies' ONE table, and the census
the report publishes is the census the gate computes.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

DESK = Path(__file__).resolve().parents[1]
ROOT = DESK.parent.parent
for _p in (str(DESK), str(DESK / "research"), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research.pack_host_terms import PACK_HOST_TERMS  # noqa: E402

from research import alt_proxies as A  # noqa: E402
from research import pack_cells as PK  # noqa: E402

VERDICTS = ("confirmed", "to_confirm", "refused")


def test_every_pack_host_has_a_terms_row() -> None:
    missing = [(p["id"], p.get("url")) for p in PK.packs()
               if "://" in str(p.get("url") or "") and A.terms_gate(str(p["url"]))[0]
               == "ungoverned"]
    assert missing == [], missing
    assert all(PK.pack_terms(p)["terms"] != "ungoverned" for p in PK.packs())


def test_every_confirmed_row_has_a_verbatim_quote_and_url() -> None:
    for host, row in PACK_HOST_TERMS.items():
        if "adopt" in row:
            continue
        assert row["verdict"] in VERDICTS, host
        assert row["terms_url"].startswith("http"), host
        assert row["checked_at"] == "2026-10-07", host
        head = row["judgement"].split(":")[0].split(" ")[0].upper()
        assert head == row["verdict"].upper(), (host, row["judgement"][:40])
        if row["verdict"] in ("confirmed", "refused"):
            assert len(row["terms_quote"].strip()) >= 20, host
        if row.get("fetch_status") == "FETCH_BLOCKED":
            assert row["verdict"] == "to_confirm" and row.get("box_action"), host
    # and the minting gate enforces it: a confirmed row with no quote does not mint
    for p in PK.packs():
        gate = PK.pack_terms(p)
        if gate["terms"] == "confirmed":
            assert PK._has_quote(gate["terms_ref"]), (p["id"], gate)


def test_rows_live_in_the_one_terms_table() -> None:
    for host, row in PACK_HOST_TERMS.items():
        tid = row.get("adopt") or A.PACK_HOST_PREFIX + host
        assert A.TERMS_HOSTS[host] == tid, host
        assert tid in A.TERMS or tid in A.GATE_TERMS, host
        if "adopt" not in row:
            assert A.GATE_TERMS[tid][0] == row["verdict"]
            assert A.GATE_TERMS_EVIDENCE[tid]["terms_quote"] == row["terms_quote"]
            assert A.terms_gate("https://www." + host + "/x")[0] == row["verdict"]
            if row["verdict"] == "confirmed" and row.get("attribution"):
                assert A.attribution_for(tid) is not None
    # no pack host key shadows another governed host
    keys = list(A.TERMS_HOSTS)
    assert len(keys) == len(set(keys))


def test_a_refused_or_unquoted_host_mints_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    import libs.moat.registry as reg
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(reg, "record_discovery", lambda **kw: (calls.append(kw), ("D", True))[1])
    monkeypatch.setattr(reg, "enqueue_candidate", lambda **kw: (calls.append(kw), ("C", True))[1])
    refused = next(h for h, r in PACK_HOST_TERMS.items() if r.get("verdict") == "refused")
    res = PK.emit_for({"id": "r", "url": f"https://www.{refused}/x"}, ["v"], ["XAUUSD"])
    assert res["status"] == "BLOCKED_ON_TERMS:refused" and calls == []
    blocked = next(h for h, r in PACK_HOST_TERMS.items() if r.get("fetch_status"))
    res = PK.emit_for({"id": "b", "url": f"https://www.{blocked}/x"}, ["v"], ["XAUUSD"])
    assert res["status"] == "BLOCKED_ON_TERMS:to_confirm" and calls == []
    monkeypatch.setitem(A.GATE_TERMS, "unquoted_test_row", ("confirmed", "no evidence"))
    res = PK.emit_for({"id": "u", "terms_ref": "unquoted_test_row"}, ["v"], ["XAUUSD"])
    assert res["status"] == "BLOCKED_ON_TERMS:to_confirm" and calls == []
    confirmed = next(h for h, r in PACK_HOST_TERMS.items() if r.get("verdict") == "confirmed")
    res = PK.emit_for({"id": "c", "url": f"https://www.{confirmed}/x"}, ["v"], ["XAUUSD"])
    assert res["emitted"] > 0


def test_the_census_is_computed_and_is_what_the_report_publishes(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    census = PK.terms_census()
    b = census["buckets"]
    assert set(b) == set(PK.CENSUS_BUCKETS)
    assert sum(v["packs"] for v in b.values()) == census["n_packs"] == len(PK.packs())
    assert sum(v["hosts"] for v in b.values()) == census["n_hosts"]
    assert b["ungoverned"] == {"hosts": 0, "packs": 0}
    minted = sum(PK.pack_terms(p)["terms"] == "confirmed" for p in PK.packs())
    assert b["confirmed"]["packs"] == minted
    monkeypatch.setattr(PK, "CURSOR", tmp_path / "cursor.json")
    monkeypatch.setattr(PK, "chain", dict)
    monkeypatch.setattr(PK, "_registry_counts", lambda: ({}, ""))
    monkeypatch.setattr(PK, "world_rows", lambda *_a, **_k: ([], ""))
    doc = PK.build(budget_s=5.0, dry_run=True)
    assert doc["terms_census"]["buckets"] == b
