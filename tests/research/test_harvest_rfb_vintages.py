"""Tests for ``scripts/harvest_rfb_vintages.py`` (R0472) -- the backfill that turns recovered
RFB releases into a vintage stack.

The fixtures are REAL ``.xls`` bytes through the real OLE2/BIFF writer, not mocked parses: the
harvest's whole job is the chain filename-token -> era-aware parse -> conservation -> store, and
a test that stubs any link proves only that the stubs agree with each other. Values are chosen so
the in-data identities close exactly, and the one deliberately-broken workbook breaks them by a
whole R$mn -- the magnitude of a real swapped-column error, far above the grand identity's 1e-6
tolerance.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from tests.data.xls_builder import build_xls, cell_number, cell_sst

from libs.research.vintage import as_of, read_log

_ROOT = Path(__file__).resolve().parents[2]

_MONTH_NAMES = (
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def _load():  # type: ignore[no-untyped-def]
    """Import the script by path -- ``scripts/`` is not an importable package."""
    spec = importlib.util.spec_from_file_location(
        "harvest_rfb_vintages", _ROOT / "scripts" / "harvest_rfb_vintages.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _panel_xls(months: list[tuple[str, float, float, float, float, float]],
               *, break_subtotal: bool = False) -> bytes:
    """An RFB-shaped workbook: MES/ANO + PF|PJ|Subtotal twice + domestic + Total Geral.

    ``months`` rows are (label, exch_pf, exch_pj, noexch_pf, noexch_pj, domestic); subtotals and
    the grand total are DERIVED so the conservation laws close by construction unless
    ``break_subtotal`` shifts the first subtotal off by 1.0.
    """
    strings = ["MES/ANO", "PF", "PJ", "Subtotal", "Total Geral"]
    cells = b""
    # header row 0: period header + grand-total header (col 8)
    cells += cell_sst(0, 0, 0) + cell_sst(0, 8, 4)
    # group row 1: PF PJ Subtotal twice, cols 1..6; col 7 is the bare domestic column
    for col, idx in ((1, 1), (2, 2), (3, 3), (4, 1), (5, 2), (6, 3)):
        cells += cell_sst(1, col, idx)
    for r, (label, epf, epj, npf, npj, dom) in enumerate(months, start=2):
        strings.append(label)
        cells += cell_sst(r, 0, len(strings) - 1)
        esub = epf + epj + (1.0 if break_subtotal else 0.0)
        nsub = npf + npj
        for col, value in ((1, epf), (2, epj), (3, esub), (4, npf), (5, npj), (6, nsub),
                           (7, dom), (8, esub + nsub + dom)):
            cells += cell_number(r, col, value)
    return build_xls([("Relatorio1", cells)], strings)


def _months(n: int, *, base: float, year: int = 2020) -> list[
    tuple[str, float, float, float, float, float]
]:
    return [
        (f"{_MONTH_NAMES[i % 12]} de {year + i // 12}",
         base + i, 10.0 + i, 5.0 + i, 2.0 + i, 1.0 + i)
        for i in range(n)
    ]


def _write(root: Path, token: str, blob: bytes) -> None:
    raw = root / "data/rfb_vintages/raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / f"{token}.xls").write_bytes(blob)


def test_backfill_records_each_release_under_its_own_vintage(tmp_path: Path) -> None:
    mod = _load()
    # DDMMYYYY era release, then a YYYYMMDD era release that REVISES month 1 upward.
    _write(tmp_path, "04012021", _panel_xls(_months(14, base=100.0)))
    revised = _months(15, base=100.0)
    revised[0] = (revised[0][0], 140.0, *revised[0][2:])
    _write(tmp_path, "20210604", _panel_xls(revised))

    report = mod.harvest(tmp_path)
    assert report["status"] == "OK", report
    assert [r["vintage"] for r in report["releases"]] == ["2021-01-04", "2021-06-04"]
    assert all(r["status"] == "RECORDED" for r in report["releases"])

    # Point-in-time semantics: the January value is the FIRST print at the first vintage and the
    # revised print after the second -- and absent before either (knowability, not backfill).
    series = "RFB_CRIPTO_EXCHANGE_PF"
    assert as_of(tmp_path, series, "2020-12-31") == {}
    assert as_of(tmp_path, series, "2021-01-04")["2020-01"] == 100.0
    assert as_of(tmp_path, series, "2021-06-04")["2020-01"] == 140.0

    # Idempotence: the second pass parses everything and appends NOTHING.
    n_before = len(read_log(tmp_path, series))
    again = mod.harvest(tmp_path)
    assert again["status"] == "OK"
    assert again["n_new_rows"] == 0
    assert len(read_log(tmp_path, series)) == n_before


def test_broken_conservation_is_refused_and_pollutes_nothing(tmp_path: Path) -> None:
    mod = _load()
    _write(tmp_path, "04012021", _panel_xls(_months(14, base=100.0), break_subtotal=True))
    report = mod.harvest(tmp_path)
    assert report["status"] == "REFUSED"
    assert report["n_refused"] == 1 and report["n_new_rows"] == 0
    assert "conservation" in str(report["releases"][0]["reason"])
    assert read_log(tmp_path, "RFB_CRIPTO_EXCHANGE_PF") == []


def test_undateable_filename_is_refused_not_defaulted(tmp_path: Path) -> None:
    mod = _load()
    _write(tmp_path, "notadate", _panel_xls(_months(14, base=100.0)))
    report = mod.harvest(tmp_path)
    assert report["status"] == "REFUSED"
    assert "8 digits" in str(report["releases"][0]["reason"])


def test_empty_archive_reads_no_data_never_ok(tmp_path: Path) -> None:
    mod = _load()
    report = mod.harvest(tmp_path)
    assert report["status"] == "NO-DATA"
    assert report["n_files"] == 0
    assert report["store"]["status"] == "UNMEASURED"


def test_live_fetch_downloads_only_missing_releases(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mod = _load()
    raw = tmp_path / "data/rfb_vintages/raw"
    raw.mkdir(parents=True)
    (raw / "04012021.xls").write_bytes(b"already-here")

    listing = (
        "<a href='x/criptoativos_dados_abertos_04012021.xls/view'>old</a>"
        "<a href='x/criptoativos_dados_abertos_20210604.xls/view'>new</a>"
    )

    class _Resp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    calls: list[str] = []

    def fake_urlopen(req, timeout=0.0):  # type: ignore[no-untyped-def]
        url = req.full_url
        calls.append(url)
        if url.endswith("/arquivos"):
            return _Resp(listing.encode())
        return _Resp(b"xls-bytes")

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    out = mod.fetch_new_releases(raw)
    assert out["status"] == "OK"
    assert out["n_new"] == 1 and out["new"] == ["20210604"]
    assert (raw / "20210604.xls").read_bytes() == b"xls-bytes"
    # the release already on disk was not re-fetched
    assert not any("04012021" in u for u in calls if u.endswith(".xls"))


def test_unreachable_live_index_degrades_loudly(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    mod = _load()

    def dead(req, timeout=0.0):  # type: ignore[no-untyped-def]
        raise OSError("no route to host")

    monkeypatch.setattr(mod.urllib.request, "urlopen", dead)
    out = mod.fetch_new_releases(tmp_path)
    assert out["status"] == "UNREACHABLE"
    assert out["n_new"] == 0 and "no route" in str(out["detail"])
