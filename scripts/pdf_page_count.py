#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any


DICT_PATTERN = re.compile(rb"<<(?:(?!<<|>>).){0,5000}>>", re.S)
COUNT_PATTERN = re.compile(rb"/Count\s+([0-9]+)\b")
TYPE_PAGES_PATTERN = re.compile(rb"/Type\s*/Pages\b")
TYPE_PAGE_PATTERN = re.compile(rb"/Type\s*/Page\b(?!s)")


class PageCountError(RuntimeError):
    pass


def _stream_slices(data: bytes) -> list[tuple[bytes, bytes]]:
    slices: list[tuple[bytes, bytes]] = []
    for match in re.finditer(rb"<<(?P<dict>.*?)>>\s*stream(?:\r\n|\n|\r)", data, re.S):
        start = match.end()
        end = data.find(b"endstream", start)
        if end == -1:
            continue
        stream = data[start:end]
        if stream.endswith(b"\r\n"):
            stream = stream[:-2]
        elif stream.endswith((b"\n", b"\r")):
            stream = stream[:-1]
        slices.append((match.group("dict"), stream))
    return slices


def _inflate_pdf_streams(data: bytes) -> bytes:
    chunks = [data]
    for stream_dict, stream in _stream_slices(data):
        if b"FlateDecode" not in stream_dict:
            continue
        try:
            chunks.append(zlib.decompress(stream))
        except zlib.error:
            continue
    return b"\n".join(chunks)


def count_pdf_pages(pdf_path: str | Path) -> int:
    path = Path(pdf_path)
    if not path.exists():
        raise PageCountError(f"PDF not found: {path}")
    if not path.is_file():
        raise PageCountError(f"PDF path is not a file: {path}")

    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise PageCountError(f"Not a PDF file: {path}")

    expanded = _inflate_pdf_streams(data)
    page_tree_counts: list[int] = []
    for dictionary in DICT_PATTERN.findall(expanded):
        if TYPE_PAGES_PATTERN.search(dictionary):
            count_match = COUNT_PATTERN.search(dictionary)
            if count_match:
                page_tree_counts.append(int(count_match.group(1)))

    if page_tree_counts:
        return page_tree_counts[-1]

    page_objects = TYPE_PAGE_PATTERN.findall(expanded)
    if page_objects:
        return len(page_objects)

    raise PageCountError(f"Could not determine page count for {path}")


def check_pdf_pages(pdf_path: str | Path, max_pages: int = 1) -> dict[str, Any]:
    page_count = count_pdf_pages(pdf_path)
    return {
        "pdf_path": str(Path(pdf_path).resolve()),
        "page_count": page_count,
        "page_limit": max_pages,
        "over_page_limit": page_count > max_pages,
    }


def emit(payload: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return
    for key, value in payload.items():
        print(f"{key}: {value}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check PDF page count without external dependencies")
    parser.add_argument("--pdf", required=True, help="PDF file to inspect")
    parser.add_argument("--max-pages", type=int, default=1, help="Maximum allowed pages")
    parser.add_argument("--json", action="store_true", help="Emit JSON")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        payload = check_pdf_pages(args.pdf, args.max_pages)
    except PageCountError as exc:
        payload = {
            "pdf_path": str(Path(args.pdf).resolve()),
            "page_limit": args.max_pages,
            "status": "failed",
            "error": str(exc),
        }
        emit(payload, as_json=args.json)
        return 2

    payload["status"] = "over-limit" if payload["over_page_limit"] else "ok"
    emit(payload, as_json=args.json)
    return 1 if payload["over_page_limit"] else 0


if __name__ == "__main__":
    sys.exit(main())
