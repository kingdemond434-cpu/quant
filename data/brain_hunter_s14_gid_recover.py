#!/usr/bin/env python3
"""BRAIN HUNTER s14 -- GID-block recovery for a PDF whose font subset stripped
every Unicode channel.

s13's proposed route for `101 Formulaic Alphas.pdf` (arXiv:1601.00991) was
"/Differences glyph names + AGL". THAT ROUTE CANNOT WORK ON THIS FILE, and the
reason is provable from the file itself (see `diagnose()`):

  1. /Differences names are `/gNNNN` -- raw TrueType glyph INDICES, not AGL names.
  2. `post` is format 3.0 -- the glyph-name table is absent by design.
  3. the embedded `cmap` is a SYNTHETIC PUA identity (char code C -> U+F000+C),
     so it re-encodes the code rather than mapping it.

Three independent name channels, all stripped. What survives is the glyph INDEX,
and a glyph index is a position in the ORIGINAL font's glyph order -- which for a
Latin/Greek alphabet is contiguous. So the block can be calibrated from the codes
that DO carry a /ToUnicode entry and extended by offset arithmetic.

The calibration is EVIDENCE, not assumption: `calibrate()` derives each block's
base GID from >=2 observed (gid, char) pairs in the same font and REFUSES a block
whose observed pairs are not mutually consistent.

Unmapped glyphs render as `<gNNNN>` and NEVER as the empty string -- s13's tables
lost their row labels to silent empties, which read identically to "this cell has
no label" (the WS-005 class: absence resolving to a clean verdict).

Usage: python data/brain_hunter_s14_gid_recover.py <file.pdf> [--diagnose]
"""
from __future__ import annotations

import importlib.util
import re
import struct
import sys
from pathlib import Path

_S13 = Path(__file__).with_name("brain_hunter_s13_pdf_cmap_extract.py")
_spec = importlib.util.spec_from_file_location("s13", _S13)
assert _spec and _spec.loader
s13 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s13)

GID_NAME_RE = re.compile(r"g(\d+)")


def encoding_differences(objs: dict[int, bytes], font_body: bytes) -> dict[int, str]:
    """{char code: glyph name} from the font's /Encoding /Differences array."""
    enc = re.search(rb"/Encoding\s*(\d+)\s+\d+\s+R", font_body)
    if not enc:
        return {}
    body = objs.get(int(enc.group(1)), b"")
    diffs = re.search(rb"/Differences\s*\[(.*?)\]", body, re.S)
    if not diffs:
        return {}
    out: dict[int, str] = {}
    code = 0
    for num, name in re.findall(rb"(\d+)|/([A-Za-z0-9._]+)", diffs.group(1)):
        if num:
            code = int(num)
        else:
            out[code] = name.decode("latin-1")
            code += 1
    return out


def calibrate(pairs: list[tuple[int, str]]) -> list[tuple[int, int, str]]:
    """Derive contiguous (base_gid, length, alphabet) blocks from observed pairs.

    `pairs` are (gid, character) observations harvested from the font's own
    /ToUnicode entries. A block is accepted only when >=2 observations agree on
    the same base; a single lonely observation is NOT enough to extend a block,
    because one point fits any offset.
    """
    alphabets = {
        "upper": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "lower": "abcdefghijklmnopqrstuvwxyz",
        "digit": "0123456789",
    }
    votes: dict[tuple[str, int], list[int]] = {}
    for gid, ch in pairs:
        for key, alpha in alphabets.items():
            if ch in alpha:
                votes.setdefault((key, gid - alpha.index(ch)), []).append(gid)
    blocks = []
    for (key, base), gids in votes.items():
        if len(set(gids)) < 2:
            continue  # one point fits any offset -- not evidence
        blocks.append((base, len(alphabets[key]), alphabets[key]))
    return sorted(blocks)


def gid_table(blocks: list[tuple[int, int, str]]) -> dict[int, str]:
    out: dict[int, str] = {}
    for base, length, alpha in blocks:
        for i in range(length):
            out.setdefault(base + i, alpha[i])
    return out


def font_cmap_with_gids(
    objs: dict[int, bytes], font_body: bytes
) -> tuple[dict[int, str], dict[int, int]]:
    """Return (code->unicode from /ToUnicode, code->gid from /Differences)."""
    tu: dict[int, str] = {}
    tum = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", font_body)
    if tum:
        data = s13.stream_data(objs.get(int(tum.group(1)), b"") or b"")
        if data:
            tu = s13.parse_cmap(data)
    gids: dict[int, int] = {}
    for code, name in encoding_differences(objs, font_body).items():
        m = GID_NAME_RE.fullmatch(name)
        if m:
            gids[code] = int(m.group(1))
    return tu, gids


def build_tables(objs: dict[int, bytes], resources: bytes) -> dict[bytes, dict[int, str]]:
    """s13's font_tables(), extended: unmapped codes recovered by GID block, and
    anything still unknown rendered as a VISIBLE `<gNNNN>` placeholder."""
    resources = s13.resolve(objs, resources)
    fm = re.search(rb"/Font\s*(\d+\s+\d+\s+R|<<)", resources)
    if not fm:
        return {}
    if fm.group(1) == b"<<":
        start = fm.end() - 2
        depth, i = 0, start
        while i < len(resources) - 1:
            if resources[i : i + 2] == b"<<":
                depth += 1
                i += 2
            elif resources[i : i + 2] == b">>":
                depth -= 1
                i += 2
                if depth == 0:
                    break
            else:
                i += 1
        fdict = resources[start:i]
    else:
        fdict = s13.resolve(objs, fm.group(1))

    tables: dict[bytes, dict[int, str]] = {}
    for name, ref in re.findall(rb"/([A-Za-z0-9#+.\-]+)\s+(\d+)\s+\d+\s+R", fdict):
        body = objs.get(int(ref), b"")
        if not re.search(rb"/Type\s*/Font", body):
            continue
        tu, gids = font_cmap_with_gids(objs, body)
        if not tu and b"/WinAnsiEncoding" in body:
            # Type1 base-14: the code space IS Latin-1 (no ToUnicode is correct,
            # not missing) -- s13 dropped these fonts whole.
            tu = {c: chr(c) for c in range(32, 256)}
        pairs = [(gids[c], tu[c]) for c in gids if c in tu and len(tu.get(c, "")) == 1]
        recovered = gid_table(calibrate(pairs))
        table = dict(tu)
        for code, gid in gids.items():
            if code in table:
                continue
            table[code] = recovered.get(gid) or f"<g{gid}>"
        tables[b"/" + name] = table
    return tables


def extract(raw: bytes) -> str:
    objs = s13.load_objects(raw)
    pages: list[tuple[bytes, list[int]]] = []
    for _num, body in list(objs.items()):
        if not re.search(rb"/Type\s*/Page\b", body):
            continue
        res = re.search(rb"/Resources\s*(\d+\s+\d+\s+R|<<)", body)
        cm = re.search(rb"/Contents\s*(?:\[([^\]]*)\]|(\d+)\s+\d+\s+R)", body)
        if not res or not cm:
            continue
        resources = (
            body[res.end() - 2 :] if res.group(1) == b"<<" else s13.resolve(objs, res.group(1))
        )
        cids = (
            [int(x) for x in re.findall(rb"(\d+)\s+\d+\s+R", cm.group(1))]
            if cm.group(1)
            else [int(cm.group(2))]
        )
        pages.append((resources, cids))
    out: list[str] = []
    for resources, cids in pages:
        tables = build_tables(objs, resources)
        content = b"".join(s13.stream_data(objs.get(c, b"")) or b"" for c in cids)
        out.extend(s13.render_page(tables, content))
        out.append("\f")
    return "\n".join(out)


def diagnose(raw: bytes) -> None:
    """Prove, per font, WHICH Unicode channels the producer stripped."""
    objs = s13.load_objects(raw)
    for num, body in sorted(objs.items()):
        if not re.search(rb"/Type\s*/Font", body):
            continue
        bf = re.search(rb"/BaseFont\s*/([A-Za-z0-9+\-.]+)", body)
        tu, gids = font_cmap_with_gids(objs, body)
        pairs = [(gids[c], tu[c]) for c in gids if c in tu and len(tu.get(c, "")) == 1]
        blocks = calibrate(pairs)
        post_fmt = None
        fd = re.search(rb"/FontDescriptor\s+(\d+)", body)
        if fd:
            ff = re.search(rb"/FontFile2\s+(\d+)", objs.get(int(fd.group(1)), b""))
            if ff:
                d = s13.stream_data(objs.get(int(ff.group(1)), b"") or b"") or b""
                n = struct.unpack(">H", d[4:6])[0] if len(d) > 6 else 0
                for i in range(n):
                    off = 12 + 16 * i
                    if d[off : off + 4] == b"post":
                        o = struct.unpack(">I", d[off + 8 : off + 12])[0]
                        post_fmt = hex(struct.unpack(">I", d[o : o + 4])[0])
        print(
            f"obj {num:>4} {bf.group(1).decode() if bf else '?':<24} "
            f"tounicode={len(tu):>3} gidnames={len(gids):>3} "
            f"unmapped={sum(1 for c in gids if c not in tu):>3} "
            f"post={post_fmt} blocks={[(b, a[0]) for b, _l, a in blocks]}"
        )


if __name__ == "__main__":
    data = Path(sys.argv[1]).read_bytes()
    if "--diagnose" in sys.argv:
        diagnose(data)
    else:
        sys.stdout.write(extract(data))
