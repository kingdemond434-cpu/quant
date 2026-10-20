"""Legacy entry point. The fetcher is `mt5desk/fetch_tff.py`; this copy had drifted from it
(substring market matching, non-TFF metals and DXY slugs) and is now a thin alias."""
from __future__ import annotations

from mt5desk.fetch_tff import TARGETS, load_year, main, pick  # noqa: F401

if __name__ == "__main__":
    main()
