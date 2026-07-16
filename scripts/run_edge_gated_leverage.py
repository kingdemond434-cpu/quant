"""DEPRECATED -- superseded by the dynamic leverage controller.

The old fixed-floor/cap edge gate (floor 3x, cap 6x) used arbitrary constant bounds. The
constitution now needs leverage as a continuously optimized control variable with an ENDOGENOUS
ceiling (diminishing-returns argmax of E[log] AND a risk-of-ruin cap), computed in run_leverage_opt
via `libs/risk/dynamic_leverage`. This shim delegates so any legacy caller still gets the dynamic
value and writes the same `data/leverage_target.json` (back-compatible `gated_leverage` key kept).

    python scripts/run_edge_gated_leverage.py   # -> run_leverage_opt
"""

from __future__ import annotations

try:                                          # works whether run as script or imported as package
    from run_leverage_opt import main as _dynamic_main
except ImportError:
    from scripts.run_leverage_opt import main as _dynamic_main


def main() -> None:
    _dynamic_main()


if __name__ == "__main__":
    main()
