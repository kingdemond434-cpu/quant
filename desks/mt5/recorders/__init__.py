"""The desk's proprietary capture layer: the Fusion tick tape and the vol-term archive.

WHY THIS PACKAGE EXISTS, in one paragraph. Every other asset this desk holds is reproducible.
The code can be rewritten, the bars can be re-downloaded, the certificates can be re-earned on
the same history. Recorded time cannot. An hour of Fusion quotes that nobody wrote down is gone
at any price, from any vendor, forever -- there is no archive of one retail CFD broker's quote
stream, and there never will be one for a date in the past. That asymmetry is the whole argument
for this package: starting capture sooner strictly dominates starting it better, because the
inventory of unrecorded hours only ever grows while the code is being improved.

WHAT IS HERE

    tick_source.py     the thin capture interface, its MetaTrader5 implementation and a
                       deterministic fake -- so everything above it is testable off Windows
    tape_store.py      append-only, content-addressed, crash-safe storage; the gap ledger that
                       records what was MISSED as a fact rather than as an absence; and the
                       compaction that folds a finished day's containers without touching a tick
    tick_recorder.py   the continuous loop: universe from the live symbol list, cursors,
                       terminal restarts, weekend gaps, symbol-list changes, disk floor
    tick_integrity.py  the proof: per symbol per day, does the tape say what it claims to say
    tape_features.py   what the tape buys that public bar data cannot -- executable spread,
                       quote intensity, microprice, order-flow imbalance, the true intrabar path
                       and realised/jump variance on the M1..D1 clock, and a cost surface
                       measured rather than assumed
    vol_archive.py     the second forward-only asset: an implied-vol / term-structure archive
                       on MT5-tradeable ground, accumulated one observation per cycle

THE ONE THING MEASUREMENT CHANGED ABOUT THE DESIGN. Writing a segment per 60-second cycle is what
makes a crash cost at most one cycle, and it is also 1,440 parquet containers per symbol per day
at a measured ~3 KB of footer each -- 4.3 MB of container around the ticks, 1.26 GB/day across
this universe, which no argument about the value of tick data would have survived. The fix was
not to record less: it was to keep the 60-second beat for safety and fold the containers once a
day has stopped receiving, which is lossless and 25x smaller. `tape_store`'s retention section
carries the whole measurement, including the estimate it overturned.

NOTHING HERE DECIDES ANYTHING. No module in this package can move a position, change a size,
mint a certificate or condition capital. It records, it measures, and it publishes artifacts the
existing machinery reads. That separation is deliberate: a recorder that can affect the money
path is a recorder that can lose money, and its only job is to never miss.
"""
