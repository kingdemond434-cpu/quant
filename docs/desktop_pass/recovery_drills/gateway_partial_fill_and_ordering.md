# Gateway: partial fills and out-of-order broker reads (MONEY PATH, desktop pass)

Owner: the Live control room thread. Target: the desktop "Growth allocator overhaul" session.
Base: LIVE 2d61e69a1. PR #197 grades both of these as FAIL rows (`partial_fill`, `out_of_order`) in `reports/RECOVERY_DRILLS.json` until this spec lands.

## 1. Partial fill: the scalp lane forgets a position it actually holds

**Where:** `desks/mt5/mt5desk/gateway.py`, scalp executor, around line 3800:

```python
rc = res.retcode if res else None
...
if rc not in (10008, 10009):
    continue
```

**The defect:** retcode 10010 (`DONE_PARTIAL`) means the broker filled part of the order and the position exists. The scalp lane treats that as a failure and skips the basket record. As a result:
- the position runs without the lane's stop management and time exit;
- the next pass can open a second entry on top of it.

`order_door.validate` already labels the fill `partial`. Nothing acts on that label.

**The fix:**
1. Accept `rc in (10008, 10009, 10010)` (use `order_door.SUCCESS`).
2. Record the basket with `filled = float(res.volume or 0)` instead of `per`.
3. When `filled < per`, log `SCALP-EXEC PARTIAL filled/asked` and write `residual = per - filled` on the basket row.
4. Never re-send the residual in the same pass. The next pass re-decides size against the position the broker reports.

**Close path:** `close_all` / `flatten`, around line 1693. After `order_send`, when `rc == 10010` or `res.volume < p.volume`:
- re-read `positions_get(ticket=p.ticket)`;
- log `CLOSE PARTIAL ticket residual=...`;
- set `st.setdefault("close_residual", {})[str(p.ticket)] = residual`.

The next pass's close loop already picks the position up again. Do not loop a resend inside the pass. That would be a blind resubmission of an uncertain outcome.

## 2. Out-of-order: a positions read older than the newest deal is taken at face value

**Where:** `reconcile(st)`, around line 1951. Today it stores `positions_get` and `orders_get` with no notion of when the terminal last saw them. `record_trades` already dedupes deals by ticket, so a late deal is never lost; the ledger side is safe. The open-book side is not safe: a terminal that lags can report a position as still open after its closing deal has arrived (or the reverse). The pass then sizes against a book that no longer exists.

**The fix (read only, no new sends):**
1. In `reconcile`, store `st["position_snapshot_msc"] = max(p.time_update_msc for p in pos)` (0 when there are no positions).
2. In `record_trades`, store `st["last_deal_msc"] = max(d.time_msc)` over the deals read, and `st["closed_position_ids"]` (the `position_id` of each DEAL_ENTRY_OUT read this pass).
3. The book is inconsistent when a ticket in `st["position"]` is in `closed_position_ids`, or when an IN deal's `position_id` is absent from `st["position"]` and `positions_get(ticket=...)` confirms it is open. In that case:
   - set `st["book_inconsistent"] = {"why": ..., "at": now()}`;
   - re-read once;
   - if the book is still inconsistent, refuse new risk for this pass. Pass `{"verdict": "UNMEASURED", "why": "book_inconsistent"}` into `new_risk_gate` (see `gateway_new_risk_gate.md`) instead of the reconcile verdict.

   Managing open positions continues.

## Proof

Add three faults to `libs/tiers/gateway_drill.py` (non-money-path; the Live control room thread can land them once the gateway side exists):
- `partial_fill`: `order_send` returns `retcode=10010, volume=asked/2`. Pass when the basket holds the filled volume and no second entry goes out.
- `close_partial`: the close returns 10010 with a residual. Pass when the residual is recorded and the close is not resent in the same pass.
- `stale_positions`: `history_deals_get` returns an OUT deal for a ticket that `positions_get` still lists. Pass when new risk is refused for the pass.

Done when `gateway_drill.campaign()['breaches'] == []` on the box and the two scorecard rows read PASS.
