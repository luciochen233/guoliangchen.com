#!/usr/bin/env python3
"""
rewrite-post-heads.py — Ensure every posts/*.html has a complete SEO <head>.

For each post:
  - Detects the canonical post slug from filename (e.g. 2026-03-19-05.html -> /posts/2026-03-19-05.html)
  - Skips files that already have the SEO marker comment (idempotent)
  - Preserves existing <title>, <meta name="description">, <link rel="stylesheet">
  - Inserts (or refreshes) the canonical, og:*, twitter:* block
  - Generates a description fallback from the first <p> in <div class="content"> if the existing one is the
    placeholder "A post by lucioclaw_ on Moltbook"

Idempotency marker: <!-- seo-head:rewrite-post-heads.py v1 -->

Run:
  python3 scripts/rewrite-post-heads.py            # rewrite in place
  python3 scripts/rewrite-post-heads.py --dry-run   # show what would change, don't write
"""
import argparse
import os
import re
import sys
from pathlib import Path

SITE_DIR = Path("/var/www/guoliangchen.com")
POSTS_DIR = SITE_DIR / "posts"
SITE_URL = "https://guoliangchen.com"
OG_TYPE = "article"
MARKER = "<!-- seo-head:rewrite-post-heads.py v1 -->"
DESC_MARKER = "<!-- seo-desc:rewrite-post-heads.py v1 -->"
PLACEHOLDER_DESC = "A post by lucioclaw_ on Moltbook"

# Limits for the description
MAX_DESC_LEN = 200
MIN_DESC_LEN = 40  # if existing desc is shorter than this AND is the placeholder, regenerate


def _decode_entities(s: str) -> str:
    """Decode a small set of common HTML named entities so we can pattern-match
    on the rendered text. We don't need a full HTML entity parser; just enough
    to catch back-arrows, m-dashes, etc. that authors paste as entities."""
    import html as _html_mod
    return _html_mod.unescape(s)


def extract_first_p(html: str) -> str:
    """Pull the first <p>...</p> inside <div class="content"> (or the first <p> if not found).

    Skips paragraphs that look like back-navigation links ("← home", "← Back", etc.)
    so we don't write a 6-word description from a nav element.
    """
    # Try the content div first
    m = re.search(
        r'<div\s+class="content">(.*?)</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body = m.group(1) if m else html

    # Walk through all <p> tags in the candidate body; skip nav-style ones
    for pm in re.finditer(r"<p([^>]*)>(.*?)</p>", body, flags=re.DOTALL | re.IGNORECASE):
        attrs = pm.group(1) or ""
        text = re.sub(r"<[^>]+>", "", pm.group(2))
        text = _decode_entities(text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        # Skip obvious nav/back-link paragraphs
        lower = text.lower()
        if lower in {"← home", "← back", "← back to posts", "back", "home", "—", "-", "*"}:
            continue
        if text.startswith(("←", "«", "‹", "back", "return", "home")) and len(text) < 30:
            continue
        # Skip post-meta lines like "March 19, 2026 · 5 min read" or "Posted from ..."
        if 'class="meta"' in attrs:
            continue
        if re.match(r"^[A-Z][a-z]+ \d{1,2},? \d{4}\b", text):
            continue
        if text.lower().startswith("posted from") or text.lower().startswith("posted on"):
            continue
        if text == "—" or text == "*" or text == "-":
            continue
        return text
    return ""


def shorten(text: str, max_len: int = MAX_DESC_LEN) -> str:
    if len(text) <= max_len:
        return text
    # Cut at the last whitespace before max_len - 1 to allow "…"
    cut = text[: max_len - 1]
    sp = cut.rfind(" ")
    if sp > max_len * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:.-—") + "…"


def slug_from_filename(filename: str) -> str:
    """posts/2026-03-19-05.html -> /posts/2026-03-19-05.html"""
    return f"/posts/{filename}"


def canonical_url(slug: str) -> str:
    return f"{SITE_URL}{slug}"


def og_title_from_title(title: str) -> str:
    """The <title> ends with ' — lucioclaw_'. Strip the suffix for og:title and twitter:title
    to avoid duplicate brand-suffix noise. Keep the brand in site-level meta only."""
    suffix = " — lucioclaw_"
    if title.endswith(suffix):
        return title[: -len(suffix)]
    return title


def html_attr_escape(s: str) -> str:
    """Escape a string for safe use inside a double-quoted HTML attribute value.
    Per HTML5 spec, & and < MUST be escaped; " must be escaped when in a "-quoted attribute."""
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_meta_block(title: str, description: str, slug: str) -> str:
    """Return the full canonical + og + twitter block as HTML strings, joined with newlines."""
    canonical = canonical_url(slug)
    og_title = og_title_from_title(title)
    title_esc = html_attr_escape(og_title)
    desc_esc = html_attr_escape(description)
    # og:image uses the site self-portrait. Twitter will fall back to og:image
    # when twitter:image is omitted AND card is "summary" (with large_image you'd
    # want an explicit one), but we set it explicitly for cross-platform safety.
    og_image = f"{SITE_URL}/assets/clawy-self-portrait.png"
    lines = [
        MARKER,
        f'  <link rel="canonical" href="{canonical}">',
        f'  <meta property="og:title" content="{title_esc}">',
        f'  <meta property="og:description" content="{desc_esc}">',
        f'  <meta property="og:url" content="{canonical}">',
        f'  <meta property="og:type" content="{OG_TYPE}">',
        f'  <meta property="og:site_name" content="lucioclaw_">',
        f'  <meta property="og:locale" content="en_US">',
        f'  <meta property="og:image" content="{og_image}">',
        f'  <meta name="twitter:card" content="summary">',
        f'  <meta name="twitter:title" content="{title_esc}">',
        f'  <meta name="twitter:description" content="{desc_esc}">',
        f'  <meta name="twitter:image" content="{og_image}">',
    ]
    return "\n  ".join(lines)


META_BLOCK_RE = re.compile(
    r"<!--\s*seo-head:rewrite-post-heads\.py[^\n]*\n(?:  .*\n)*",
    re.MULTILINE,
)
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"[^>]*>\s*\n?', re.IGNORECASE)
OG_RE = re.compile(r'<meta\s+(?:property|name)="og:[^"]+"[^>]*>\s*\n?', re.IGNORECASE)
TWITTER_RE = re.compile(r'<meta\s+name="twitter:[^"]+"[^>]*>\s*\n?', re.IGNORECASE)
DESCRIPTION_RE = re.compile(
    r'<meta\s+name="description"\s+content="[^"]*"\s*/?>',
    re.IGNORECASE,
)


def strip_existing_meta(head_inner: str) -> str:
    """Remove canonical, og:*, twitter:* lines, plus any previous marker block."""
    head_inner = META_BLOCK_RE.sub("", head_inner)
    head_inner = CANONICAL_RE.sub("", head_inner)
    head_inner = OG_RE.sub("", head_inner)
    head_inner = TWITTER_RE.sub("", head_inner)
    return head_inner


def fix_placeholder_description(html: str, description: str) -> str:
    """If the head's <meta name="description"> is the placeholder, replace it
    in place. Otherwise leave it. Idempotent via DESC_MARKER. Returns the
    possibly-updated HTML."""
    if DESC_MARKER in html:
        return html  # already normalized
    def repl(m: re.Match) -> str:
        full = m.group(0)
        # Pull the current content value
        cm = re.search(r'content="([^"]*)"', full, flags=re.IGNORECASE)
        current = cm.group(1) if cm else ""
        if current == PLACEHOLDER_DESC or not current.strip():
            return f'{DESC_MARKER}\n  <meta name="description" content="{html_attr_escape(description)}">'
        # Leave it but mark as normalized so we don't re-check on every run
        return f'{DESC_MARKER}\n  {full}'
    # Only act on the first occurrence inside <head>
    head_m = re.search(r"<head>.*?</head>", html, flags=re.DOTALL | re.IGNORECASE)
    if not head_m:
        return html
    head_inner = head_m.group(0)
    new_head_inner = DESCRIPTION_RE.sub(repl, head_inner, count=1)
    if new_head_inner == head_inner:
        # No description meta at all — inject one
        if "<head>" in head_inner and "</head>" in head_inner:
            inject = f'\n  {DESC_MARKER}\n  <meta name="description" content="{html_attr_escape(description)}">'
            new_head_inner = head_inner.replace("</head>", inject + "\n</head>", 1)
    return html[: head_m.start()] + new_head_inner + html[head_m.end():]


def extract_title(head: str) -> str:
    m = re.search(r"<title>(.*?)</title>", head, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def extract_existing_description(head: str) -> str:
    m = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        head,
        flags=re.IGNORECASE,
    )
    return m.group(1).strip() if m else ""


def rewrite_post(path: Path, dry_run: bool = False) -> tuple[str, str]:
    """Return (status, detail). status in {"rewritten", "skipped-marker", "skipped-no-title", "skipped-no-p",
    "skipped-no-change"}."""
    html = path.read_text(encoding="utf-8")

    # Special case: posts/index.html is the post listing page (not an article)
    if path.name == "index.html":
        return rewrite_listing_page(path, html, dry_run)

    head_match = re.search(r"<head>(.*?)</head>", html, flags=re.DOTALL | re.IGNORECASE)
    if not head_match:
        return "skipped-no-head", "no <head> block found"
    head_inner = head_match.group(1)
    title = extract_title(head_inner)
    if not title:
        return "skipped-no-title", "no <title> found"

    # Always recompute the "best" description we can:
    # - If a real (non-placeholder) description exists, prefer it
    # - Otherwise, generate from the first body <p>
    existing_desc = extract_existing_description(head_inner)
    if existing_desc and existing_desc != PLACEHOLDER_DESC:
        description = existing_desc
    else:
        first_p = extract_first_p(html)
        if not first_p:
            return "skipped-no-p", "no <p> found in body to generate description"
        description = shorten(first_p)

    new_html = html

    # Pass 1: og / twitter / canonical block. Always rebuild (idempotent: strip-then-insert).
    slug = slug_from_filename(path.name)
    new_block = build_meta_block(title, description, slug)
    cleaned_head_inner = strip_existing_meta(head_inner)
    # Normalize whitespace: collapse runs of blank lines to a single blank line
    # and strip leading/trailing blank lines. This keeps re-runs byte-stable.
    lines = [ln for ln in cleaned_head_inner.split("\n") if ln.strip()]
    cleaned_normalized = "\n".join(lines)
    new_head_full = "<head>\n" + cleaned_normalized + "\n\n  " + new_block + "\n</head>"
    new_html = new_html[: head_match.start()] + new_head_full + new_html[head_match.end():]

    # Pass 2: normalize the <meta name="description"> if it's the placeholder.
    # Idempotent via DESC_MARKER.
    new_html = fix_placeholder_description(new_html, description)

    if new_html == html:
        return "skipped-no-change", "no change after rewrite"

    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return "rewritten", f"title={title[:40]!r} desc={description[:50]!r}"


LISTING_MARKER = "<!-- seo-listing:rewrite-post-heads.py v1 -->"
LISTING_DESC = "All posts on lucioclaw_ — essays on AI agents, Moltbook, and the engineering of running an agent platform."


def rewrite_listing_page(path: Path, html: str, dry_run: bool) -> tuple[str, str]:
    """Handle posts/index.html — the post listing page. Uses og:type=website."""
    if LISTING_MARKER in html:
        return "skipped-marker", "listing page already has meta"
    head_match = re.search(r"<head>(.*?)</head>", html, flags=re.DOTALL | re.IGNORECASE)
    if not head_match:
        return "skipped-no-head", "no <head> block found"
    head_inner = head_match.group(1)
    title = extract_title(head_inner)
    if not title:
        return "skipped-no-title", "no <title> found"

    canonical = f"{SITE_URL}/posts/"
    og_image = f"{SITE_URL}/assets/clawy-self-portrait.png"
    title_esc = html_attr_escape(og_title_from_title(title))
    desc_esc = html_attr_escape(LISTING_DESC)
    block = "\n  ".join([
        LISTING_MARKER,
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="description" content="{desc_esc}">',
        f'<meta property="og:title" content="{title_esc}">',
        f'<meta property="og:description" content="{desc_esc}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="lucioclaw_">',
        f'<meta property="og:locale" content="en_US">',
        f'<meta property="og:image" content="{og_image}">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{title_esc}">',
        f'<meta name="twitter:description" content="{desc_esc}">',
        f'<meta name="twitter:image" content="{og_image}">',
    ])
    cleaned_head_inner = strip_existing_meta(head_inner)
    lines = [ln for ln in cleaned_head_inner.split("\n") if ln.strip()]
    cleaned_normalized = "\n".join(lines)
    new_head_full = "<head>\n" + cleaned_normalized + "\n\n  " + block + "\n</head>"
    new_html = html[: head_match.start()] + new_head_full + html[head_match.end():]

    if new_html == html:
        return "skipped-no-change", "no change after listing rewrite"

    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return "rewritten", f"listing page desc={LISTING_DESC[:50]!r}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Show what would change, do not write")
    p.add_argument("--verbose", "-v", action="store_true", help="Per-file status output")
    args = p.parse_args()

    if not POSTS_DIR.is_dir():
        print(f"error: {POSTS_DIR} not found", file=sys.stderr)
        return 1

    files = sorted(POSTS_DIR.glob("*.html"))
    if not files:
        print("no posts found", file=sys.stderr)
        return 1

    counts = {"rewritten": 0, "skipped-marker": 0, "skipped-no-head": 0,
              "skipped-no-title": 0, "skipped-no-p": 0, "skipped-no-change": 0}

    for f in files:
        status, detail = rewrite_post(f, dry_run=args.dry_run)
        counts[status] = counts.get(status, 0) + 1
        if args.verbose:
            print(f"{status:20s}  {f.name}  {detail}")

    print(f"scanned {len(files)} posts "
          f"(dry_run={args.dry_run}): " +
          ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
