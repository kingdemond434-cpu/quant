"""Gateway loop: run every 60s, shadow mode until armed by the human."""

from __future__ import annotations

import time

from mt5desk import gateway


def main() -> None:
    while True:
        try:
            gateway.main()
        except Exception as e:  # noqa: BLE001 - loop must never die
            gateway.log(f"LOOP ERROR: {e!r}")
        time.sleep(60)


if __name__ == "__main__":
    main()