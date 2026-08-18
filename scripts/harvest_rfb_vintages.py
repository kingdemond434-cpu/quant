"""Backfill + forward-capture of the RFB crypto-panel VINTAGE STACK (R0472, OP-047, L1.11a).

WHAT THIS CLOSES. libs/research/vintage.py can say what was knowable on date d, but its history
began 2026-08-12 -- machinery without SAMPLE. Receita Federal republishes the WHOLE panel under a
dated filename (`criptoativos_dados_abertos_<token>.xls`), so every recovered release is a genuine
vintage: the raw workbooks live in data/rfb_vintages/raw/, fetched from the live server while they
lasted and from the Wayback `id_` raw-replay modifier after they 404ed. This organ turns that
archive into RFB_CRIPTO_* rows in the vintage store, each release recorded under its OWN
publication date -- never today's -- and then keeps the stack current by checking the live
`arquivos` listing for releases the archive does not hold yet.

REFUSAL IS THE DESIGN, REPAIR IS NOT. A workbook that fails the era-aware parse or whose in-data
conservation laws (PF+PJ=Subtotal twice, subtotals+domestic=Total Geral) do not close is REFUSED
and reported, never coerced: a mislabelled or mis-parsed vintage would invert the very revisions
the stack exists to measure. Files are processed oldest-vintage-first and the store appends only
CHANGES, so re-running over an unchanged archive records zero rows and that is the healthy state.

    python scripts/harvest_rfb_vintages.py [--no-fetch] [--root PATH]

Statuses: OK (recorded/idempotent), NO-DATA (archive absent on this box -- data/ is untracked, so
a clone without the raw files must say so rather than report a healthy harvest over nothing, and
the exit stays 0 exactly like collect_fred_macro's key-gated skip), REFUSED (a present workbook
failed the parse or its own arithmetic -- exit 2, because every archived release parses clean and
a refusal on a re-run means regression, not weather).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from libs.data.xls_reader import XlsError, read_xls  # noqa: E402
from libs.ops.lawful import guard  # noqa: E402
from libs.research.rfb_panel import (  # noqa: E402
    SERIES_PREFIX,
    RfbPanelError,
    extract,
    publication_date,
)
from libs.research.vintage import record, summarise  # noqa: E402

_RAW_DIR = "data/rfb_vintages/raw"
_REPORT = "data/rfb_vintage_harvest.json"

#: The live Plone listing. New releases appear here monthly-ish; old ones quietly 404 (which is
#: why the Wayback half of this archive exists at all).
_LIVE_INDEX = (
    "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/"
    "declaracoes-e-demonstrativos/criptoativos/arquivos"
)
_NAME_RE = re.compile(r"criptoativos_dados_abertos_(\d{8})\.xls\b")


def fetch_new_releases(raw_dir: Path, *, timeout: float = 25.0) -> dict[str, object]:
    """Download releases the archive does not hold yet, and say honestly when we cannot look.

    A network failure here is WEATHER, not a harvest failure: the backfill below still runs over
    everything already on disk. But it is reported as its own status, never folded into OK --
    "checked the live page and found nothing new" and "could not check" are different claims
    (L1.28a), and only one of them is evidence about the source.
    """
    try:
        req = urllib.request.Request(_LIVE_INDEX, headers={"User-Agent": "quant-rfb/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # any transport failure: degrade to backfill-only, loudly
        return {"status": "UNREACHABLE", "detail": repr(exc)[:200], "n_new": 0}

    tokens = sorted(set(_NAME_RE.findall(page)))
    fetched: list[str] = []
    failed: list[str] = []
    for token in tokens:
        dest = raw_dir / f"{token}.xls"
        if dest.exists():
            continue
        url = f"{_LIVE_INDEX}/criptoativos_dados_abertos_{token}.xls"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "quant-rfb/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                blob = resp.read()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            fetched.append(token)
        except Exception as exc:  # a dead individual file is recorded, not retried here
            failed.append(f"{token}: {exc!r}"[:120])
    return {
        "status": "OK",
        "n_listed": len(tokens),
        "n_new": len(fetched),
        "new": fetched,
        "failed": failed,
    }


def harvest(root: Path) -> dict[str, object]:
    """Parse every archived release oldest-first and append what changed to the vintage store."""
    raw_dir = root / _RAW_DIR
    files = sorted(raw_dir.glob("*.xls*")) if raw_dir.is_dir() else []
    results: list[dict[str, object]] = []
    dated: list[tuple[str, Path]] = []
    for path in files:  # attrition-visible: every file present lands in exactly one bucket (L1.60)
        try:
            dated.append((publication_date(path.stem), path))
        except RfbPanelError as exc:
            results.append({"file": path.name, "status": "REFUSED", "reason": str(exc)[:200]})

    n_recorded = 0
    for vintage, path in sorted(dated):
        try:
            parsed = extract(read_xls(path))
        except (XlsError, RfbPanelError) as exc:
            results.append(
                {"file": path.name, "vintage": vintage, "status": "REFUSED",
                 "reason": str(exc)[:200]}
            )
            continue
        if not parsed.conservation.ok:
            results.append(
                {"file": path.name, "vintage": vintage, "status": "REFUSED",
                 "reason": f"conservation {parsed.conservation.status}: "
                           f"{parsed.conservation.detail}"[:200]}
            )
            continue
        n_new = sum(
            record(root, series, obs, vintage=vintage)
            for series, obs in parsed.observations.items()
        )
        n_recorded += n_new
        results.append(
            {"file": path.name, "vintage": vintage, "status": "RECORDED",
             "n_periods": parsed.n_periods, "n_new_rows": n_new,
             "n_dropped_rows": parsed.n_dropped_rows}
        )

    refused = [r for r in results if r["status"] == "REFUSED"]
    if not files:
        status = "NO-DATA"
        detail = f"{raw_dir} holds no workbooks -- data/ is untracked, so this box has no archive"
    elif refused:
        status = "REFUSED"
        detail = (f"{len(refused)}/{len(files)} workbook(s) refused -- every archived release "
                  f"parses clean, so a refusal is a regression, not weather")
    else:
        status = "OK"
        detail = f"{len(files)} release(s), {n_recorded} new revision row(s) appended"
    return {
        "status": status,
        "detail": detail,
        "n_files": len(files),
        "n_refused": len(refused),
        "n_new_rows": n_recorded,
        "releases": results,
        "store": summarise(root, f"{SERIES_PREFIX}_TOTAL_GERAL"),
    }


def main() -> int:
    guard()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=_ROOT)
    ap.add_argument("--no-fetch", action="store_true",
                    help="skip the live-listing check; backfill from the local archive only")
    args = ap.parse_args()

    raw_dir = args.root / _RAW_DIR
    live: dict[str, object] = {"status": "SKIPPED", "n_new": 0}
    if not args.no_fetch:
        live = fetch_new_releases(raw_dir)

    report = harvest(args.root)
    report["live_fetch"] = live
    report["generated_at"] = datetime.now(UTC).isoformat()
    out = args.root / _REPORT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")

    print(f"rfb-vintages: {report['status']} -- {report['detail']} "
          f"(live fetch: {live['status']}, {live.get('n_new', 0)} new)")
    return 2 if report["status"] == "REFUSED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
