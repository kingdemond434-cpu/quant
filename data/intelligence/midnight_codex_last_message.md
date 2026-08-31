Implemented and committed `12dfff8c`:

- [`scripts/run_midnight_completion.py`](/home/quant/quant-platform/scripts/run_midnight_completion.py) now labels unchanged, resource-fenced catch-up debt as `DEFERRED_RESOURCE`, not a hard pipeline failure. It remains incomplete and owed.
- Added regression coverage in [`test_midnight_completion.py`](/home/quant/quant-platform/tests/scripts/test_midnight_completion.py).

Proof: 4 targeted tests passed; syntax compilation and constitution-core verification passed.

Runtime evidence: remote workers are live—edge search PID 3180 (~4.1 GB), gauntlet PID 7628, orthogonal sweep PID 7752—with only 64 MB free. Serial admission is correct; competing starts would risk the MT5 terminal.

Checkpoint recorded at epoch 121. Blockers remain explicit: 19,917 deferred cells await the live worker, and the authority ratchet reports queue/cohort count regressions; its repair actuator is rate-limited, so shared artifacts were not overwritten.