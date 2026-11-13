"""The global mining supervisor's verdict side: joining the gauntlet's verdicts onto mined
cells, attributing judged docket cells to sources, and each source's ACTIVE/COLD status.

Split out of `mining_supervisor.py` for size only; `Pipeline` inherits these methods.
"""
from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

_DESK = Path(__file__).resolve().parents[1]
_ROOT = _DESK.parent.parent
for _p in (str(_ROOT), str(_DESK)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from libs.mining import acquirer as acq  # noqa: E402
from libs.mining import compiler, prereg, rejection  # noqa: E402
from libs.mining.pit_store import iso, utcnow  # noqa: E402
from libs.mining.registry import Cell  # noqa: E402
from research.mining_supervisor_wiring import (  # noqa: E402
    SOURCE,
    _WAYBACK,
    _scout_seats,
    producer_of,
    _INDEX_PAGE,
    _site,
    ACTIVE_WINDOW,
    DEEPENING_CAP,
)


class VerdictJoin:
    """Methods of `mining_supervisor.Pipeline`; never instantiated alone."""

    # --------------------------------------------------------------------- 4. join
    def join_verdicts(self, now: datetime | None = None) -> int:
        try:
            size = self.gate_ledger.stat().st_size
        except OSError:
            return 0
        off = int(self.cells.kv_get("gate_ledger_offset", "0") or 0)
        if off > size:
            off = 0                                       # ledger rotated
        joined = 0
        with self.gate_ledger.open("rb") as fh:
            fh.seek(off)
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break                                 # a row still being written
                off += len(raw)
                try:
                    v = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if not isinstance(v, dict):
                    continue
                for cell, axis in self.cells.by_alias(str(v.get("cell") or "")):
                    if cell.status in ("EVALUATING", "EVALUATED"):
                        joined += self._apply_verdict(cell, v, axis=axis, now=now)
        self.cells.kv_set("gate_ledger_offset", str(off))
        return joined

    # --------------------------------------------------- the one registry: global attribution
    def index_judged(self, now: datetime | None = None) -> int:
        """Every judged docket cell, whoever minted it, into `judged_cells` (own byte offset, so
        the first pass reads the whole ledger once and every later one only what is new)."""
        try:
            size = self.gate_ledger.stat().st_size
        except OSError:
            return 0
        off = int(self.cells.kv_get("judged_offset", "0") or 0)
        off = 0 if off > size else off
        batch: list[tuple[str, str, bool]] = []
        stamp = iso(now or utcnow())
        with self.gate_ledger.open("rb") as fh:
            fh.seek(off)
            for raw in fh:
                if not raw.endswith(b"\n"):
                    break
                off += len(raw)
                try:
                    v = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, ValueError):
                    continue
                if not isinstance(v, dict) or not v.get("cell"):
                    continue
                if rejection.reason_for_verdict(v)[1] == "DEFERRED":
                    continue
                batch.append((str(v["cell"]), str(v.get("at") or stamp), bool(v.get("passed"))))
                if len(batch) >= 20_000:
                    self.cells.record_judged(batch)
                    batch = []
        self.cells.record_judged(batch)
        self.cells.kv_set("judged_offset", str(off))
        return off

    def _url_index(self) -> dict[str, list[tuple[str, str]]]:
        idx: dict[str, list[tuple[str, str]]] = {}
        for s in self.roster:
            for k in s.url_keys or ([s.url_key] if s.url_key else []):
                idx.setdefault(k.partition("/")[0], []).append((k, s.id))
        return idx

    def _seat_index(self) -> dict[str, str]:
        """DECLARED seats only: a docket `source` string a registry row says it answers for.
        No name-alike fallback -- a seat nobody declared is an internal producer, not a source."""
        out: dict[str, str] = {}
        for s in self.roster:
            for seat in s.seats:
                out.setdefault(seat, s.id)
        return out

    @staticmethod
    def attribute_url(url: Any, idx: Mapping[str, list[tuple[str, str]]]) -> str:
        """The ONE registry source whose URL is this URL or its longest proper path prefix.

        A web.archive.org capture is judged as the page it archived. A host-only registry URL is
        a SITE-level source: it takes a page on its host only when it is the host's sole registry
        row (on a shared host it would be a wildcard). A tie at the winning length is ambiguous
        and credits nobody: a wrong credit is worse than none.
        """
        raw = str(url or "")
        m = _WAYBACK.match(raw)
        key = acq.canonical_url(m.group(1) if m else raw)
        if not key:
            return ""
        host = key.partition("/")[0]
        rows = idx.get(host) or []
        best: list[str] = []
        best_len = -1
        page = key.split("?", 1)[0]
        for rk, sid in rows:
            # a listing's query is not its scope, nor is its index page: /x/index.htm scopes /x
            rp = _INDEX_PAGE.sub("", rk.split("?", 1)[0])
            if rk == key:
                hit = len(rk) + 1                         # exact beats any prefix
            elif "/" in rp and (page == rp or page.startswith(rp + "/")):
                hit = len(rp)
            elif "/" not in rk and len(rows) == 1:        # the host's only row, site-level
                hit = 0
            else:
                continue
            if hit > best_len:
                best, best_len = [sid], hit
            elif hit == best_len:
                best.append(sid)
        return best[0] if len(set(best)) == 1 else ""

    def attribute_source(self, row: Mapping[str, Any], idx: Mapping[str, list[tuple[str, str]]],
                         seats: Mapping[str, str]) -> tuple[str, str]:
        """(source id, how): the declared seat, then the row's own URL, then -- only with BOTH
        signals -- a seat named exactly as a registry id whose URL is on the same site."""
        seat = str(row.get("source") or "")
        sid = seats.get(seat, "")
        if sid:
            return sid, "seat"
        url = row.get("source_url") or row.get("url")
        sid = self.attribute_url(url, idx)
        if sid:
            return sid, "url"
        named = self.by_id.get(seat.removeprefix("miner:"))
        if named is not None and _site(url) and _site(url) in {
                _site(k) for k in named.url_keys or [named.url_key]}:
            return named.id, "seat+site"
        return "", ""

    def attributed_evaluations(self, now: datetime | None = None) -> dict[str, Any]:
        """Per registry source: docket cells EVALUATED within ACTIVE_WINDOW.

        Reads the judge's own docket (`external_survivors.json`) and names each row's cell by the
        judge's rule (`frontier_identity.docket_cell`), so a docket cell and its verdict share a
        key by construction. A row is credited through a DECLARED seat or its URL, never a guess;
        what stays unattributed is counted by producer so the gap is visible."""
        t = now or utcnow()
        try:
            rows = json.loads(self.docket.read_text("utf-8"))
        except (OSError, ValueError):
            return {"by_source": {}, "basis": f"UNMEASURED: {self.docket.name} unreadable"}
        if isinstance(rows, dict):
            rows = rows.get("rows") or rows.get("items") or []
        judged = self.cells.judged_since(t - ACTIVE_WINDOW)
        idx, seats = self._url_index(), self._seat_index()
        organ_of = _scout_seats()
        by: dict[str, set[str]] = {}
        producers: dict[str, dict[str, int]] = {}
        funnel: dict[str, dict[str, int]] = {}
        how: dict[str, int] = {}
        unattributed: dict[str, int] = {}
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict) or not r.get("family"):
                continue
            try:
                cid = self.hooks.gauntlet_cell(r)
            except Exception:
                continue
            if cid not in judged:
                continue
            sid, via = self.attribute_source(r, idx, seats)
            organ = producer_of(r.get("source"), organ_of)
            f = funnel.setdefault(organ, {"judged": 0, "credited": 0})
            f["judged"] += 1
            f["credited"] += int(bool(sid))
            if sid:
                pr = producers.setdefault(sid, {})
                pr[organ] = pr.get(organ, 0) + 1
            if not sid:
                p = str(r.get("source") or "?").split(":")
                k = ":".join(p[:2])
                unattributed[k] = unattributed.get(k, 0) + 1
                continue
            by.setdefault(sid, set()).add(cid)
            how[via] = how.get(via, 0) + 1
        top = dict(sorted(unattributed.items(), key=lambda kv: -kv[1])[:25])
        self._producers = producers
        return {"by_source": {k: len(v) for k, v in by.items()}, "credited_by": how,
                # the producing ORGAN's funnel (scout_roster seats), beside the source credit:
                # a source is judged ACTIVE per source; ROI per organ reads this
                "by_producer": dict(sorted(funnel.items())),
                "unattributed_judged_rows": sum(unattributed.values()),
                "unattributed_top_producers": top,
                "basis": f"{self.docket.name} x judged_cells ({len(judged)} judged in window)"}

    def register_cursors(self, now: datetime | None = None) -> int:
        """A durable cursor per canonical source, carrying its registration; fetch state kept."""
        wrote = 0
        for s in self.roster:
            reg = {"canonical_id": s.id, "origin": s.origin, "owner": s.owner,
                   "url_key": s.url_key, "aliases": sorted(s.aliases),
                   "shares_page": sorted(s.shares_page)}
            cur = self.cursors.get(s.id)
            old = {k: v for k, v in (cur.get("registered") or {}).items() if k != "first_seen"}
            if old != reg:
                reg["first_seen"] = (cur.get("registered") or {}).get("first_seen") or iso(
                    now or utcnow())
                self.cursors.save(s.id, {**cur, "registered": reg})
                wrote += 1
        return wrote

    def _apply_verdict(self, cell: Cell, v: Mapping[str, Any], *, axis: str = "as_donated",
                       now: datetime | None = None) -> int:
        """One docket cell's verdict onto its mining cell.

        The FIRST judged docket cell settles the mining cell (EVALUATED, with that gate's reason
        or as a survivor). Every later one is recorded per axis, and a later pass on any axis
        makes the mining cell a survivor -- the docket judged it, so the count is the docket's.
        A docket cell outside the sealed expansion is FAILS_PREREG."""
        reason, gate = rejection.reason_for_verdict(v)
        if gate == "DEFERRED":
            return 0
        g = str(v.get("cell") or "")
        try:
            contract = self.prereg.load(cell.cell_id)
            sealed = {str(contract.get("gauntlet_cell") or ""),
                      *[str(x) for x in (contract.get("gauntlet_cells_expanded") or {}).values()]}
            spec = prereg.spec_of(contract)
            recomputed = {self.hooks.gauntlet_cell(spec), *self._expanded(spec).values()}
            ok = g in sealed and g in recomputed
            why = "" if ok else (f"judged {g}, which is not in the sealed expansion "
                                 f"({len(sealed)} cells) or its recomputation")
        except (OSError, ValueError, prereg.PreregMutationError) as exc:
            ok, why = False, str(exc)
        at = str(v.get("at") or iso(now or utcnow()))
        if not self.cells.record_axis_verdict(cell.cell_id, g, axis, at, bool(v.get("passed")),
                                              str(v.get("terminal_gate") or ""),
                                              "" if reason is None else reason.value):
            return 0                                          # this docket cell already joined
        verdict = {"gauntlet_cell": g, "axis": axis, "passed": bool(v.get("passed")),
                   "terminal_gate": v.get("terminal_gate"), "at": v.get("at"),
                   "downstream_status": v.get("downstream_status")}
        if cell.status == "EVALUATED":
            if ok and reason is None and not (cell.verdict or {}).get("survivor"):
                self.cells.update_doc(cell.cell_id, {"verdict": {
                    **(cell.verdict or {}), "survivor": True, "survivor_axis": verdict}})
            return 1
        if not ok:
            self.cells.transition(cell.cell_id, "EVALUATED", stage="preregister",
                                  reason="FAILS_PREREG", now=now, updates={"verdict": verdict})
            self.ledger.reject(cell.cell_id, "FAILS_PREREG", "preregister", detail=why,
                               source_id=cell.source_id)
            return 1
        if reason is None:
            self.cells.transition(cell.cell_id, "EVALUATED", stage="gauntlet", now=now,
                                  updates={"verdict": {**verdict, "survivor": True}})
            return 1
        self.cells.transition(cell.cell_id, "EVALUATED", stage="gauntlet",
                              reason=reason.value, now=now, updates={"verdict": verdict})
        self.ledger.reject(cell.cell_id, reason.value, "gauntlet", source_id=cell.source_id,
                           detail=f"terminal gate {gate} ({axis})",
                           kill_class=rejection.kill_class(gate))
        return 1

    # --------------------------------------------------------------------- deepening
    def handoff_deepening(self) -> int:
        if self.hooks.handoff is None:
            return 0
        cells = [c for c in self.cells.by_status("RESEARCH_ONLY", limit=50_000)
                 if (c.verdict or {}).get("handoff")][-DEEPENING_CAP:]
        tasks = [{
            "source": SOURCE, "kind": "story_mechanism",
            "title": f"{c.source_id}: {c.claim[:90]}",
            "description": (f"Verbatim claim ({c.original_language}): {c.claim}. MT5 "
                            f"instruments: {c.required_instruments or 'none named'}. "
                            f"Provenance: {c.source_uri}, available "
                            f"{c.available_for_decision_at}. Extract the exact mechanism as a "
                            "registered MT5 family and parameters if the text states one; "
                            "otherwise reject with why. Stated performance is not evidence."),
            "url": c.source_uri, "symbols": c.required_instruments,
            "mechanism_class": c.mechanism_family, "mechanism_key": c.mechanism_hash,
            "lang": c.original_language, "available_time": c.available_for_decision_at,
            "mining_cell_id": c.cell_id,
            "consumer": "deepening_worker (story_mechanism) -> miner_candidate_compiler -> "
                        "gauntlet"} for c in cells]
        return self.hooks.handoff(tasks) if tasks else 0

    # --------------------------------------------------------------------- 5. metrics
    def source_status(self, now: datetime | None = None) -> dict[str, dict[str, Any]]:
        t = now or utcnow()
        receipts = self.cells.evaluated_by_source(t - ACTIVE_WINDOW)
        try:
            docket = self.attributed_evaluations(t)
        except Exception as exc:                          # never lets status reporting fail
            docket = {"by_source": {}, "basis": f"ERROR {type(exc).__name__}: {exc}"[:200]}
        self._attribution = {k: v for k, v in docket.items() if k != "by_source"}
        via = docket["by_source"]
        runs = self.store.last_runs()
        recs = self.store.records_by_source()
        out = {}
        for s in self.roster:
            if not s.enabled:
                continue
            n_mine, n_docket = int(receipts.get(s.id, 0)), int(via.get(s.id, 0))
            n = n_mine + n_docket
            r = runs.get(s.id) or {}
            # Every use mints cells now: allocation_intel's facts become exogenous_conditioner
            # cells (see `conditioners`), so each use can carry a receipt.
            cell_use = bool(set(compiler.USES) & set(s.uses))
            out[s.id] = {"status": "ACTIVE" if n >= 1 and cell_use else "COLD",
                         "uses": list(s.uses),
                         "cold_reason": ("" if n >= 1 and cell_use else
                                         "serves no use" if not cell_use else
                                         "no cell EVALUATED in 30 days"),
                         "consumer": s.consumer,
                         "evaluated_cells_30d": n, "priority": s.priority,
                         "evaluated_via": {"mining": n_mine, "docket": n_docket},
                         "producers": dict(getattr(self, "_producers", {}).get(s.id, {})),
                         "origin": s.origin, "url_key": s.url_key, "aliases": list(s.aliases),
                         "shares_page": list(s.shares_page),
                         "last_outcome": r.get("outcome") or "NEVER_RUN",
                         "last_run": r.get("at"), "last_detail": r.get("detail") or "",
                         "records_total": int(recs.get(s.id, 0)), "auth": s.auth,
                         "owner": s.owner, "mode": s.mode}
        return out
