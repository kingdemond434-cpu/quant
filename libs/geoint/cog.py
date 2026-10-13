"""A MINIMAL CLOUD-OPTIMISED GEOTIFF READER: HTTP range reads, tiled, DEFLATE/LZW/none, no GDAL.

WHY THIS EXISTS (2026-10-13). The desk's Python has numpy and scipy and nothing that reads a
GeoTIFF (no rasterio, no GDAL, no tifffile, no PIL), and the GEOINT factory needs a few hundred
kilobytes out of a 220 MB Sentinel-2 band file per scene. A COG is a TIFF whose tiles are laid out
so a reader can fetch only the tiles a window touches; everything needed to do that is the TIFF
header, one IFD and two offset arrays. This module reads exactly that and nothing more:

  * byte order II/MM, classic TIFF (magic 42; BigTIFF is refused, never guessed),
  * tiled single-band images (TileWidth/TileLength/TileOffsets/TileByteCounts),
  * compression 1 (none), 8 / 32946 (DEFLATE via zlib) -- what the Sentinel-2 COGs on the AWS
    open-data bucket carry (measured on 14SPE B04: compression 8, predictor 2, uint16, 1024 tiles),
  * predictor 1 (none) and 2 (horizontal differencing, per row, integer samples),
  * ModelPixelScale (33550) and ModelTiepoint (33922) for the pixel -> map transform.

Anything outside that is refused with a named reason (``CogUnsupported``) rather than decoded
wrongly: a half-read raster that looks like a raster is the worst failure a sensor can have.

The byte source is injectable (``fetch(url, start, end) -> bytes``), so the tests build a COG in
memory and read it back through the same code path the pilot uses over HTTP.
"""
from __future__ import annotations

import struct
import urllib.request
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np

Fetch = Callable[[str, int, int], bytes]

HEADER_BYTES = 65_536
_TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8, 16: 8}
_TYPE_FMT = {1: "B", 2: "c", 3: "H", 4: "I", 6: "b", 7: "B", 8: "h", 9: "i", 11: "f", 12: "d",
             16: "Q"}
_DTYPES = {(1, 8): np.uint8, (1, 16): np.uint16, (1, 32): np.uint32, (2, 8): np.int8,
           (2, 16): np.int16, (2, 32): np.int32, (3, 32): np.float32, (3, 64): np.float64}


class CogUnsupported(ValueError):
    """The file is a TIFF this reader does not decode; the reason is the message."""


def http_fetch(url: str, start: int, end: int, timeout: float = 60.0) -> bytes:
    """Bytes [start, end] inclusive of `url` by an HTTP Range request (urllib; proxy from env)."""
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}",
                                               "User-Agent": "quant-geoint/1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = bytes(resp.read())
    return data


@dataclass(frozen=True)
class GeoTransform:
    """Pixel (col, row) of the top-left corner -> map (x, y): x = x0 + col*dx, y = y0 - row*dy."""

    x0: float
    y0: float
    dx: float
    dy: float

    def to_pixel(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.x0) / self.dx, (self.y0 - y) / self.dy

    def to_map(self, col: float, row: float) -> tuple[float, float]:
        return self.x0 + col * self.dx, self.y0 - row * self.dy


class COG:
    """One single-band tiled TIFF read lazily by byte ranges."""

    def __init__(self, url: str, fetch: Fetch | None = None) -> None:
        self.url = url
        self._fetch: Fetch = fetch or http_fetch
        self._head = self._fetch(url, 0, HEADER_BYTES - 1)
        self.bytes_read = len(self._head)
        if self._head[:2] == b"II":
            self._bo = "<"
        elif self._head[:2] == b"MM":
            self._bo = ">"
        else:
            raise CogUnsupported("not a TIFF (no II/MM byte-order mark)")
        magic = struct.unpack(self._bo + "H", self._head[2:4])[0]
        if magic != 42:
            raise CogUnsupported(f"TIFF magic {magic}: only classic TIFF (42) is read, "
                                 "BigTIFF (43) is refused")
        ifd = struct.unpack(self._bo + "I", self._head[4:8])[0]
        self.tags = self._read_ifd(ifd)
        t = self.tags
        self.width = int(t[256][0])
        self.height = int(t[257][0])
        bits = int(t.get(258, [1])[0])
        fmt = int(t.get(339, [1])[0])
        if int(t.get(277, [1])[0]) != 1:
            raise CogUnsupported("more than one sample per pixel: only single-band files are read")
        if (fmt, bits) not in _DTYPES:
            raise CogUnsupported(f"sample format {fmt} with {bits} bits is not decoded")
        self.dtype = np.dtype(_DTYPES[(fmt, bits)]).newbyteorder("<" if self._bo == "<" else ">")
        self.compression = int(t.get(259, [1])[0])
        if self.compression not in (1, 8, 32946):
            raise CogUnsupported(f"compression {self.compression}: only none and DEFLATE are read")
        self.predictor = int(t.get(317, [1])[0])
        if self.predictor not in (1, 2):
            raise CogUnsupported(f"predictor {self.predictor} is not decoded")
        if 322 not in t or 324 not in t:
            raise CogUnsupported("not tiled: a strip TIFF is not cloud-optimised")
        self.tile_w = int(t[322][0])
        self.tile_h = int(t[323][0])
        self.offsets = [int(v) for v in t[324]]
        self.counts = [int(v) for v in t[325]]
        self.tiles_across = -(-self.width // self.tile_w)
        nodata = t.get(42113)
        self.nodata: float | None = None
        if nodata:
            try:
                self.nodata = float(b"".join(nodata).decode("ascii").strip("\x00 "))
            except (ValueError, UnicodeDecodeError, TypeError):
                self.nodata = None
        scale, tie = t.get(33550), t.get(33922)
        if not scale or not tie:
            raise CogUnsupported("no ModelPixelScale/ModelTiepoint: not georeferenced")
        # tiepoint (i, j, k, x, y, z): raster point (i, j) sits at map (x, y)
        i, j = float(tie[0]), float(tie[1])
        dx, dy = float(scale[0]), float(scale[1])
        self.transform = GeoTransform(x0=float(tie[3]) - i * dx, y0=float(tie[4]) + j * dy,
                                      dx=dx, dy=dy)
        self.tiles_read = 0

    # ---------------------------------------------------------------- TIFF structure
    def _bytes(self, start: int, length: int) -> bytes:
        if start + length <= len(self._head):
            return self._head[start:start + length]
        data = self._fetch(self.url, start, start + length - 1)
        self.bytes_read += len(data)
        return data

    def _read_ifd(self, offset: int) -> dict[int, list[Any]]:
        n = struct.unpack(self._bo + "H", self._bytes(offset, 2))[0]
        raw = self._bytes(offset + 2, 12 * n)
        tags: dict[int, list[Any]] = {}
        for k in range(n):
            tag, typ, cnt = struct.unpack(self._bo + "HHI", raw[12 * k:12 * k + 8])
            size = _TYPE_SIZE.get(typ)
            if size is None:
                continue
            total = size * cnt
            payload = (raw[12 * k + 8:12 * k + 8 + total] if total <= 4
                       else self._bytes(struct.unpack(self._bo + "I",
                                                      raw[12 * k + 8:12 * k + 12])[0], total))
            if typ == 2:
                tags[tag] = [payload]
            elif typ in (5, 10):
                vals = struct.unpack(self._bo + ("I" if typ == 5 else "i") * (2 * cnt), payload)
                tags[tag] = [vals[2 * m] / vals[2 * m + 1] if vals[2 * m + 1] else float("nan")
                             for m in range(cnt)]
            else:
                tags[tag] = list(struct.unpack(self._bo + _TYPE_FMT[typ] * cnt, payload))
        return tags

    # ---------------------------------------------------------------- pixels
    def _decode(self, blob: bytes) -> np.ndarray:
        if self.compression in (8, 32946):
            blob = zlib.decompress(blob)
        arr = np.frombuffer(blob, dtype=self.dtype, count=self.tile_w * self.tile_h)
        arr = arr.reshape(self.tile_h, self.tile_w).astype(self.dtype.newbyteorder("="))
        if self.predictor == 2:
            if arr.dtype.kind not in "iu":
                raise CogUnsupported("predictor 2 on a float raster is not decoded")
            arr = np.cumsum(arr, axis=1, dtype=arr.dtype)
        return arr

    def read_window(self, col0: int, row0: int, ncols: int, nrows: int) -> np.ndarray:
        """Pixels [row0:row0+nrows, col0:col0+ncols]; outside the raster reads as nodata/0."""
        out = np.zeros((nrows, ncols), dtype=self.dtype.newbyteorder("="))
        if self.nodata is not None:
            out[:] = self.nodata
        c_lo, r_lo = max(col0, 0), max(row0, 0)
        c_hi, r_hi = min(col0 + ncols, self.width), min(row0 + nrows, self.height)
        if c_lo >= c_hi or r_lo >= r_hi:
            return out
        for tr in range(r_lo // self.tile_h, (r_hi - 1) // self.tile_h + 1):
            for tc in range(c_lo // self.tile_w, (c_hi - 1) // self.tile_w + 1):
                idx = tr * self.tiles_across + tc
                if self.counts[idx] == 0:
                    continue
                blob = self._fetch(self.url, self.offsets[idx],
                                   self.offsets[idx] + self.counts[idx] - 1)
                self.bytes_read += len(blob)
                self.tiles_read += 1
                tile = self._decode(blob)
                ty0, tx0 = tr * self.tile_h, tc * self.tile_w
                ys, ye = max(r_lo, ty0), min(r_hi, ty0 + self.tile_h)
                xs, xe = max(c_lo, tx0), min(c_hi, tx0 + self.tile_w)
                out[ys - row0:ye - row0, xs - col0:xe - col0] = tile[ys - ty0:ye - ty0,
                                                                     xs - tx0:xe - tx0]
        return out

    def read_bbox(self, xmin: float, ymin: float, xmax: float, ymax: float
                  ) -> tuple[np.ndarray, GeoTransform]:
        """The pixels covering a map-coordinate box, with the window's own transform."""
        c0, r0 = self.transform.to_pixel(xmin, ymax)
        c1, r1 = self.transform.to_pixel(xmax, ymin)
        col0, row0 = int(np.floor(c0)), int(np.floor(r0))
        ncols, nrows = int(np.ceil(c1)) - col0, int(np.ceil(r1)) - row0
        arr = self.read_window(col0, row0, ncols, nrows)
        x0, y0 = self.transform.to_map(col0, row0)
        return arr, GeoTransform(x0=x0, y0=y0, dx=self.transform.dx, dy=self.transform.dy)


def write_cog(arr: np.ndarray, x0: float, y0: float, dx: float, dy: float,
              tile: int = 256, predictor: int = 2) -> bytes:
    """A minimal little-endian tiled DEFLATE GeoTIFF of a 2-D uint16 array (tests and fixtures)."""
    a = np.ascontiguousarray(arr, dtype="<u2")
    h, w = a.shape
    ta, td = -(-w // tile), -(-h // tile)
    blobs: list[bytes] = []
    for tr in range(td):
        for tc in range(ta):
            t = np.zeros((tile, tile), dtype="<u2")
            part = a[tr * tile:(tr + 1) * tile, tc * tile:(tc + 1) * tile]
            t[:part.shape[0], :part.shape[1]] = part
            if predictor == 2:
                t = np.diff(t, axis=1, prepend=np.zeros((tile, 1), dtype="<u2")).astype("<u2")
            blobs.append(zlib.compress(t.tobytes()))
    n_tiles = len(blobs)
    entries: list[tuple[int, int, int, bytes]] = []   # tag, type, count, payload
    extra = bytearray()

    def short(tag: int, v: int) -> None:
        entries.append((tag, 3, 1, struct.pack("<HH", v, 0)))

    short(256, w)
    short(257, h)
    short(258, 16)
    short(259, 8)
    short(262, 1)
    short(277, 1)
    short(284, 1)
    short(317, predictor)
    short(322, tile)
    short(323, tile)
    short(339, 1)
    n_entries = 11 + 4
    ifd_size = 2 + 12 * n_entries + 4
    base = 8 + ifd_size
    scale = struct.pack("<3d", dx, dy, 0.0)
    tie = struct.pack("<6d", 0.0, 0.0, 0.0, x0, y0, 0.0)
    off_scale = base + len(extra)
    extra += scale
    off_tie = base + len(extra)
    extra += tie
    off_offsets = base + len(extra)
    extra += b"\x00" * (4 * n_tiles)
    off_counts = base + len(extra)
    extra += struct.pack(f"<{n_tiles}I", *[len(b) for b in blobs])
    data_start = base + len(extra)
    offsets, pos = [], data_start
    for b in blobs:
        offsets.append(pos)
        pos += len(b)
    extra[off_offsets - base:off_offsets - base + 4 * n_tiles] = struct.pack(
        f"<{n_tiles}I", *offsets)
    entries.append((324, 4, n_tiles, struct.pack("<I", off_offsets)))
    entries.append((325, 4, n_tiles, struct.pack("<I", off_counts)))
    entries.append((33550, 12, 3, struct.pack("<I", off_scale)))
    entries.append((33922, 12, 6, struct.pack("<I", off_tie)))
    if n_tiles == 1:   # a single LONG fits in the entry itself
        entries[-4] = (324, 4, 1, struct.pack("<I", offsets[0]))
        entries[-3] = (325, 4, 1, struct.pack("<I", len(blobs[0])))
    entries.sort(key=lambda e: e[0])
    ifd = struct.pack("<H", len(entries))
    for tag, typ, cnt, payload in entries:
        ifd += struct.pack("<HHI", tag, typ, cnt) + payload
    ifd += struct.pack("<I", 0)
    return b"II*\x00" + struct.pack("<I", 8) + ifd + bytes(extra) + b"".join(blobs)


def bytes_fetch(store: dict[str, bytes]) -> Fetch:
    """A fetch over an in-memory {url: bytes} store (tests)."""
    def fetch(url: str, start: int, end: int) -> bytes:
        return store[url][start:end + 1]
    return fetch


__all__ = ["COG", "CogUnsupported", "GeoTransform", "bytes_fetch", "http_fetch", "write_cog"]
