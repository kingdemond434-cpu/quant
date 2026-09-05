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
        if spec.get("params") is None:
            # REFUSED RATHER THAN SEALED. A certificate with no parameterization is unrunnable
            # for ever: enrolment cannot guess it, the allocator cannot fund it, and it spends the
            # rest of its life inflating the survivor count while reaching no capital. Publishing
            # it is strictly worse than not publishing it, because the desk then believes it holds
            # an edge it cannot express. Named on stderr so the sweep that produced it can be
            # fixed, rather than dropped in silence.
            print(f"REFUSED-UNRUNNABLE: {row.get('id')} passed all ten gates but its sweep "
                  f"recorded no `params`; sealing it would mint a certificate nothing can run",
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
