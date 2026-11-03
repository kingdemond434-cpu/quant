"""fetch_alfred runs on an hourly clock and prints its failures: a requests/urllib error quotes
the request URL, and that URL carries `api_key`. Nothing it prints may carry the key."""
from __future__ import annotations

import sys
import urllib.error
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "desks" / "mt5"
for _p in (str(ROOT), str(DESK), str(DESK / "research")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from research import fetch_alfred as FA  # noqa: E402

SECRET = "SECRET"
URL = ("https://api.stlouisfed.org/fred/series/observations?series_id=GDP"
       f"&api_key={SECRET}&file_type=json")


class _NoRefusal:
    @staticmethod
    def fred_refusal(sid: str, leg: str) -> None:
        return None


def test_urlerror_with_api_key_prints_without_the_secret(tmp_path: Path, monkeypatch,
                                                         capsys) -> None:
    monkeypatch.setattr(FA, "OUT", tmp_path / "out")
    monkeypatch.setattr(FA, "REPORTS", tmp_path / "reports")
    (tmp_path / "out").mkdir()
    (tmp_path / "reports").mkdir()
    monkeypatch.setattr(FA, "api_key", lambda: SECRET)
    monkeypatch.setattr(FA, "_free_data", lambda: _NoRefusal)

    def boom(series_id: str, key: str, timeout: int = 60) -> Any:
        raise urllib.error.URLError(f"failed GET {URL} (api_key={SECRET})")
    monkeypatch.setattr(FA, "fetch_vintages", boom)
    FA.main(["GDP", "--force"])
    out = capsys.readouterr().out
    assert "URLError" in out and "api_key=REDACTED" in out
    assert SECRET not in out
    assert SECRET not in (tmp_path / "reports" / "alfred_vintages.json").read_text("utf-8")


def test_safe_blanks_bare_pairs_and_the_literal_key() -> None:
    assert SECRET not in FA._safe(urllib.error.URLError(f"api_key={SECRET}"))
    assert SECRET not in FA._safe(f"token {SECRET} leaked", SECRET)
    assert FA._safe("series_id=GDP") == "series_id=GDP"
