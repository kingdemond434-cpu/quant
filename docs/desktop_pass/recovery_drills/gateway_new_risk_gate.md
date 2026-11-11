# Gateway: reconcile and connectivity before new exposure (money path, desktop pass)

From the "Live control room" thread, recovery drills, 2026-10-06. The cloud classifier refused the
edit to `desks/mt5/mt5desk/gateway.py` ("Production Deploy"). That is expected for the money path.
This spec is for the desktop "Growth allocator overhaul" session.

## Defect (measured)
The gateway drill (`libs/tiers/gateway_drill.py`, branch `claude/recovery-drills`) runs the real
`gateway.py` against a faulty MT5 double in a sandbox. On live 2d61e69a1 it finds two breaches:
- `terminal_disconnected`: `terminal_info().connected` is False, `connect()` still returns True,
  and the pass may open new risk.
- `reconcile_unreadable`: `positions_get` raises, so `restart_reconcile` returns
  verdict UNMEASURED. `gateway.main` then goes on to place new orders on a book it never read.
  If `restart_reconcile` itself raises, `main` only logs "the lanes' own venue checks still stand".

## Fix (no size, heat, floor or allocator change; management of open positions is untouched)
1. Add, right after `NEW_RISK_OK: bool = False`:

```python
def new_risk_gate(release_ok: bool, release_why: str, reconcile: dict | None,
                  terminal: object) -> tuple[bool, str]:
    """May this pass open NEW exposure? Management of open positions never asks.
    Reconcile before exposure: an unread book, an unsettled in-doubt send or a terminal that is
    running but disconnected from the broker refuses new risk for the pass, exactly as a release
    mismatch does. A missing reconcile report is a refusal, never a licence."""
    if not release_ok:
        return False, f"release identity: {release_why}"
    if terminal is None or not bool(getattr(terminal, "connected", False)):
        return False, "broker terminal is not connected"
    rr = reconcile if isinstance(reconcile, dict) else {}
    if rr.get("verdict") != "OK":
        return False, (f"restart reconcile {rr.get('verdict') or 'MISSING'}: "
                       f"{rr.get('why') or 'broker state not read this pass'}")
    unread = [k.get("key") for k in rr.get("in_doubt") or []
              if isinstance(k, dict) and k.get("unreadable")]
    if unread:
        return False, f"{len(unread)} in-doubt send(s) could not be settled at the venue"
    return True, release_why
```

2. In `main()`, in the `except` around `_door.restart_reconcile(...)`, record the failure:

```python
    except Exception as exc:
        st["restart_reconcile"] = {"verdict": "FAILED",
                                   "why": f"{type(exc).__name__}: {exc}"[:200]}
        log(f"RESTART RECONCILE FAILED ({type(exc).__name__}: {exc}); managing open positions "
            f"only this pass")
```

3. Replace `NEW_RISK_OK, _ident_why = release_gate()` and its log line with:

```python
    try:
        _terminal = mt5.terminal_info()
    except Exception:
        _terminal = None
    NEW_RISK_OK, _ident_why = new_risk_gate(*release_gate(), st.get("restart_reconcile"),
                                            _terminal)
    if not NEW_RISK_OK:
        log(f"NEW RISK REFUSED: {_ident_why} -- managing open positions only")
```

## Proof after applying
`python -c "from libs.tiers import gateway_drill as g; print(g.campaign()['breaches'])"` must print
`[]`: the two faults are refused, and `healthy` is not refused. Then run `desks/mt5/tests/test_order_door_chaos.py`,
`desks/mt5/tests/test_tier_s_gateway_drill.py`, `./ops/gates.sh` and `--laws-only`.
Rule 1 note: this refuses only new entries made on a broker state the desk has not read. It sizes no
position smaller, and a pass with a clean reconcile is unchanged.
