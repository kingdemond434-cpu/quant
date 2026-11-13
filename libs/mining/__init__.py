"""MT5_GLOBAL_MINING_V1: the global mining spine.

    fetch -> PIT store -> extract -> dedup -> compile -> preregister -> gauntlet

`sources.yaml` is the roster, `acquirer` fetches with durable cursors into `pit_store`,
`extractor` turns records into typed cells, `dedup` folds them by MECHANISM (never by surface
text or language), `compiler` maps a cell onto a registered gauntlet family, `prereg` seals the
contract before anything is judged, and `rejection` keeps the ledger whose counts are the
headline metric. `desks/mt5/research/mining_supervisor.py` runs the loop as one leg of the
existing hourly cycle; there is no scheduler here.

Nothing in this package judges, sizes or trades. The sealed gauntlet is the only evaluator and
is read, never modified.
"""
