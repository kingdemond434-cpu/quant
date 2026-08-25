# Claude instructions (binding)

Read `docs/LAWS.md` + `docs/RESEARCH.md` first (consolidated 2026-08-25) — binding on every
session. Then AGENTS.md for the standing wiring (supervisor, holds, queue,
hourly cadence, universal gate as the only promotion path). Absence is never
permission; everything fails closed.

## Survivors ledger — ALWAYS CHECK AT SESSION START

- `reports/UNIVERSAL_SURVIVORS.json` — every universal 10-gate pass, counted
  in the `n` field, each survivor keyed by `<hunt>.<cell>`.
- `reports/SURVIVORS_LEDGER.json` — append-only human/agent-visible ledger of
  every claim and its status (CLAIMED → UNIVERSAL → SIGNAL_GATE → ALLOCATED →
  DEPLOYED / REJECTED), written by the desk on every transition.
- Count them and act: a new survivor in the ledger is a pipeline claim that must
  proceed through the universal gate → signal gate → allocation → deployment.
  Never let a survivor sit un-actioned across a session.