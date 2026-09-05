"""Daily execution intelligence: refit the fill/slip surface, measure netting. Cycle entry point."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for p in (str(_DESK), str(_DESK / "research"), str(_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from mt5desk import execution_registry, fill_surface, netting  # noqa: E402


def _book_report() -> dict:
    """The theoretical-position ledger's savings, when the gateway has written one.

    The intent-based report above counts opposing INTENTS; the ledger counts opposing
    theoretical POSITIONS and prices the spread the netting saved against each symbol's own
    spread. An absent ledger is reported as such -- a box that has not run the wired gateway
    has no netting evidence yet, which is a different fact from "nothing to net".
    """
    try:
        book = netting.TheoreticalBook()
        if not book.symbols():
            return {"verdict": "UNMEASURED", "why": "no theoretical positions recorded yet"}
        return netting.savings_report(book, write=True)
    except Exception as exc:                                    # noqa: BLE001
        return {"verdict": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}


def run() -> dict:
    fs = fill_surface.run(write=True)
    nt = netting.savings_report(write=True)
    book = _book_report()
    try:
        board = execution_registry.scoreboard()
    except Exception as exc:                                    # noqa: BLE001
        board = {"status": "UNMEASURED", "why": f"{type(exc).__name__}: {exc}"}
    return {"fill_surface": fs.get("note"), "fills": fs.get("n_fills"),
            "netting": nt.get("verdict"), "opposing_share": nt.get("opposing_share"),
            "netting_book": book.get("verdict"), "netting_book_why": book.get("why"),
            "algo_scoreboard": board}


def main() -> int:
    argparse.ArgumentParser().parse_args()
    d = run()
    print(f"EXECUTION INTELLIGENCE  surface: {d['fill_surface']} ({d['fills']} fills); "
          f"netting: {d['netting']} opposing_share={d['opposing_share']}; "
          f"book: {d['netting_book']}; algos: {d['algo_scoreboard']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
