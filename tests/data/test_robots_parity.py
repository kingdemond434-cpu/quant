"""ONE robots.txt matcher: `polite_fetch.RobotsRules` (read through `HostAccess.permits_labelled`)
and `research/hard_stop.robots_verdict` must agree -- as a LABEL (LAWS 5e) -- on every row of the
shared table `tests/data/robots_parity_fixtures.json`. Where hard_stop has no `robots_verdict`
yet (it lands with alt-seat-cells), its half skips and the table still binds polite_fetch."""
from __future__ import annotations

import io
import json
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "desks" / "mt5"), str(ROOT / "desks" / "mt5" / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.data import polite_fetch as pf  # noqa: E402

TABLE = json.loads((Path(__file__).with_name("robots_parity_fixtures.json"))
                   .read_text(encoding="utf-8"))
ROWS = TABLE["fixtures"]


class _Resp(io.BytesIO):
    status = 200
    headers = Message()

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *a: object) -> None:
        self.close()


def _send_for(row: dict[str, Any]) -> Any:
    def send(req: Any, timeout: float) -> Any:
        assert req.full_url.endswith("/robots.txt"), "only robots.txt may be read here"
        code = int(row["robots_status"])
        if code == 0:
            raise urllib.error.URLError("unreachable")
        if code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "x", Message(), io.BytesIO(b""))
        return _Resp(str(row["robots_body"]).encode("utf-8"))
    return send


def test_the_table_uses_the_desk_token() -> None:
    assert TABLE["product"] == pf.DESK_UA_PRODUCT


def _expected_label(row: dict[str, Any]) -> str:
    """The LAWS 5e label for a row: robots' own opinion (`allowed`) read as a label."""
    code = int(row["robots_status"])
    if code == 0 or code >= 500:
        return "ACCESS_UNCLEAR"
    return "PUBLIC" if row["allowed"] else "PUBLIC_WITH_TERMS"


@pytest.mark.parametrize("row", ROWS, ids=[r["name"] for r in ROWS])
def test_polite_fetch_reads_every_row(row: dict[str, Any]) -> None:
    """The matcher's verdict reaches the fetch as a LABEL, never a refusal (LAWS 5e): every row
    proceeds except an access control on robots.txt itself (401/403/429), which holds."""
    acc = pf.HostAccess(None)
    ok, why, label = acc.permits_labelled(row["url"], send=_send_for(row))
    if int(row["robots_status"]) in (401, 403, 429):
        assert not ok and acc.hold(row["url"]), "a 401/403/429 on robots.txt holds the site"
        return
    assert ok is True and why == "", (row["name"], why)
    assert label["access_label"] == _expected_label(row), (row["name"], label)
    assert label["redistribute_allowed"] is False, "no robots label grants redistribution"


@pytest.mark.parametrize("row", ROWS, ids=[r["name"] for r in ROWS])
def test_hard_stop_reads_every_row_the_same(row: dict[str, Any]) -> None:
    hs = pytest.importorskip("hard_stop")
    if not hasattr(hs, "robots_verdict"):
        pytest.skip("hard_stop.robots_verdict lands with alt-seat-cells; table binds it then")
    got = hs.robots_verdict(row["url"], int(row["robots_status"]), row["robots_body"])
    assert got["allowed"] is row["allowed"], (row["name"], got)
    # ...and the same LABEL, with the fetch proceeding (LAWS 5e) unless robots.txt itself was
    # an access control
    refused = int(row["robots_status"]) in (401, 403, 429)
    assert got["proceed"] is (not refused), (row["name"], got)
    if not refused:
        assert got["access_label"] == _expected_label(row), (row["name"], got)
