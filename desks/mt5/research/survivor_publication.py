"""Atomically publish canonical QQUANT passes to the desk survivor ledgers."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gate_policy import all_ten_pass, is_exact_policy


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        with suppress(FileNotFoundError):
            os.unlink(name)


def unrunnable_reason(row: dict[str, Any]) -> str | None:
    """Why this certificate could never be enrolled, or None if it can.

    ONE JUDGE, BECAUSE THERE ARE FOUR PENS. Certificates reach UNIVERSAL_SURVIVORS.json from
    `publish_qquant_survivors` below, from `scripts/external_gauntlet.py`, from
    `scripts/full_pipeline.py` and from `side_channels/full_pipeline.py`, and on 2026-09-06 all
    four disagreed about what a publishable certificate is:

        publish_qquant_survivors      refuses `params is None`          (correct)
        scripts/external_gauntlet     writes the row with NO shadow_spec at all when the
                                      selector is unknown -- it prints NO-SPEC and stores it anyway
        scripts/full_pipeline         writes a shadow_spec with no `params` KEY, plus a hardcoded
                                      selector "asia" and family "session_range_breakout"
        side_channels/full_pipeline   writes params, guesses the selector, defaults to "asia"

    So the fence that already existed protected one of four doors, and the other three minted the
    zombies: 18 certificates that passed all ten gates, are counted in every survivor total,
    inflate the desk's belief about its own edge, and can never be enrolled, funded or falsified.
    Fixing the three publishers individually leaves a fourth to be written next month. This is the
    predicate all of them ask, so a new publisher inherits the refusal by calling one function.

    WHAT IS AND IS NOT A DEFECT:

        no shadow_spec            REFUSED -- nothing to enrol from
        shadow_spec not a mapping REFUSED -- same, with a clearer cause
        params absent / None      REFUSED -- the parameterisation that passed was never recorded,
                                  and guessing one enrols a DIFFERENT strategy than the one
                                  certified, which is the two-stage law's exact prohibition
        params == {}              ALLOWED -- the complete parameterisation "family defaults",
                                  byte-exactly what the gauntlet executed. Excluding it has
                                  already stranded overnight_gap_decay certificates twice
                                  (2026-08-27) and over-reported unrunnables as 13 against 6.
        symbol / family missing   REFUSED -- an identity with no instrument cannot be run

    Returns prose, not a bool, because every caller prints it: a refusal nobody can read is how
    the NO-SPEC line above came to be ignored for weeks while the rows kept accumulating.
    """
    spec = row.get("shadow_spec")
    if spec is None:
        return ("carries no `shadow_spec` at all, so there is nothing to enrol from -- the "
                "publisher sealed a gate verdict without the specification that makes it runnable")
    if not isinstance(spec, dict):
        return f"`shadow_spec` is {type(spec).__name__}, not a mapping, so it names no strategy"
    if "params" not in spec or spec.get("params") is None:
        return ("`shadow_spec.params` is absent -- the parameterisation that passed the gauntlet "
                "was never recorded, and enrolling a guessed one would forward-test a DIFFERENT "
                "strategy than the one certified")
    if not isinstance(spec.get("params"), dict):
        return f"`shadow_spec.params` is {type(spec['params']).__name__}, not a mapping"
    if not str(spec.get("symbol") or "").strip():
        return "`shadow_spec.symbol` is empty, so the certificate names no instrument to trade"
    if not str(spec.get("family") or "").strip():
        return "`shadow_spec.family` is empty, so nothing can resolve a constructor for it"
    return None


def hunt_name(raw: object) -> str:
    """The hunt component of a survivor key, guaranteed to contain no dot.

    A qquant survivor key is `qquant.<hunt>.<cell>` and EVERY downstream consumer splits it on
    dots -- forward_reconcile says so in its own docstring. So a dot inside the hunt component
    does not produce a slightly-wrong label, it shifts every field after it by one.

    Measured 2026-09-01: one live certificate is keyed
    `qquant.hunt16.json.AUDNZD dav_range_filter_adx SHORT afternoon NORMAL_DAY` -- the producer
    passed the FILE NAME rather than the hunt name. Split on dots, its "symbol" reads `hunt16`
    and its family reads `json`, which is how a filename ended up in the symbol column of the
    currency-exposure report and why the row matches no authorized run and can never enrol.

    Stripping is not enough on its own: any dot breaks the contract, so any that survive become
    underscores. A mangled-but-parseable name is recoverable; a shifted key is not.
    """
    name = str(raw or "").strip()
    name = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]   # never a path
    if name.endswith(".json"):
        name = name[: -len(".json")]
    return name.replace(".", "_")


def _shadow_spec(row: dict[str, Any]) -> dict[str, Any] | None:
    """The runnable identity of a certified cell -- INCLUDING the parameters that passed.

    THE PARAMS WERE BEING DELETED AT PUBLICATION, and that is how a certificate becomes a zombie:
    it passes all ten gates, gets sealed into the canon, is counted in every survivor total, and
    can never be enrolled or funded because nothing knows how to run it. `shadow_admission` refuses
    it -- correctly, since guessing a parameterization is running a DIFFERENT strategy than the one
    that was certified -- and the refusal reads like an admission bug rather than a publication one.

    This function used to rebuild the spec from the cell-ID string alone, and the ID does not carry
    parameters. The sweep had them all along: `full_pipeline` writes `"params": c["params"]` onto
    every verdict row, three lines from where the gates are scored. They were dropped one step
    later, here.

    Measured on the sealed canon 2026-09-05: 6 of 66 certificates carry `params: None` and are
    refused at enrolment. `session_range_breakout` proves the params are load-bearing rather than
    decorative -- 15 of its certificates carry parameters and 5 do not, same family, so the missing
    five are a lost parameterization and not a parameterless strategy.

    `{}` AND `None` ARE DIFFERENT ANSWERS. An empty mapping is a family that genuinely takes no
    parameters (`overnight_gap_decay`, which enrols and funds fine); `None` is a parameterization
    that was never recorded. Only the second is a defect, and `publish_qquant_survivors` refuses it
    rather than sealing another zombie.
    """
    parts = str(row.get("id") or "").split()
    if len(parts) != 5:
        return None
    symbol, family, side, selector, condition = parts
    params = row.get("params")
    return {
        "symbol": symbol,
        "family": family,
        "side": side.upper(),
        "selector": selector,
        "condition": None if condition.upper() in {"NONE", "ALL", "UNCONDITIONED"}
        else condition,
        "is_universe": True,
        "hunt": row.get("hunt"),
        "params": params if isinstance(params, dict) else None,
    }


def publish_qquant_survivors(report: dict[str, Any], reports: Path) -> dict[str, Any]:
    """Merge only exact ten-gate passes; never erase survivors from other hunts."""
    if not is_exact_policy(report.get("gate_policy")):
        raise ValueError("QQUANT report does not carry the exact immutable gate policy")
    now = datetime.now(UTC).isoformat()
    path = reports / "UNIVERSAL_SURVIVORS.json"
    current = _read(path)
    survivors = current.get("survivors")
    survivors = dict(survivors) if isinstance(survivors, dict) else {}
    published: list[str] = []
    for row in report.get("verdicts", []):
        if not isinstance(row, dict) or row.get("passed") is not True:
            continue
        if not all_ten_pass(row.get("stages")):
            continue
        spec = _shadow_spec(row)
        if spec is None:
            continue
        # REFUSED RATHER THAN SEALED. A certificate with no parameterization is unrunnable for
        # ever: enrolment cannot guess it, the allocator cannot fund it, and it spends the rest of
        # its life inflating the survivor count while reaching no capital. Publishing it is
        # strictly worse than not publishing it, because the desk then believes it holds an edge
        # it cannot express. Named on stderr so the sweep that produced it can be fixed.
        #
        # THIS USED TO ASK ITS OWN QUESTION (`spec.get("params") is None`) and it was the only
        # publisher that asked at all. Delegated to the shared judge so all four pens refuse the
        # same shapes -- a second spelling of the same rule is how the other three came to have a
        # different one, or none.
        why = unrunnable_reason({"shadow_spec": spec})
        if why:
            print(f"REFUSED-UNRUNNABLE: {row.get('id')} passed all ten gates but {why}",
                  file=sys.stderr)
            continue
        hunt = hunt_name(row.get("hunt"))
        key = f"qquant.{hunt}.{row['id']}"
        survivors[key] = {
            "hunt": hunt,
            "cell": row["id"],
            "sym": spec["symbol"],
            "days": row.get("days"),
            "gates": row["stages"],
            "shadow_spec": spec,
            "gated_at": report.get("swept_at") or now,
            "status": "UNIVERSAL",
        }
        published.append(key)
    payload = {
        "n": len(survivors),
        "survivors": survivors,
        "gate_policy": report["gate_policy"],
        "note": "Exact original ten-gate passes only; shadow remains zero-order authority.",
        "swept_at": report.get("swept_at") or now,
    }
    _atomic_json(path, payload)

    ledger_path = reports / "SURVIVORS_LEDGER.json"
    ledger_doc = _read(ledger_path)
    claims = ledger_doc.get("claims")
    claims = dict(claims) if isinstance(claims, dict) else {}
    for key in published:
        claims[key] = {**survivors[key], "updated_at": now}
    _atomic_json(ledger_path, {"n": len(claims), "claims": claims})
    return {"published": published, "survivor_count": len(survivors)}
