"""LICENCE ENFORCEMENT for everything the civilizations read from public repositories.

A public repository is not a public-domain one. What may be KEPT depends on its licence:

    permissive (MIT, Apache-2.0, BSD, ISC, Unlicense, CC0, 0BSD, Zlib)
        the file is kept with its notice: the repository's copyright lines head the body and
        the full licence text is written once per repository under notices/
    anything else (GPL/AGPL/LGPL/MPL, a proprietary EULA, no licence at all, unrecognised)
        METADATA ONLY: the path, the language and a rewritten description made of the facts
        the extractors need (indicator calls with their periods, formula strings, identifiers).
        The verbatim text is read in memory to derive that description and never stored.

Notebooks keep their cell SOURCES only; outputs (tables, images, printed data) are dropped for
every licence, because an output is data the notebook's author may not have had the right to
publish either. `DATA_EXCLUDE` in fetchers keeps data files out of reach altogether.
"""
from __future__ import annotations

import json
import re
from typing import Any

PERMISSIVE: frozenset[str] = frozenset({
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "Unlicense", "CC0-1.0",
    "0BSD", "Zlib", "BSL-1.0", "MIT-0"})

_DETECT: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("AGPL-3.0", re.compile(r"GNU AFFERO GENERAL PUBLIC LICENSE", re.I)),
    ("LGPL-3.0", re.compile(r"GNU LESSER GENERAL PUBLIC LICENSE", re.I)),
    ("GPL-3.0", re.compile(r"GNU GENERAL PUBLIC LICENSE", re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License", re.I)),
    ("Apache-2.0", re.compile(r"Apache License,?\s+Version 2\.0", re.I)),
    ("MIT", re.compile(r"Permission is hereby granted, free of charge", re.I)),
    ("ISC", re.compile(r"Permission to use, copy, modify, and/?or distribute this software", re.I)),
    ("BSD-3-Clause", re.compile(r"Neither the name of .{0,200} nor the names", re.I | re.S)),
    ("BSD-2-Clause", re.compile(r"Redistribution and use in source and binary forms", re.I)),
    ("Unlicense", re.compile(r"This is free and unencumbered software", re.I)),
    ("CC0-1.0", re.compile(r"CC0 1\.0|Creative Commons Zero", re.I)),
    ("BSL-1.0", re.compile(r"Boost Software License", re.I)),
)
LICENCE_FILE = re.compile(r"^(?:LICEN[CS]E|COPYING|UNLICENSE)(?:[.-][\w.-]*)?$", re.I)
_COPYRIGHT = re.compile(r"^\s*(?:Copyright|\(c\)|©).{0,200}$", re.I | re.M)


def detect(text: str) -> str:
    """The SPDX id a licence file's text states, 'NOASSERTION' when none is recognised."""
    for spdx, rx in _DETECT:
        if rx.search(text or ""):
            return spdx
    return "NOASSERTION"


def is_permissive(spdx: str | None) -> bool:
    return str(spdx or "") in PERMISSIVE


def notice_header(spdx: str, licence_text: str, repo: str) -> str:
    lines = [ln.strip() for ln in _COPYRIGHT.findall(licence_text or "")][:5]
    head = "; ".join(lines) if lines else f"copyright the authors of {repo}"
    return f"[licence {spdx}: {head}. Full notice: notices/ for {repo}]\n"


def strip_notebook(body: str) -> str:
    """A .ipynb reduced to its cell sources, outputs and attachments dropped."""
    try:
        nb = json.loads(body)
    except ValueError:
        return ""
    out: list[str] = []
    for cell in nb.get("cells") or [] if isinstance(nb, dict) else []:
        src = cell.get("source") if isinstance(cell, dict) else None
        text = "".join(src) if isinstance(src, list) else str(src or "")
        if text.strip():
            out.append(f"# [{cell.get('cell_type', 'cell')}]\n{text}")
    return "\n\n".join(out)


_IDENT = re.compile(r"\b(?:def|class|function|void|public\s+\w+|private\s+\w+)\s+([A-Za-z_]\w*)")
_CALL = re.compile(r"\b([A-Za-z_][\w.]*)\s*\(\s*([^()]{0,80})\)")


def derived_description(path: str, body: str, spdx: str, repo: str) -> str:
    """For a file whose licence does not let its text be kept: the FACTS the extractors read,
    in a sentence form of our own. Identifiers name what exists; a call with its literal
    arguments (`RSI(14)`, `ts_rank(close, 10)`) is a parameter fact, not expression."""
    from libs.civilizations import expression as E

    idents = sorted(set(_IDENT.findall(body or "")))[:60]
    calls: list[str] = []
    for name, args in _CALL.findall(body or ""):
        if re.fullmatch(r"[\w\s.,=+-]*", args) and any(ch.isdigit() for ch in args):
            compact = re.sub(r"\s+", "", args)
            calls.append(f"{name.split('.')[-1]}({compact})")
    calls = sorted(set(calls))[:80]
    formulas = [f for _, f in E.extract_formulas(body or "", max_n=40)]
    parts = [f"file {path} in {repo}, licence {spdx}: text not kept (metadata only)."]
    if idents:
        parts.append("defines " + ", ".join(idents) + ".")
    if calls:
        parts.append("calls with parameters " + ", ".join(calls) + ".")
    parts.extend(f"formula: {f}" for f in formulas)
    return "\n".join(parts)


def keep(path: str, body: str, spdx: str, licence_text: str,
         repo: str) -> tuple[str, dict[str, Any]]:
    """(body to store, meta) for one file under the repository's licence."""
    if path.lower().endswith(".ipynb"):
        body = strip_notebook(body)
    meta: dict[str, Any] = {"licence": spdx, "licence_permissive": is_permissive(spdx)}
    if is_permissive(spdx):
        return notice_header(spdx, licence_text, repo) + body, meta
    meta["metadata_only"] = True
    return derived_description(path, body, spdx, repo), meta
