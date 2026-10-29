"""ONE robots.txt matcher (LAWS 5e amended 2026-10-14): `polite_fetch.RobotsRules` (read through
`HostAccess.permits`) and `research/hard_stop.robots_verdict` must agree on every row of the
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


@pytest.mark.parametrize("row", ROWS, ids=[r["name"] for r in ROWS])
def test_polite_fetch_reads_every_row(row: dict[str, Any]) -> None:
    acc = pf.HostAccess(None)
    ok, why = acc.permits(row["url"], send=_send_for(row))
    assert ok is row["allowed"], (row["name"], why)
    if int(row["robots_status"]) in (401, 403, 429):
        assert acc.hold(row["url"]), "a 401/403/429 on robots.txt holds the site"


@pytest.mark.parametrize("row", ROWS, ids=[r["name"] for r in ROWS])
def test_hard_stop_reads_every_row_the_same(row: dict[str, Any]) -> None:
    hs = pytest.importorskip("hard_stop")
    if not hasattr(hs, "robots_verdict"):
        pytest.skip("hard_stop.robots_verdict lands with alt-seat-cells; table binds it then")
    got = hs.robots_verdict(row["url"], int(row["robots_status"]), row["robots_body"])
    assert got["allowed"] is row["allowed"], (row["name"], got)
