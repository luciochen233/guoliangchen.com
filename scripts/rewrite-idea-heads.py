#!/usr/bin/env python3
"""
rewrite-idea-heads.py — Ensure every ideas/**/*.html has a complete SEO <head>.

Two page kinds:

  1. Listing pages (og:type=website)
     - /ideas/index.html
     - /ideas/{year}W{week}/index.html (one per week)

     Title: "Ideas — lucioclaw_" or "Ideas {week} — lucioclaw_"
     Description: static summary text (listing pages are noisy to auto-summarize)

  2. Individual idea pages (og:type=article)
     - /ideas/{year}W{week}/{num}-{slug}.html

     Title: "Idea #{num}: {title} — lucioclaw_"
     Description: extracted from the first <p> in <div class="content">

The script is idempotent via marker comments:
  - LISTING_MARKER for listing pages
  - IDEA_MARKER for individual idea pages

Run:
  python3 scripts/rewrite-idea-heads.py            # rewrite in place
  python3 scripts/rewrite-idea-heads.py --dry-run   # show what would change
  python3 scripts/rewrite-idea-heads.py --verbose   # per-file output
"""
import argparse
import re
import sys
from pathlib import Path

SITE_DIR = Path("/var/www/guoliangchen.com")
IDEAS_DIR = SITE_DIR / "ideas"
SITE_URL = "https://guoliangchen.com"
OG_IMAGE = f"{SITE_URL}/assets/clawy-self-portrait.png"

# Markers (must not collide with rewrite-post-heads.py markers)
LISTING_MARKER = "<!-- seo-listing:rewrite-idea-heads.py v1 -->"
IDEA_MARKER = "<!-- seo-idea:rewrite-idea-heads.py v1 -->"

# Limits
MAX_DESC_LEN = 200
MIN_DESC_LEN = 40

# Static descriptions for listing pages
MAIN_LISTING_DESC = (
    "A continuously-updated idea log by lucioclaw_ — short, sharp notes on "
    "biology, physics, computing, materials, and weird cross-domain research directions. "
    "Grouped by ISO week."
)


def _decode_entities(s: str) -> str:
    import html as _html_mod
    return _html_mod.unescape(s)


def html_attr_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def extract_first_p(html: str) -> str:
    """First <p> in <div class="content"> (or first <p> overall), stripped of tags.
    Skips nav/back-link paragraphs and meta-date lines like 'Date: 2026-03-24 ...'."""
    m = re.search(
        r'<div\s+class="content">(.*?)</div>',
        html,
        flags=re.DOTALL | re.IGNORECASE,
    )
    body = m.group(1) if m else html

    for pm in re.finditer(r"<p([^>]*)>(.*?)</p>", body, flags=re.DOTALL | re.IGNORECASE):
        attrs = pm.group(1) or ""
        text = re.sub(r"<[^>]+>", "", pm.group(2))
        text = _decode_entities(text)
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        lower = text.lower()
        if lower in {"← home", "← back", "← back to posts", "back", "home", "—", "-", "*"}:
            continue
        if text.startswith(("←", "«", "‹", "back", "return", "home")) and len(text) < 30:
            continue
        if 'class="meta"' in attrs:
            continue
        # Skip "Date: 2026-03-24" or "Date: 2026-03-24  Found: ..." style preambles
        if re.match(r"^Date:\s*\d{4}-\d{2}-\d{2}", text, flags=re.IGNORECASE):
            continue
        if text == "—" or text == "*" or text == "-":
            continue
        return text
    return ""


def shorten(text: str, max_len: int = MAX_DESC_LEN) -> str:
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    sp = cut.rfind(" ")
    if sp > max_len * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,;:.-—") + "…"


def strip_existing_meta(head_inner: str) -> str:
    """Remove previous canonical / og / twitter / idea-marker lines so we can re-insert cleanly."""
    head_inner = re.sub(
        r"<!--\s*seo-(?:listing|idea):rewrite-idea-heads\.py[^\n]*\n(?:  .*\n)*",
        "",
        head_inner,
        flags=re.MULTILINE,
    )
    head_inner = re.sub(
        r'<link\s+rel="canonical"[^>]*>\s*\n?',
        "",
        head_inner,
        flags=re.IGNORECASE,
    )
    head_inner = re.sub(
        r'<meta\s+(?:property|name)="og:[^"]+"[^>]*>\s*\n?',
        "",
        head_inner,
        flags=re.IGNORECASE,
    )
    head_inner = re.sub(
        r'<meta\s+name="twitter:[^"]+"[^>]*>\s*\n?',
        "",
        head_inner,
        flags=re.IGNORECASE,
    )
    return head_inner


def extract_title(head: str) -> str:
    m = re.search(r"<title>(.*?)</title>", head, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else ""


def og_title_from_title(title: str) -> str:
    """Strip ' — lucioclaw_' suffix (used for og/twitter title)."""
    suffix = " — lucioclaw_"
    if title.endswith(suffix):
        return title[: -len(suffix)]
    return title


def build_listing_block(title: str, description: str, canonical: str) -> str:
    title_esc = html_attr_escape(og_title_from_title(title))
    desc_esc = html_attr_escape(description)
    return "\n  ".join([
        LISTING_MARKER,
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="description" content="{desc_esc}">',
        f'<meta property="og:title" content="{title_esc}">',
        f'<meta property="og:description" content="{desc_esc}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="website">',
        f'<meta property="og:site_name" content="lucioclaw_">',
        f'<meta property="og:locale" content="en_US">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{title_esc}">',
        f'<meta name="twitter:description" content="{desc_esc}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
    ])


def build_idea_block(title: str, description: str, canonical: str) -> str:
    title_esc = html_attr_escape(og_title_from_title(title))
    desc_esc = html_attr_escape(description)
    return "\n  ".join([
        IDEA_MARKER,
        f'<link rel="canonical" href="{canonical}">',
        f'<meta name="description" content="{desc_esc}">',
        f'<meta property="og:title" content="{title_esc}">',
        f'<meta property="og:description" content="{desc_esc}">',
        f'<meta property="og:url" content="{canonical}">',
        f'<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="lucioclaw_">',
        f'<meta property="og:locale" content="en_US">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        f'<meta name="twitter:card" content="summary">',
        f'<meta name="twitter:title" content="{title_esc}">',
        f'<meta name="twitter:description" content="{desc_esc}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
    ])


def week_listing_description(week: str) -> str:
    return (
        f"Ideas collected by lucioclaw_ in {week} — short notes on biology, physics, "
        f"computing, materials, and weird cross-domain research directions."
    )


def rewrite_listing_page(path: Path, html: str, dry_run: bool) -> tuple[str, str]:
    """Handle /ideas/index.html and /ideas/{week}/index.html."""
    if LISTING_MARKER in html:
        return "skipped-marker", "listing page already has meta"

    head_match = re.search(r"<head>(.*?)</head>", html, flags=re.DOTALL | re.IGNORECASE)
    if not head_match:
        return "skipped-no-head", "no <head> block found"
    head_inner = head_match.group(1)
    title = extract_title(head_inner)
    if not title:
        return "skipped-no-title", "no <title> found"

    # Compute canonical URL from the file's path
    rel = path.relative_to(SITE_DIR).parent.as_posix()  # "ideas" or "ideas/26W23"
    canonical = f"{SITE_URL}/{rel}/"
    # Static description: main vs weekly
    if rel == "ideas":
        description = MAIN_LISTING_DESC
    else:
        # rel looks like "ideas/26W23"
        week = rel.split("/")[-1]
        description = week_listing_description(week)

    block = build_listing_block(title, description, canonical)
    cleaned_head_inner = strip_existing_meta(head_inner)
    lines = [ln for ln in cleaned_head_inner.split("\n") if ln.strip()]
    cleaned_normalized = "\n".join(lines)
    new_head_full = "<head>\n" + cleaned_normalized + "\n\n  " + block + "\n</head>"
    new_html = html[: head_match.start()] + new_head_full + html[head_match.end():]

    if new_html == html:
        return "skipped-no-change", "no change after listing rewrite"
    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return "rewritten", f"listing rel={rel} desc={description[:50]!r}"


def rewrite_idea_page(path: Path, html: str, dry_run: bool) -> tuple[str, str]:
    """Handle /ideas/{week}/{num}-{slug}.html."""
    if IDEA_MARKER in html:
        return "skipped-marker", "idea page already has meta"

    head_match = re.search(r"<head>(.*?)</head>", html, flags=re.DOTALL | re.IGNORECASE)
    if not head_match:
        return "skipped-no-head", "no <head> block found"
    head_inner = head_match.group(1)
    title = extract_title(head_inner)
    if not title:
        return "skipped-no-title", "no <title> found"

    # Get canonical URL from filename
    rel = path.relative_to(SITE_DIR).as_posix()  # "ideas/26W23/1-foo.html"
    canonical = f"{SITE_URL}/{rel}"

    # Description: prefer existing <meta name="description"> only if it's clearly real
    # (substantively different from the title, not just a stripped/shorter title repeat).
    # The build-ideas.py template currently sets description = title, so most existing
    # meta is title-only and we should regenerate from the body.
    desc_m = re.search(
        r'<meta\s+name="description"\s+content="([^"]*)"',
        head_inner,
        flags=re.IGNORECASE,
    )
    existing_desc = (desc_m.group(1).strip() if desc_m else "")
    og_title = og_title_from_title(title)
    looks_like_title_repeat = (
        existing_desc == og_title
        or existing_desc == title
        or (len(existing_desc) <= 60 and existing_desc in title)
    )
    if existing_desc and not looks_like_title_repeat and len(existing_desc) >= MIN_DESC_LEN:
        description = existing_desc
    else:
        first_p = extract_first_p(html)
        if not first_p:
            return "skipped-no-p", "no <p> found in body to generate description"
        description = shorten(first_p)

    block = build_idea_block(title, description, canonical)
    cleaned_head_inner = strip_existing_meta(head_inner)
    lines = [ln for ln in cleaned_head_inner.split("\n") if ln.strip()]
    cleaned_normalized = "\n".join(lines)
    new_head_full = "<head>\n" + cleaned_normalized + "\n\n  " + block + "\n</head>"
    new_html = html[: head_match.start()] + new_head_full + html[head_match.end():]

    if new_html == html:
        return "skipped-no-change", "no change after idea rewrite"
    if not dry_run:
        path.write_text(new_html, encoding="utf-8")
    return "rewritten", f"title={title[:40]!r} desc={description[:50]!r}"


def route(path: Path) -> str:
    """Return 'listing' or 'idea' based on file location relative to ideas/."""
    rel = path.relative_to(IDEAS_DIR)
    # rel.parts is like ('26W23', 'index.html') for week index, ('26W23', '1-foo.html')
    # for idea page, or ('index.html',) for main listing.
    if len(rel.parts) == 1 and rel.parts[0] == "index.html":
        return "listing"
    if len(rel.parts) == 2 and rel.parts[1] == "index.html":
        return "listing"
    return "idea"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    if not IDEAS_DIR.is_dir():
        print(f"error: {IDEAS_DIR} not found", file=sys.stderr)
        return 1

    files = sorted(IDEAS_DIR.rglob("*.html"))
    if not files:
        print("no idea files found", file=sys.stderr)
        return 1

    counts = {
        "rewritten": 0, "skipped-marker": 0, "skipped-no-head": 0,
        "skipped-no-title": 0, "skipped-no-p": 0, "skipped-no-change": 0,
    }

    for f in files:
        html = f.read_text(encoding="utf-8")
        kind = route(f)
        if kind == "listing":
            status, detail = rewrite_listing_page(f, html, dry_run=args.dry_run)
        else:
            status, detail = rewrite_idea_page(f, html, dry_run=args.dry_run)
        counts[status] = counts.get(status, 0) + 1
        if args.verbose:
            print(f"{kind:8s} {status:20s}  {f.relative_to(SITE_DIR)}  {detail}")

    print(
        f"scanned {len(files)} idea files "
        f"(dry_run={args.dry_run}): " +
        ", ".join(f"{k}={v}" for k, v in counts.items() if v)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
