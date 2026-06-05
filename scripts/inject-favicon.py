#!/usr/bin/env python3
"""
inject-favicon.py — Idempotently inject <link rel="icon"> into every HTML page's <head>.

Why: avoids the browser-favicon 404 noise (and the lazy "incomplete" signal some
crawlers use) without requiring us to design an icon. favicon.ico at site root
is a 16x16 transparent PNG-as-ICO (see project notes).

Idempotence marker: <!-- favicon:inject-favicon.py v1 -->

Behavior:
  - If the marker is already present, the file is skipped (byte-stable on re-run).
  - If any existing <link rel="icon" ...> is present (e.g. a data: URI), it is
    replaced with the canonical /favicon.ico line, then the marker is added.
  - The link is inserted as the first child of <head>, right after <head>, so
    it's near other identity-level metadata.

Run: python3 scripts/inject-favicon.py [--root /var/www/guoliangchen.com]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

MARKER = "<!-- favicon:inject-favicon.py v1 -->"
FAVICON_LINK = '<link rel="icon" type="image/x-icon" href="/favicon.ico">'
SKIP_DIRS = {"__pycache__", ".git"}

def iter_html(root: Path):
    for p in sorted(root.rglob("*.html")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p

def transform(text: str) -> str | None:
    """Return new text, or None if no change needed."""
    if MARKER in text:
        return None  # already injected; byte-stable

    if not re.search(r"<head\b", text, re.IGNORECASE):
        return None  # no <head> to inject into

    # Replace any existing <link rel="icon" ...> (data: or otherwise) with the
    # canonical /favicon.ico line, and ensure marker is right after it.
    link_re = re.compile(
        r'<link\s+[^>]*rel\s*=\s*["\']icon["\'][^>]*>',
        re.IGNORECASE,
    )
    if link_re.search(text):
        new_text = link_re.sub(FAVICON_LINK, text, count=1)
        if MARKER not in new_text:
            new_text = new_text.replace(FAVICON_LINK, FAVICON_LINK + "\n" + MARKER, 1)
        return new_text

    # No existing favicon link — inject right after <head>.
    new_text = re.sub(
        r"(<head\b[^>]*>)",
        r"\1\n" + MARKER + "\n  " + FAVICON_LINK,
        text,
        count=1,
        flags=re.IGNORECASE,
    )
    return new_text

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/var/www/guoliangchen.com")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    root = Path(args.root)
    if not root.is_dir():
        print(f"root not a directory: {root}", file=sys.stderr)
        return 2

    changed = 0
    skipped = 0
    no_head = 0
    for p in iter_html(root):
        text = p.read_text(encoding="utf-8")
        new = transform(text)
        if new is None:
            if MARKER in text:
                skipped += 1
            else:
                no_head += 1
            continue
        if not args.dry_run:
            p.write_text(new, encoding="utf-8")
        changed += 1
        print(f"  + {p.relative_to(root)}")
    print(
        f"\ninject-favicon: changed={changed} already_ok={skipped} no_head={no_head} root={root}"
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
