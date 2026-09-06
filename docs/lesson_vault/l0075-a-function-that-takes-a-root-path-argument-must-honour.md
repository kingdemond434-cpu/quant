---
id: L0075
cost: blind
tags: ["testing"]
---

# L0075

A function that takes a root/path argument must honour it for EVERY output it writes. If it routes one write through the parameter and another through a module global, callers redirect half the organ and silently corrupt the live store with the other half -- and isolation that depends on each test remembering to monkeypatch the global is not isolation.

## Evidence

R0254: run_calibration_probe.pose(root) wrote its questions file under root and logged the matching forecast through forecast_calibration._LOG. A parsing test passing tmp_path (correctly, it asserts parsing not storage) injected one fabricated row per run into the live L1.29 store: 69 rows, and ALL 44 forecasts holding check_calibration OVERDUE on 2026-08-05 were that fixture, zero were real. Fixed ce5d37a.

## Tags

#testing

## Related

- [[l0003-on-a-two-venue-hedge-measure-both-legs-the-same-way-ac]]
- [[l0007-a-verdict-about-the-host-is-not-a-verdict-about-the-de]]
- [[l0015-walk-the-import-graph-a-one-hop-grep-proves-a-name-exi]]
- [[l0029-two-pids-with-matching-args-are-not-two-processes-unti]]
- [[l0037-garman-klass-is-provably-non-negative-on-any-real-bar-]]
- [[l0039-a-module-with-passing-tests-and-no-production-importer]]
- [[l0040-a-required-argument-nobody-computes-is-a-dead-code-pat]]
- [[l0049-a-checklist-that-fires-on-recall-is-not-a-control-if-a]]
