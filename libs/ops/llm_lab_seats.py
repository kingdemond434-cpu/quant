"""LLM LAB SEATS -- which model answers a lab job, and who gets the credit.

EVERY `:free` id of every family on OpenRouter's public model list is a named seat (paid ids are
never registered). The first job of a cycle takes the least-called seat (coverage); the rest go to
the best measured seats by the same yield formula the labs are ranked on. A failed seat falls
through to the next with the attempt on the record, and the job is credited to the seat that
ANSWERED -- never a silent substitution. A loopback open-weight seat (any family) takes over when
the cloud is out.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from libs.ops import deepseek_cycle as ds
from libs.ops.llm_lab_core import (
    MODELS,
    MODELS_TTL_H,
    MODELS_URL,
    _iso,
    _load,
    _now_dt,
    _parse,
    _save,
)

# ------------------------------------------------------------------------- the models


def _get_json(url: str, timeout: float = 20.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": "quant-deepseek-lab/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def model_family(model_id: str) -> str:
    """The seat family: the provider prefix of an OpenRouter id, `local` for a loopback model."""
    mid = str(model_id or "")
    if mid.startswith("local/"):
        return "local"
    return mid.split("/", 1)[0] if "/" in mid else "?"


def refresh_models(root: Path, *, fetch: Callable[[str], Any] | None = None,
                   now: datetime | None = None) -> dict[str, Any]:
    """Section 27. OpenRouter's PUBLIC model list (no key is sent), cached for MODELS_TTL_H.

    EVERY `:free` id of EVERY family is a seat (zuck: "this doesnt literally mean deepseek but our
    llm factory lab" + every :free model each cycle). Paid ids are never registered, so a paid
    route cannot be reached from here even by a stale pin."""
    t = now or _now_dt()
    path = root / MODELS
    cached = _load(path, {})
    at = _parse(cached.get("fetched_utc")) if isinstance(cached, dict) else None
    if at and (t - at) < timedelta(hours=MODELS_TTL_H) and cached.get("models"):
        return dict(cached)
    try:
        doc = (fetch or _get_json)(MODELS_URL)
        rows = doc.get("data") if isinstance(doc, dict) else None
        if not isinstance(rows, list):
            raise ValueError("no data list")
    except Exception as exc:
        out = dict(cached) if isinstance(cached, dict) else {}
        out.update({"status": "UNMEASURED" if not out.get("models") else "STALE",
                    "last_error": f"{type(exc).__name__}: {str(exc)[:200]}",
                    "attempted_utc": _iso(t)})
        _save(path, out)
        return out
    models = []
    for m in rows:
        mid = str((m or {}).get("id") or "")
        if not mid.endswith(":free"):
            continue
        params = m.get("supported_parameters") or []
        low = mid.lower()
        models.append({"id": mid, "family": model_family(mid), "free": True,
                       "context_length": m.get("context_length"),
                       "reasoning": ("reasoning" in params) or "r1" in low or "think" in low,
                       "structured_output": ("response_format" in params
                                             or "structured_outputs" in params),
                       "created": m.get("created")})
    out = {"status": "MEASURED", "fetched_utc": _iso(t), "source": MODELS_URL,
           "families": sorted({m["family"] for m in models}),
           "models": sorted(models, key=lambda m: (-(m.get("created") or 0), m["id"]))}
    _save(path, out)
    return out


def model_rate(attrib: dict[str, Any], model: str) -> tuple[float, str]:
    """The seat's measured yield per call -- the same formula `lab_rate` applies to labs, so the
    auction ranks models and labs on one scale. Under three calls a seat is on PROBATION."""
    row = (attrib.get("by_model") or {}).get(model) or {}
    calls = int(row.get("calls") or 0)
    if calls < 3:
        return 1.0, "PROBATION"
    useful = (float(row.get("compiled") or 0) + 5.0 * float(row.get("passed") or 0)
              + 0.25 * float(row.get("requests") or 0))
    return (1.0 + useful) / (1.0 + calls), "MEASURED"


def plan_seats(tier: str, reg: dict[str, Any], attrib: dict[str, Any], *, pin: str = "",
               used: set[str] | None = None, coverage: bool = False, n: int = 3
               ) -> dict[str, Any]:
    """The ordered seats one job tries. Never a silent substitution: the plan names why each
    seat is where it is, and the job records the seat that actually answered.

    * COVERAGE slot (`coverage=True`, the first job of a cycle): the least-called free seat goes
      first, so every listed model keeps getting calls and a new one is measured, not ignored.
    * Otherwise seats rank by `model_rate` (probation = 1.0), deep jobs prefer reasoning seats,
      and a seat already used this cycle drops behind unused ones -- the load spreads over seats.
    * An unmeasured registry has no seats to plan with: a `:free` env pin is used as written; a
      paid pin never is."""
    if reg.get("status") not in ("MEASURED", "STALE"):
        if pin.endswith(":free"):
            return {"seats": [pin], "why": "registry UNMEASURED; :free env pin used as written"}
        return {"seats": [], "why": "registry UNMEASURED and no :free pin: MODEL_UNAVAILABLE"}
    u = used or set()
    calls = {k: int((v or {}).get("calls") or 0)
             for k, v in (attrib.get("by_model") or {}).items()}
    models = [m for m in reg["models"] if m.get("free")]
    if not models:
        return {"seats": [], "why": "no free model is listed: MODEL_UNAVAILABLE"}
    want_reasoning = tier == "deep"

    def key(m: dict[str, Any]) -> tuple[Any, ...]:
        rate, _ = model_rate(attrib, m["id"])
        return (m["id"] in u, bool(m.get("reasoning")) != want_reasoning, -rate,
                calls.get(m["id"], 0), m["id"])

    ranked = sorted(models, key=key)
    why = "ranked by measured seat yield"
    if coverage:
        cov = min(models, key=lambda m: (m["id"] in u, calls.get(m["id"], 0), m["id"]))
        ranked = [cov] + [m for m in ranked if m["id"] != cov["id"]]
        why = (f"coverage slot: {cov['id']} is the least-called free seat "
               f"({calls.get(cov['id'], 0)} calls)")
    seats = [m["id"] for m in ranked[:n]]
    listed = {m["id"] for m in models}
    if pin and pin in listed and pin not in seats:
        seats = [*seats[:n - 1], pin]
    return {"seats": seats, "why": why,
            "pin": (None if not pin else "listed" if pin in listed else "DELISTED")}


def _local_chat(user: str, system: str, model: str, base_url: str, timeout: float = 600.0
                ) -> tuple[str, str | None]:
    """A loopback OpenAI-compatible server (ollama, llama.cpp, vLLM). Refuses any non-loopback
    host: the local rung exists so nothing leaves the box."""
    host = urllib.parse.urlparse(base_url).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        return "", f"LOCAL_REFUSED: {host!r} is not loopback"
    body = json.dumps({"model": model, "messages": [{"role": "system", "content": system},
                                                    {"role": "user", "content": user}],
                       "temperature": 0.7}).encode("utf-8")
    req = urllib.request.Request(base_url.rstrip("/") + "/chat/completions", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        from libs.ops import openrouter_guard  # loopback never bills; the guard still sees it
        openrouter_guard.check_request(req)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            doc = json.loads(r.read().decode("utf-8"))
        return str(doc["choices"][0]["message"]["content"]), None
    except Exception as exc:
        return "", f"LOCAL_FAILED: {type(exc).__name__}: {str(exc)[:200]}"


def local_seat(env: dict[str, str]) -> tuple[str, str]:
    """(base_url, model) of the loopback open-weight seat, any family. LLM_LAB_LOCAL_* first,
    the older DEEPSEEK_LOCAL_* names still honoured."""
    return (env.get("LLM_LAB_LOCAL_BASE_URL") or env.get("DEEPSEEK_LOCAL_BASE_URL") or "",
            env.get("LLM_LAB_LOCAL_MODEL") or env.get("DEEPSEEK_LOCAL_MODEL") or "")


def make_chat(env: dict[str, str], reg: dict[str, Any], attrib: dict[str, Any] | None = None
              ) -> Callable[..., dict[str, Any]]:
    """Free cloud seats of every family (ranked per job by `plan_seats`), then the loopback
    open-weight seat. Each failed seat is an attempt on the record; the seat that answered is the
    model the job is credited to."""
    from libs.ops import llm_seat

    att = attrib or {}
    used: set[str] = set()

    def chat(user: str, system: str, tier: str) -> dict[str, Any]:
        seat = ds.seat_state(env)
        attempts: list[dict[str, Any]] = []
        plan: dict[str, Any] = {"seats": [], "why": "DARK"}
        if seat.lit:
            pin = seat.deep_model if tier == "deep" else seat.bulk_model
            plan = plan_seats(tier, reg, att, pin=pin, used=used, coverage=not used)
            for mid in plan["seats"]:
                ls = llm_seat.Seat(name=f"llm_lab_{tier}",
                                   base_url=env.get("DEEPSEEK_BASE_URL",
                                                    "https://openrouter.ai/api/v1"),
                                   key=ds.resolve_key(env)[0], model=mid)
                text, err = llm_seat.chat(user, system=system, seat=ls,
                                          max_tokens=16000 if tier == "deep" else 6000)
                used.add(mid)
                if not err and text:
                    # llm_seat may swap a retired id for a listed one under us; credit the id
                    # that actually answered and keep the swap on the record.
                    resolved = getattr(llm_seat, "last_resolved", None)
                    actual = str(resolved(ls) or "") if callable(resolved) else ""
                    if actual and actual != mid:
                        attempts.append({"provider": "openrouter", "model": mid,
                                         "swapped_to": actual})
                        mid = actual
                    return {"text": text, "provider": "openrouter", "model": mid,
                            "family": model_family(mid), "pick": plan, "attempts": attempts}
                attempts.append({"provider": "openrouter", "model": mid,
                                 "error": str(err or "empty reply")[:300]})
            if not plan["seats"]:
                attempts.append({"provider": "openrouter", "error": plan["why"]})
        else:
            attempts.append({"provider": "openrouter", "error": "DARK"})
        lurl, lmodel = local_seat(env)
        if lurl and lmodel:
            text, err = _local_chat(user, system, lmodel, lurl)
            if not err:
                return {"text": text, "provider": "local", "model": f"local/{lmodel}",
                        "family": "local", "pick": plan, "attempts": attempts}
            attempts.append({"provider": "local", "model": f"local/{lmodel}", "error": err})
        return {"text": "", "error": "; ".join(str(a.get("error")) for a in attempts),
                "attempts": attempts}

    return chat


