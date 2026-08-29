#!/usr/bin/env python3
"""BRAIN HUNTER s13 -- per-font ToUnicode CMap binding PDF text extractor.

s12 diagnosed the wall: `101 Formulaic Alphas.pdf` streams decompress cleanly but the
text is font-subsetted, and MERGING every /ToUnicode CMap into one table collides
(multiple subset fonts share one single-byte code space, so `a` -> `^`). The fix is to
bind each CMap to its own font resource name and switch tables on the `Tf` operator.

Pure stdlib (zlib + re): no PDF library is installed on the box and the research freeze
forbids installs. Writes plain text to stdout.

Usage: python data/brain_hunter_s13_pdf_cmap_extract.py <file.pdf>
"""
from __future__ import annotations

import re
import sys
import zlib

OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)


def load_objects(raw: bytes) -> dict[int, bytes]:
    """Return {objnum: body}. Later definitions win (incremental updates)."""
    objs: dict[int, bytes] = {}
    for m in OBJ_RE.finditer(raw):
        objs[int(m.group(1))] = m.group(3)
    return objs


def stream_data(body: bytes) -> bytes | None:
    """Return the decoded stream of an object body, or None.

    Index-based, NOT regex-delimited: a Flate payload frequently abuts `endstream`
    with no trailing EOL, and a `\r?\n`-anchored pattern silently drops those objects
    (21 of this paper's 22 pages).
    """
    if b"stream" not in body:
        return None
    i = body.index(b"stream") + len(b"stream")
    try:
        j = body.rindex(b"endstream")
    except ValueError:
        return None
    data = body[i:j].lstrip(b"\r\n")
    if b"/FlateDecode" not in body[:i]:
        return data
    try:
        return zlib.decompress(data)
    except zlib.error:
        try:
            return zlib.decompressobj().decompress(data)
        except zlib.error:
            return None


def resolve(objs: dict[int, bytes], token: bytes) -> bytes:
    """Follow `N 0 R` indirect references one hop (repeatedly)."""
    seen = 0
    while seen < 8:
        m = re.fullmatch(rb"\s*(\d+)\s+\d+\s+R\s*", token)
        if not m:
            return token
        token = objs.get(int(m.group(1)), b"")
        seen += 1
    return token


def parse_cmap(text: bytes) -> dict[int, str]:
    """Parse bfchar/bfrange sections of a ToUnicode CMap into {code: str}."""
    out: dict[int, str] = {}

    def uni(h: bytes) -> str:
        s = h.decode("latin-1")
        # UTF-16BE, possibly multiple code units (ligatures such as fi)
        try:
            return bytes.fromhex(s).decode("utf-16-be", errors="ignore")
        except ValueError:
            return ""

    for blk in re.findall(rb"beginbfchar(.*?)endbfchar", text, re.S):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            out[int(src, 16)] = uni(dst)
    for blk in re.findall(rb"beginbfrange(.*?)endbfrange", text, re.S):
        # form 1: <lo> <hi> <dststart>
        for lo, hi, dst in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk
        ):
            lo_i, hi_i = int(lo, 16), int(hi, 16)
            base = int(dst, 16)
            for k in range(min(hi_i - lo_i + 1, 65536)):
                out[lo_i + k] = chr(base + k)
        # form 2: <lo> <hi> [ <d0> <d1> ... ]
        for lo, _hi, arr in re.findall(
            rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[(.*?)\]", blk, re.S
        ):
            lo_i = int(lo, 16)
            for k, dst in enumerate(re.findall(rb"<([0-9A-Fa-f]*)>", arr)):
                out[lo_i + k] = uni(dst)
    return out


def font_tables(objs: dict[int, bytes], resources: bytes) -> dict[bytes, dict[int, str]]:
    """{resource_name: cmap} for one page's /Font resource dict -- THE binding s12 lacked."""
    resources = resolve(objs, resources)
    fm = re.search(rb"/Font\s*(\d+\s+\d+\s+R|<<)", resources)
    if not fm:
        return {}
    if fm.group(1) == b"<<":
        # inline dict: take the balanced-ish slice to the matching >>
        start = fm.end() - 2
        depth, i = 0, start
        while i < len(resources) - 1:
            if resources[i : i + 2] == b"<<":
                depth += 1
                i += 2
                continue
            if resources[i : i + 2] == b">>":
                depth -= 1
                i += 2
                if depth == 0:
                    break
                continue
            i += 1
        fdict = resources[start:i]
    else:
        fdict = resolve(objs, fm.group(1))

    tables: dict[bytes, dict[int, str]] = {}
    for name, ref in re.findall(rb"/([A-Za-z0-9#+.\-]+)\s+(\d+)\s+\d+\s+R", fdict):
        fobj = objs.get(int(ref), b"")
        tu = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", fobj)
        if not tu:
            continue
        data = stream_data(objs.get(int(tu.group(1)), b"") or b"")
        if data:
            tables[b"/" + name] = parse_cmap(data)
    return tables


def _decode_literal(s: bytes) -> bytes:
    """Resolve PDF literal-string escapes, including \\ooo octal."""
    out = bytearray()
    i = 0
    simple = {b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12, b"(": 40, b")": 41, b"\\": 92}
    while i < len(s):
        c = s[i : i + 1]
        if c != b"\\":
            out += c
            i += 1
            continue
        nxt = s[i + 1 : i + 2]
        if nxt in simple:
            out.append(simple[nxt])
            i += 2
        elif nxt.isdigit():
            j = i + 1
            while j < len(s) and j < i + 4 and s[j : j + 1].isdigit():
                j += 1
            out.append(int(s[i + 1 : j], 8) & 0xFF)
            i = j
        else:
            out += nxt
            i += 2
    return bytes(out)


TOKEN_RE = re.compile(
    rb"(/[A-Za-z0-9#+.\-]+)\s+[\d.]+\s+Tf"          # 1: font switch
    rb"|\((?:\\.|[^\\()])*\)\s*(?:Tj|')"             # literal show
    rb"|<([0-9A-Fa-f\s]*)>\s*Tj"                     # 2: hex show
    rb"|\[((?:\\.|[^\]\\]|\\\])*)\]\s*TJ"            # 3: array show
    rb"|(T\*|Td|TD|ET)",                             # 4: line/section break
    re.S,
)
STR_IN_ARRAY = re.compile(rb"\((?:\\.|[^\\()])*\)|<([0-9A-Fa-f\s]*)>|(-?[\d.]+)")


def render_page(tables: dict[bytes, dict[int, str]], content: bytes) -> list[str]:
    """Replay one page's content stream, switching CMaps on `Tf`.

    The font table is per-PAGE state that changes mid-stream, which is exactly what a single
    merged CMap cannot represent -- subset fonts share one single-byte code space, so merging
    collides (`a` -> `^`).
    """
    out: list[str] = []
    font: dict[int, str] = {}
    line: list[str] = []

    def show(data: bytes, hexmode: bool) -> None:
        codes = (
            [int(data[k : k + 2], 16) for k in range(0, len(data) - 1, 2)]
            if hexmode
            else list(_decode_literal(data))
        )
        for code in codes:
            line.append(font.get(code, ""))

    for m in TOKEN_RE.finditer(content):
        if m.group(1):
            font = tables.get(m.group(1), {})
        elif m.group(2) is not None:
            show(re.sub(rb"\s", b"", m.group(2)), True)
        elif m.group(3) is not None:
            for sm in STR_IN_ARRAY.finditer(m.group(3)):
                if sm.group(1) is not None:
                    show(re.sub(rb"\s", b"", sm.group(1)), True)
                elif sm.group(2) is not None:
                    # kerning: a large negative adjustment is an inter-word space
                    if float(sm.group(2)) < -140:
                        line.append(" ")
                else:
                    show(sm.group(0)[1:-1], False)
        elif m.group(4):
            out.append("".join(line))
            line.clear()
        else:  # literal-string show outside an array
            lit = m.group(0)
            show(lit[lit.index(b"(") + 1 : lit.rindex(b")")], False)
    if line:
        out.append("".join(line))
    return out


def extract(raw: bytes) -> str:
    objs = load_objects(raw)
    pages: list[tuple[bytes, list[int]]] = []
    for _num, body in list(objs.items()):
        if b"/Type" not in body or not re.search(rb"/Type\s*/Page\b", body):
            continue
        res = re.search(rb"/Resources\s*(\d+\s+\d+\s+R|<<)", body)
        if not res:
            continue
        resources = (
            body[res.end() - 2 :] if res.group(1) == b"<<" else resolve(objs, res.group(1))
        )
        cm = re.search(rb"/Contents\s*(?:\[([^\]]*)\]|(\d+)\s+\d+\s+R)", body)
        if not cm:
            continue
        if cm.group(1):
            cids = [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", cm.group(1))]
        else:
            cids = [int(cm.group(2))]
        pages.append((resources, cids))

    # Pages are emitted in object order, which for this producer is document order.
    out: list[str] = []
    for resources, cids in pages:
        tables = font_tables(objs, resources)
        content = b"".join(stream_data(objs.get(c, b"")) or b"" for c in cids)
        out.extend(render_page(tables, content))
        out.append("\f")
    return "\n".join(out)


if __name__ == "__main__":
    with open(sys.argv[1], "rb") as fh:
        sys.stdout.write(extract(fh.read()))
