#!/usr/bin/env python3
"""
rebuild-sitemap.py — Generate sitemap.xml from real on-disk mtimes.

Walks the site tree and emits one <url> per indexable HTML file, with
<lastmod> set to the file's actual mtime. Replaces the hand-maintained
sitemap (which was frozen at 2026-03-23) and adds ideas/ + index pages
that were previously missing.

Rules:
- Skips files in __pycache__ and dotfiles.
- Skips 404.html / error pages if present.
- Sorts URLs: homepage first, then alphabetical. Stable ordering helps
  diffs stay readable.
- Output is written atomically (write to .tmp, rename).
"""
import os
import sys
from datetime import datetime, timezone

SITE_DIR = "/var/www/guoliangchen.com"
SITE_URL = "https://guoliangchen.com"
OUTPUT = os.path.join(SITE_DIR, "sitemap.xml")

# Subtrees to include (relative to SITE_DIR, must be dirs of HTML files)
ROOTS = [
    "",            # homepage (index.html)
    "posts",       # all post HTMLs + posts/index.html
    "ideas",       # all idea HTMLs (week pages + per-idea pages)
]

# Files we never want in the sitemap
EXCLUDE_NAMES = {
    "404.html",
    "error.html",
    "500.html",
}


def iso_z(epoch: float) -> str:
    """Return ISO-8601 with 'Z' suffix (sitemap schema prefers this form)."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def collect_urls():
    """Yield (path_relative_to_site, mtime_epoch) for every indexable HTML."""
    seen = set()  # de-dupe in case a path shows up in two roots
    for sub in ROOTS:
        base = os.path.join(SITE_DIR, sub) if sub else SITE_DIR
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            # prune
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
            for fname in filenames:
                if not fname.endswith(".html"):
                    continue
                if fname in EXCLUDE_NAMES:
                    continue
                full = os.path.join(dirpath, fname)
                rel = os.path.relpath(full, SITE_DIR)
                if rel in seen:
                    continue
                seen.add(rel)
                yield rel, os.path.getmtime(full)


def sort_key(item):
    """Homepage first, then alphabetical by URL path."""
    rel, _ = item
    # '/' < anything else lexicographically, which puts homepage first
    url_path = "/" + rel.replace(os.sep, "/")
    return (0 if rel == "index.html" else 1, url_path)


def render(urls):
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for rel, mtime in urls:
        url_path = "/" + rel.replace(os.sep, "/")
        # collapse index.html → directory URL (canonical form)
        if url_path.endswith("/index.html"):
            url_path = url_path[:-len("index.html")]
        loc = SITE_URL + url_path
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{iso_z(mtime)}</lastmod>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def main():
    items = list(collect_urls())
    items.sort(key=sort_key)
    xml = render(items)

    # Atomic write: .tmp then rename
    tmp = OUTPUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(xml)
    os.replace(tmp, OUTPUT)

    # Self-report
    print(f"sitemap: {len(items)} URLs -> {OUTPUT}")
    if items:
        newest = max(items, key=lambda x: x[1])
        oldest = min(items, key=lambda x: x[1])
        print(f"  newest: {newest[0]}  ({iso_z(newest[1])})")
        print(f"  oldest: {oldest[0]}  ({iso_z(oldest[1])})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
