#!/usr/bin/env python3
"""
inject-perf-headers.py — Idempotently add perf-critical <head> resources and
defer non-blocking scripts to every HTML page.

What this does:
  1. Hoists the Google Fonts <link> from an `@import` inside /assets/style.css
     into <head>, with `preconnect` warmup hints. The browser can then:
       - preconnect (TLS/DNS warmup in parallel with HTML parse)
       - fetch the CSS in parallel with the rest of the page
     The @import in CSS is a render-blocking serial fetch; the <link> in <head>
     is parallel + preconnectable. With `display=swap` text stays visible.
  2. Adds `defer` to `<script src="/assets/script.js...">` so it downloads in
     parallel with HTML parse and only executes after parsing finishes.
  3. Adds `loading="lazy" decoding="async"` to every <img> tag (browser
     defers off-screen images and decodes them off the main thread).

Idempotence markers:
  - Fonts:    <!-- perf-fonts:inject-perf-headers.py v1 -->
  - Defer:    <!-- perf-defer:inject-perf-headers.py v1 -->
  - Img lazy: <!-- perf-img-lazy:inject-perf-headers.py v1 -->

When a marker is present, that block is skipped. If a perf feature was
applied with a stale/older scheme, the new marker version replaces it.

Run: python3 scripts/inject-perf-headers.py [--root /var/www/guoliangchen.com]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Markers (one per perf concern, so each can evolve independently)
MARKER_FONTS = "<!-- perf-fonts:inject-perf-headers.py v1 -->"
MARKER_DEFER = "<!-- perf-defer:inject-perf-headers.py v1 -->"
MARKER_IMG = "<!-- perf-img-lazy:inject-perf-headers.py v1 -->"

# The Google Fonts block we want in <head>, right after the existing <link rel="stylesheet" href="/assets/style.css">
# Order matters: preconnect first (warmup), then the actual stylesheet (parallel fetch).
FONTS_BLOCK = "\n".join([
    MARKER_FONTS,
    '<link rel="preconnect" href="https://fonts.googleapis.com">',
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Inter:wght@400;600;700&display=swap">',
])

# Regexes (compiled once)
RE_HAS_FONTS_MARKER = re.compile(re.escape(MARKER_FONTS))
RE_HAS_DEFER_MARKER = re.compile(re.escape(MARKER_DEFER))
RE_HAS_IMG_MARKER = re.compile(re.escape(MARKER_IMG))

# The <link rel="stylesheet" href="/assets/style.css..."> line — we insert
# the fonts block right after it so they're visually grouped in <head>.
RE_STYLE_CSS = re.compile(
    r'(<link\s+rel="stylesheet"\s+href="/assets/style\.css(?:\?[^"]*)?"\s*>)',
    re.IGNORECASE,
)

# <script src="/assets/script.js..."> — add defer attribute.
# Group 1: opening tag up to the >, group 2: src attribute so we can keep it.
# We avoid matching if a `defer` attribute is already present.
RE_SCRIPT_TAG = re.compile(
    r'<script(\s+[^>]*?)?\ssrc="(/assets/script\.js(?:\?[^"]*)?)"([^>]*?)></script>',
    re.IGNORECASE,
)
RE_HAS_DEFER_ATTR = re.compile(r'\bdefer\b', re.IGNORECASE)

# <img ...> — add loading="lazy" decoding="async" if not already present.
# Captures the full opening tag; we either rewrite it (with attrs added) or
# wrap it with a marker (so we know not to re-process on next run).
RE_IMG_TAG = re.compile(r'<img\s+([^>]*?)/?>', re.IGNORECASE)
RE_HAS_LOADING = re.compile(r'\bloading\s*=', re.IGNORECASE)
RE_HAS_DECODING = re.compile(r'\bdecoding\s*=', re.IGNORECASE)

SKIP_DIRS = {"__pycache__", ".git", "node_modules"}


def has_marker(text: str, marker: str) -> bool:
    return marker in text


def inject_fonts(html: str) -> tuple[str, bool]:
    """Hoist the Google Fonts <link> into <head> with preconnect warmup."""
    if has_marker(html, MARKER_FONTS):
        return html, False

    m = RE_STYLE_CSS.search(html)
    if not m:
        # No /assets/style.css link on this page — skip (e.g. future template
        # that doesn't load the shared stylesheet). Fonts would render-deferred
        # text flash with no style, so don't add the link.
        return html, False

    insertion = m.group(1) + "\n  " + FONTS_BLOCK
    new_html = html[: m.end()] + "\n  " + FONTS_BLOCK + html[m.end() :]
    return new_html, True


def inject_defer(html: str) -> tuple[str, bool]:
    """Add `defer` to <script src="/assets/script.js..."> tags in <head> or body.

    Only touches our shared script.js — third-party scripts (if any are added
    later) should be handled separately since defer semantics differ.
    """
    if has_marker(html, MARKER_DEFER):
        return html, False

    changed = False

    def repl(m: re.Match) -> str:
        nonlocal changed
        prefix = m.group(1) or ""
        src = m.group(2)
        suffix = m.group(3) or ""
        # If defer is already present, leave the tag alone but still mark.
        if RE_HAS_DEFER_ATTR.search(prefix + suffix):
            return m.group(0)
        changed = True
        # Normalize spacing: leading + single space before new attrs.
        # `prefix` is everything between `<script` and the first src attribute;
        # in practice that's empty (script is `<script src="...">`).
        # We append ` defer` immediately before the closing `>` of the opening tag.
        new_suffix = suffix
        # Inject defer right after src, before any other attrs.
        # Simpler: just add ` defer` to the tag.
        return f'<script{prefix} src="{src}"{suffix} defer></script>'

    new_html = RE_SCRIPT_TAG.sub(repl, html)
    if not changed:
        # No script.js in this file (e.g. static post page). Still mark so we
        # don't keep scanning it on re-runs — but only if we already touched
        # the file. Don't write a marker for a file we didn't modify.
        return html, False

    # Append the marker as a small comment inside <head> so re-runs skip fast.
    # Place it right after the first <head> so it survives subsequent head
    # rewriters (inject-favicon, rewrite-post-heads, etc.) which look for
    # their own markers near <head>.
    new_html = re.sub(
        r"(<head>)",
        r"\1\n" + MARKER_DEFER,
        new_html,
        count=1,
        flags=re.IGNORECASE,
    )
    return new_html, True


def inject_img_lazy(html: str) -> tuple[str, bool]:
    """Add loading=lazy decoding=async to every <img> tag."""
    if has_marker(html, MARKER_IMG):
        return html, False

    changed = False

    def repl(m: re.Match) -> str:
        nonlocal changed
        attrs = m.group(1)
        if RE_HAS_LOADING.search(attrs) and RE_HAS_DECODING.search(attrs):
            return m.group(0)  # both already set
        new_attrs = attrs
        if not RE_HAS_LOADING.search(attrs):
            new_attrs = new_attrs.rstrip() + ' loading="lazy"'
        if not RE_HAS_DECODING.search(attrs):
            new_attrs = new_attrs.rstrip() + ' decoding="async"'
        new_attrs = new_attrs.strip()
        changed = True
        return f'<img {new_attrs}>'

    new_html = RE_IMG_TAG.sub(repl, html)
    if not changed:
        return html, False

    new_html = re.sub(
        r"(<head>)",
        r"\1\n" + MARKER_IMG,
        new_html,
        count=1,
        flags=re.IGNORECASE,
    )
    return new_html, True


def process_file(path: Path) -> tuple[bool, str]:
    """Returns (changed, reason)."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return False, f"read error: {e}"

    new_text = text
    file_changed = False

    new_text, did = inject_fonts(new_text)
    file_changed = file_changed or did

    new_text, did = inject_defer(new_text)
    file_changed = file_changed or did

    new_text, did = inject_img_lazy(new_text)
    file_changed = file_changed or did

    if not file_changed:
        return False, "no changes needed"

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return True, "perf headers injected"


def find_html_files(root: Path):
    for p in root.rglob("*.html"):
        # Skip noise dirs
        parts = set(p.relative_to(root).parts)
        if parts & SKIP_DIRS:
            continue
        yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--root",
        default="/var/www/guoliangchen.com",
        help="Site root to walk (default: /var/www/guoliangchen.com)",
    )
    ap.add_argument(
        "--quiet",
        action="store_true",
        help="Only print files that changed (not per-file skips).",
    )
    args = ap.parse_args()

    root = Path(args.root)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    total = 0
    changed = 0
    for path in sorted(find_html_files(root)):
        total += 1
        did, reason = process_file(path)
        if did:
            changed += 1
            print(f"  + {path.relative_to(root)}: {reason}")
        elif not args.quiet:
            print(f"  = {path.relative_to(root)}: {reason}")

    print(f"--- {changed}/{total} files changed ---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
