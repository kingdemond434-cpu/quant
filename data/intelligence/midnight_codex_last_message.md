Implemented and checkpointed.

- Commit `4df2cbc5` updates [build_mt5_midnight_state.py](/home/quant/quant-platform/scripts/build_mt5_midnight_state.py) to measure canonical gauntlet→survivor pipeline freshness, not the dormant legacy `QUEUED` loop. Added regression coverage.
- Ran zero-capital daily chain: shadow/promoter/markout completed; markout refreshed to `2026-08-28T23:03:00Z`, correctly remains UNMEASURED with 0 matched fills.
- Fresh midnight state now exits `0`, with no defects; 23 survivors, 50 shadow sleeves, 199 observations.
- Tests: `13 passed` focused state-builder/daily-cycle suite.
- Controller checkpoint written for epoch 43.

Blocked dependencies: this host lacks `MetaTrader5` (bar refresh) and `export_aurum_findings`; both are explicit daily-cycle failures. Gateway remains paused; no capital, authority, or rail changed.