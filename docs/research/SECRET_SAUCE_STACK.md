# Secret-sauce stack: status per item, and two design notes (2026-11-11)

This covers the BACKLOG row of 2026-09-30 (Asia thread). That row asked for an app-ranking archive, JP transcripts and patents, plus four 2026 items: a first-party dataset, agentic procurement, ALFRED and self-repairing scrapers. Each item below is either RUNNING (file:line, clock, artifact), BUILT IN A PR (named), FAIL-CLOSED (with its reason) or DESIGN ONLY (this note).

| Item | State | Where | Clock -> artifact |
|---|---|---|---|
| App-ranking archive | RUNNING | `libs/data/free_stack.py:534` `fetch_app_rank_apple`. Apple marketing RSS, 10 countries x free/paid, daily snapshot, never backfilled | `hourly_cycle.py:5148` leg `free_stack_hunt` -> `reports/FREE_STACK_YIELD.json`; cells via `free_stack_proposer` (`:5153`) -> `data/intelligence/free_stack_proposer/` |
| JP transcripts | RUNNING | `libs/data/free_stack.py:854` `fetch_jp_ir`. Declared IR pages, transcript/Q&A tone delta per company | same leg and artifact |
| JP patents | FAIL-CLOSED | `libs/data/free_stack.py:975`. J-PlatPat has no API, and JPO bulk data needs an application. The fetcher reads only a bulk file dropped into `data/free_stack/inbox/jp_patents/` | same leg; status names the missing file |
| US/EP patents | BUILT, IDLE UNTIL A FREE KEY EXISTS (NEEDS_KEY), PR #1026 -- not done | `desks/mt5/research/patent_filings.py`. Weekly publication counts per CPC sector from EPO OPS and USPTO ODP, mapped to index and commodity CFDs | leg `patent_filings` -> `reports/PATENT_FILINGS.json`; cells -> `data/intelligence/patent_filings/`. Idle: both routes read NEEDS_CREDENTIAL and produce nothing until a free OPS or ODP key exists on the box |
| ALFRED | BUILT, PR #1026 | `desks/mt5/research/alfred_vintages.py` on `fetch_alfred.py`, whose key path now matches the box (`data/secrets/fred.json`) | leg `alfred_vintages` -> `reports/ALFRED_VINTAGES.json`; lake `alfred_<sid>.parquet`; cells -> `data/intelligence/alfred_vintages/` |
| Self-repairing scrapers | PARTLY RUNNING + BUILT | Already running: `source_routes` (`hourly_cycle.py:5907`; a 200 with the wrong shape reads MOVED) and `source_fixer` (`:5885`; URL variants and Wayback, written as `url_override`). New: `desks/mt5/research/feed_schema_watch.py` (lake schema drift, and parser drift behind a 200, with repair tickets on which an LLM only proposes a change) | leg `feed_schema_watch` -> `reports/FEED_SCHEMA_WATCH.json`; tickets `data/feed_schema_watch/tickets/` |
| First-party dataset | DESIGN ONLY | below | -- |
| Agentic procurement | DESIGN ONLY | below | -- |

Two known gaps, for whoever picks them up next:

- `libs/data/free_stack.py:70`: the free-stack UA starts with a Chrome browser string. The two newer organs use `libs/data/robots_gate.honest_ua`. The free stack should move to the same gate and UA. That change touches 15 fetchers, so it is its own PR.
- The status of the app-ranking and JP-transcript feeds on the box is not measured from the build container. `FREE_STACK_YIELD.json` is box-only. Read `per_source.app_rank_apple` and `per_source.jp_ir_transcripts` there before calling them yielding.

## Design: the first-party dataset

**What it is.** A versioned, point-in-time dataset of everything only this desk observes. QUANT_CONSTITUTION §18 lists it: quotes, ticks and spreads as the terminal saw them, order attempts, fills, rejects, latency, slippage, swaps, stale periods, non-fired setups, blocked decisions and prediction errors. No vendor can sell it, because nobody else holds this account's view of the venue. The pieces already exist but are scattered:

- `data/tape/`
- `data/fill_corpus.jsonl`
- the shadow ledgers
- `data/compute_ledger.jsonl`
- the gateway's pass state

**Build, when it is built.**

1. Publish a catalogue file, `data/first_party/CATALOGUE.json`. It has one row per source stream, with:
   - its writer and schema hash (`libs/data/pit_certificate.schema_hash`)
   - its PIT stamp fields
   - its retention, and whether it can be regenerated (almost never: a missed tick is gone)
2. Make a daily snapshot organ. It freezes the previous UTC day of every stream into `data/first_party/<yyyy-mm-dd>/` as parquet, records the schema and payload hashes, and refuses to overwrite a sealed day.
3. Expose a reader, `libs/data/first_party.read(stream, as_of)`. It answers only from sealed days, so research never reads a stream that is still being written.
4. Point `feed_schema_watch` at the catalogue, so a drift in a first-party stream opens a ticket the same way a lake file does.

**Why not now.** Backup and restore of the existing streams is still open on the box (MoatBackup and RestoreDrill tasks are absent, and the alpha registry and shadow ledgers are not backed up). A dataset that cannot be restored is not yet an asset, so backup comes first.

## Design: agentic procurement

**What it is.** An agent that finds a data source the desk lacks and checks its terms. When the source is free and permitted, the agent prepares everything needed to start ingesting. When it is paid, the agent writes the case for buying it.

**Rule.** The agent never accepts terms, creates an account, enters payment details or uses a credential on its own. It also never scrapes anything that sits behind a login.

**Build, when it is built.**

1. Feed it the existing demand side:
   - `data_axis_miner` and `paid_substitute_engine` (the missing axes, and what a paid feed would substitute for)
   - `index_discovery` (candidate addresses)
   - `data_scout` (cost and integration effort)
2. For each candidate, the agent:
   - reads the source's licence and robots files through `libs/data/robots_gate`
   - classifies them with `libs/research/access_classifier.py`
   - writes a PROCUREMENT TICKET with: source, licence quote, `machine_use_allowed`, expected axis, and expected information value from the axis registry's prior
3. A free source whose terms allow machine use becomes a draft roster row (`free_stack_sources.json` or `asia_sources.json`) inside a PR, never a direct write.
4. A paid source gets a one-page buy case for the principal: price, what it replaces, and the measured value of the axis it fills.
5. Credentials stay the principal's act. A ticket waiting on a key says NEEDS_CREDENTIAL with the file it would read. The patent routes already use this convention.

**Why not now.** No free data source exists for this item. The value of the agent depends on axis-value estimates that are mostly UNMEASURED (no axis has a forward certificate yet). Until a few axes have measured value, a buy case would be built on a prior, not on evidence.
