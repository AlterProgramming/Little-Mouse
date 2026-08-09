#!/usr/bin/env python3
"""Recover media response bodies embedded in a HAR file.

Designed for browser HAR captures where media is fetched in HTTP byte ranges.
The script never needs cookies or browser credentials: it reconstructs only bytes
already present in the HAR response bodies.
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

RANGE_QUERY_KEYS = {"bytestart", "byteend", "start", "end", "range"}
MEDIA_MIME_PREFIXES = ("video/", "audio/", "image/")
CONTENT_RANGE_RE = re.compile(r"bytes\s+(\d+)-(\d+)/(?:\d+|\*)", re.I)


@dataclass
class Chunk:
    asset_key: str
    source_url: str
    normalized_url: str
    mime: str
    start: int
    end: int
    data: bytes


def headers_dict(headers: Iterable[dict]) -> dict[str, str]:
    return {
        str(h.get("name", "")).lower(): str(h.get("value", ""))
        for h in headers or []
        if h.get("name")
    }


def normalized_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in RANGE_QUERY_KEYS
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def asset_key(url: str) -> str:
    n = normalized_url(url)
    parts = urlsplit(n)
    stem = Path(parts.path).name or "media"
    digest = hashlib.sha256(n.encode("utf-8")).hexdigest()[:12]
    return f"{stem}-{digest}"


def range_from_entry(entry: dict, data_len: int) -> tuple[int, int]:
    response = entry.get("response", {})
    headers = headers_dict(response.get("headers", []))
    m = CONTENT_RANGE_RE.search(headers.get("content-range", ""))
    if m:
        return int(m.group(1)), int(m.group(2))

    url = entry.get("request", {}).get("url", "")
    q = {k.lower(): v for k, v in parse_qsl(urlsplit(url).query, keep_blank_values=True)}
    if q.get("bytestart", "").isdigit():
        start = int(q["bytestart"])
        if q.get("byteend", "").isdigit():
            return start, int(q["byteend"])
        return start, start + max(data_len - 1, 0)

    return 0, max(data_len - 1, 0)


def decode_body(content: dict) -> bytes | None:
    text = content.get("text")
    if text is None:
        return None
    encoding = str(content.get("encoding", "")).lower()
    if encoding == "base64":
        try:
            return base64.b64decode(text, validate=False)
        except Exception:
            return None
    return str(text).encode("utf-8")


def choose_extension(mime: str, url: str) -> str:
    path_ext = Path(urlsplit(url).path).suffix
    if path_ext and len(path_ext) <= 8:
        return path_ext
    preferred = {
        "video/mp4": ".mp4",
        "audio/mp4": ".m4a",
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    return preferred.get(mime, mimetypes.guess_extension(mime) or ".bin")


def contiguous_coverage(chunks: list[Chunk]) -> tuple[int, list[tuple[int, int]]]:
    spans = sorted((c.start, c.end) for c in chunks)
    if not spans:
        return 0, []
    gaps: list[tuple[int, int]] = []
    cursor = 0
    for start, end in spans:
        if end < cursor:
            continue
        if start > cursor:
            gaps.append((cursor, start - 1))
            cursor = end + 1
        else:
            cursor = max(cursor, end + 1)
    return cursor, gaps


def reconstruct(chunks: list[Chunk]) -> tuple[bytes | None, int, list[tuple[int, int]], bool]:
    chunks = sorted(chunks, key=lambda c: (c.start, c.end))
    max_end = max(c.end for c in chunks)
    covered_to, gaps = contiguous_coverage(chunks)
    complete_from_zero = bool(chunks) and chunks[0].start == 0 and not gaps
    if not complete_from_zero:
        return None, covered_to, gaps, False

    out = bytearray(max_end + 1)
    seen = bytearray(max_end + 1)
    conflict = False
    for chunk in chunks:
        expected = min(chunk.end - chunk.start + 1, len(chunk.data))
        for i in range(expected):
            pos = chunk.start + i
            if seen[pos] and out[pos] != chunk.data[i]:
                conflict = True
            out[pos] = chunk.data[i]
            seen[pos] = 1

    if not all(seen):
        return None, covered_to, gaps, conflict
    return bytes(out), len(out), gaps, conflict


def main() -> int:
    ap = argparse.ArgumentParser(description="Recover embedded media from HAR response bodies")
    ap.add_argument("har", type=Path, help="Input .har file")
    ap.add_argument("-o", "--output", type=Path, default=Path("har-media"), help="Output directory")
    ap.add_argument("--mime", action="append", default=[], help="Optional MIME prefix/filter, e.g. video/mp4")
    ap.add_argument("--write-urls", action="store_true", help="Include normalized source URLs in manifest (may be signed/temporary)")
    args = ap.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    with args.har.open("r", encoding="utf-8") as f:
        har = json.load(f)

    filters = tuple(args.mime) if args.mime else MEDIA_MIME_PREFIXES
    groups: dict[str, list[Chunk]] = {}

    for entry in har.get("log", {}).get("entries", []):
        response = entry.get("response", {})
        content = response.get("content", {}) or {}
        mime = str(content.get("mimeType", "") or "").split(";", 1)[0].strip().lower()
        if not mime or not any(mime.startswith(f) if f.endswith("/") else mime == f for f in filters):
            continue
        data = decode_body(content)
        if data is None:
            continue
        url = str(entry.get("request", {}).get("url", ""))
        if not url:
            continue
        start, end = range_from_entry(entry, len(data))
        actual_end = start + max(len(data) - 1, 0)
        if actual_end != end:
            end = actual_end
        key = asset_key(url)
        groups.setdefault(key, []).append(Chunk(key, url, normalized_url(url), mime, start, end, data))

    rows: list[dict[str, object]] = []
    written = 0
    for index, (_, chunks) in enumerate(sorted(groups.items()), 1):
        mime = chunks[0].mime
        ext = choose_extension(mime, chunks[0].source_url)
        recovered, covered, gaps, conflict = reconstruct(chunks)
        status = "recovered" if recovered is not None else "incomplete"
        filename = ""
        sha256 = ""
        byte_count = 0
        if recovered is not None:
            filename = f"media_{index:03d}{ext}"
            path = args.output / filename
            path.write_bytes(recovered)
            byte_count = len(recovered)
            sha256 = hashlib.sha256(recovered).hexdigest()
            written += 1

        row = {
            "asset": index,
            "status": status,
            "mime": mime,
            "chunks": len(chunks),
            "bytes": byte_count,
            "covered_from_zero": covered,
            "gaps": ";".join(f"{a}-{b}" for a, b in gaps),
            "overlap_conflict": str(bool(conflict)).lower(),
            "filename": filename,
            "sha256": sha256,
        }
        if args.write_urls:
            row["normalized_url"] = chunks[0].normalized_url
        rows.append(row)

    fields = list(rows[0].keys()) if rows else [
        "asset", "status", "mime", "chunks", "bytes", "covered_from_zero", "gaps",
        "overlap_conflict", "filename", "sha256"
    ]
    with (args.output / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"HAR entries: {len(har.get('log', {}).get('entries', []))}")
    print(f"Media assets with embedded bodies: {len(groups)}")
    print(f"Recovered contiguous assets: {written}")
    print(f"Manifest: {args.output / 'manifest.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
