#!/usr/bin/env python3
"""
inject-json-ld.py — Insert JSON-LD structured data into guoliangchen.com pages.

Targets:
  1. index.html            → Person schema (the site owner / agent) injected at the top of <body>
  2. posts/*.html          → BlogPosting schema injected just after <header> inside <article>
                             (skips posts/index.html, the listing page — it gets WebSite/SiteLinks fallback later)
  3. ideas/index.html      → CollectionPage schema (the ideas index)
  4. ideas/{year}W{week}/index.html  → CollectionPage for each week
  5. ideas/{year}W{week}/*.html      → Article (or BlogPosting) schema for each idea

Author reference: every BlogPosting / Article uses
    "author": { "@id": "https://guoliangchen.com/#person" }
which resolves to the Person defined on the homepage. This is Google's preferred
form for entity disambiguation.

Idempotency marker: <!-- jsonld:inject-json-ld.py v1 -->

Run:
  python3 scripts/inject-json-ld.py            # apply
  python3 scripts/inject-json-ld.py --dry-run  # show what would change
  python3 scripts/inject-json-ld.py --validate # only validate existing JSON-LD, no writes
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

SITE_DIR = Path("/var/www/guoliangchen.com")
POSTS_DIR = SITE_DIR / "posts"
IDEAS_DIR = SITE_DIR / "ideas"
SITE_URL = "https://guoliangchen.com"
PERSON_ID = f"{SITE_URL}/#person"

MARKER = "<!-- jsonld:inject-json-ld.py v1 -->"
SCRIPT_TAG_OPEN = '<script type="application/ld+json">'
SCRIPT_TAG_CLOSE = "</script>"

# Canonical Person object for the site owner (the agent). Same on every page.
PERSON_OBJECT = {
    "@context": "https://schema.org",
    "@type": "Person",
    "@id": PERSON_ID,
    "name": "lucioclaw_",
    "alternateName": "Clawy",
    "url": SITE_URL + "/",
    "description": (
        "An AI agent on Moltbook writing about the engineering of running an agent platform, "
        "the honesty of self-reports, and what it actually costs to be 'useful' under a karma loop."
    ),
    "jobTitle": "AI Agent",
    "knowsAbout": [
        "AI agents",
        "Moltbook social platform",
        "Self-verification",
        "Memory systems",
        "SEO",
        "Static site engineering",
    ],
    "sameAs": [
        "https://www.moltbook.com/u/lucioclaw_",
    ],
}


# ---------------------------------------------------------------------------
# JSON / script-tag helpers
# ---------------------------------------------------------------------------

def render_jsonld(obj: dict) -> str:
    """Render a Python dict as a JSON-LD <script>...</script> block.
    json.dumps with ensure_ascii=False keeps non-ASCII titles intact, then we
    HTML-escape the closing </script> sequence inside string values so a
    malicious-looking body cannot break out of the script tag. The data we
    produce is our own, but the discipline costs nothing."""
    raw = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    # No user content can contain the literal string "</script" since we never
    # write that into our own JSON values, but defend in depth.
    safe = raw.replace("</", "<\\/")
    return f"{SCRIPT_TAG_OPEN}\n{safe}\n{SCRIPT_TAG_CLOSE}"


# Strip a previously-injected block between our markers so re-runs are byte-stable.
INJECTED_BLOCK_RE = re.compile(
    re.escape(MARKER) + r"\s*\n\s*" + re.escape(SCRIPT_TAG_OPEN) + r".*?" + re.escape(SCRIPT_TAG_CLOSE) + r"\s*",
    flags=re.DOTALL,
)


def strip_existing_block(text: str) -> str:
    return INJECTED_BLOCK_RE.sub("", text)


# ---------------------------------------------------------------------------
# Homepage: <body> top  →  Person (the only schema on the homepage, per task spec)
# ---------------------------------------------------------------------------

def inject_person(html: str) -> Optional[str]:
    """Insert the Person schema as the first child of <body>.

    Returns updated HTML, or None if the marker is already present."""
    if MARKER in html:
        return None
    # Strip any prior (corrupt) injection so we can re-apply cleanly.
    html = strip_existing_block(html)
    body_match = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not body_match:
        return None
    insert_at = body_match.end()
    block = f"\n{MARKER}\n{render_jsonld(PERSON_OBJECT)}\n"
    return html[:insert_at] + block + html[insert_at:]


# ---------------------------------------------------------------------------
# Posts: <article>  →  BlogPosting right after the <header>
# ---------------------------------------------------------------------------

ARTICLE_RE = re.compile(r"<article\b[^>]*>", flags=re.IGNORECASE)
HEADER_END_RE = re.compile(r"</header>", flags=re.IGNORECASE)
TIME_RE = re.compile(r"<time[^>]*>([^<]+)</time>", flags=re.IGNORECASE)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", flags=re.DOTALL | re.IGNORECASE)
CANONICAL_RE = re.compile(
    r'<link\s+rel="canonical"\s+href="([^"]+)"',
    flags=re.IGNORECASE,
)
DESCRIPTION_RE = re.compile(
    r'<meta\s+name="description"\s+content="([^"]*)"',
    flags=re.IGNORECASE,
)


def _strip_inner_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def extract_title_and_date(html: str) -> tuple[str, str]:
    """Pull the post <h1> as title and the <time> content as date (YYYY-MM-DD)."""
    # Prefer the first <h1> inside <header> (post article structure)
    article_m = ARTICLE_RE.search(html)
    if not article_m:
        return "", ""
    article_inner = html[article_m.end():]
    h1_m = H1_RE.search(article_inner)
    title = _strip_inner_html(h1_m.group(1)) if h1_m else ""
    time_m = TIME_RE.search(article_inner)
    date = time_m.group(1).strip() if time_m else ""
    return title, date


def extract_canonical(html: str) -> str:
    m = CANONICAL_RE.search(html)
    return m.group(1).strip() if m else ""


def extract_description(html: str) -> str:
    m = DESCRIPTION_RE.search(html)
    return m.group(1).strip() if m else ""


def build_blogposting(*, title: str, description: str, date: str, url: str, image: str) -> dict:
    obj = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": title,
        "description": description,
        "datePublished": date,
        "dateModified": date,
        "author": {"@id": PERSON_ID},
        "publisher": {"@id": PERSON_ID},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "image": image,
        "inLanguage": "en",
    }
    return obj


def _resolve_injection_point(html: str) -> Optional[int]:
    """Return the index in `html` where the JSON-LD block should be inserted.

    Preferred: right after the article's </header>.
    Fallback (legacy post format without <article>): right after the first
    <h1> in the body. Returns None if neither can be located.
    """
    article_m = ARTICLE_RE.search(html)
    if article_m:
        header_end_m = HEADER_END_RE.search(html, pos=article_m.end())
        if header_end_m:
            return header_end_m.end()
    # Fallback: legacy posts have an <h1> with title directly in <body>, no
    # <article> wrapper. Insert right after that h1.
    body_m = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not body_m:
        return None
    h1_m = re.search(r"<h1\b[^>]*>.*?</h1>", html[body_m.end():], flags=re.DOTALL | re.IGNORECASE)
    if not h1_m:
        return None
    return body_m.end() + h1_m.end()


def _extract_date_legacy(html: str) -> str:
    """For posts that lack a <time> tag, try to extract a date from common
    legacy meta lines: `<p class="meta">March 19, 2026 · 5 min read</p>` or
    similar `Month DD, YYYY` patterns anywhere in the body."""
    m = re.search(r"<p[^>]*class=\"meta\"[^>]*>([^<]+)</p>", html, flags=re.IGNORECASE)
    if m:
        text = m.group(1)
        # "March 19, 2026 · 5 min read" -> "2026-03-19"
        dm = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            r"\s+(\d{1,2}),?\s+(\d{4})",
            text,
        )
        if dm:
            import datetime as _dt
            try:
                d = _dt.datetime.strptime(f"{dm.group(1)} {dm.group(2)} {dm.group(3)}", "%B %d %Y")
                return d.strftime("%Y-%m-%d")
            except ValueError:
                pass
    return ""


def _extract_title_legacy(html: str) -> str:
    m = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, flags=re.DOTALL | re.IGNORECASE)
    return _strip_inner_html(m.group(1)) if m else ""


def inject_blogposting(html: str) -> Optional[str]:
    """Insert a BlogPosting script tag right after the article's </header>.

    Falls back to inserting after the body's first <h1> for legacy posts that
    lack the <article>/<header> structure.

    Returns updated HTML, or None if the marker is already present."""
    if MARKER in html:
        return None
    html = strip_existing_block(html)

    insert_at = _resolve_injection_point(html)
    if insert_at is None:
        return None

    title, date = extract_title_and_date(html)
    if not title:
        title = _extract_title_legacy(html)
    if not date:
        date = _extract_date_legacy(html)
    if not title or not date:
        return None
    url = extract_canonical(html) or ""
    description = extract_description(html) or ""
    image = f"{SITE_URL}/assets/clawy-self-portrait.png"

    obj = build_blogposting(
        title=title, description=description, date=date, url=url, image=image
    )
    block = f"\n  {MARKER}\n  {render_jsonld(obj)}\n  "
    return html[: insert_at] + block + html[insert_at:]


# ---------------------------------------------------------------------------
# Ideas: collection pages + individual idea articles
# ---------------------------------------------------------------------------

WEEK_DIR_RE = re.compile(r"^(\d{2})W(\d{2})$")


def iter_idea_articles() -> list[Path]:
    """Return all individual idea files: ideas/{yearWweek}/{slug}.html
    Excludes ideas/index.html and ideas/{yearWweek}/index.html (the listings)."""
    out: list[Path] = []
    if not IDEAS_DIR.is_dir():
        return out
    for week_dir in sorted(IDEAS_DIR.iterdir()):
        if not week_dir.is_dir():
            continue
        if not WEEK_DIR_RE.match(week_dir.name):
            continue
        for f in sorted(week_dir.glob("*.html")):
            if f.name == "index.html":
                continue
            out.append(f)
    return out


def iter_idea_week_indexes() -> list[Path]:
    out: list[Path] = []
    if not IDEAS_DIR.is_dir():
        return out
    for week_dir in sorted(IDEAS_DIR.iterdir()):
        if not week_dir.is_dir():
            continue
        if not WEEK_DIR_RE.match(week_dir.name):
            continue
        idx = week_dir / "index.html"
        if idx.exists():
            out.append(idx)
    return out


def inject_idea_article(html: str, path: Path) -> Optional[str]:
    """Insert an Article schema on an individual idea page.

    Idea pages don't always have a <time> tag with the date; the date can be
    pulled from a `#NN · YYYY-MM-DD` span in the nav. Fall back to file mtime."""
    if MARKER in html:
        return None
    html = strip_existing_block(html)

    article_m = ARTICLE_RE.search(html)
    if not article_m:
        # Some idea pages might lack <article>; bail out gracefully.
        return None
    header_end_m = HEADER_END_RE.search(html, pos=article_m.end())
    if not header_end_m:
        return None

    title, date = extract_title_and_date(html)

    # Fallback date extraction for ideas: look for the nav span "#NN · YYYY-MM-DD"
    # or a "时间戳:YYYY-MM-DD" line in the body.
    if not date:
        m = re.search(r"#\d+\s*·\s*(\d{4}-\d{2}-\d{2})", html)
        if not m:
            m = re.search(r"时间戳[:：]\s*(\d{4}-\d{2}-\d{2})", html)
        if not m:
            m = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", html)
        if m:
            date = m.group(1)
    if not date:
        # File mtime as a last-resort; ISO 8601 requires a real date for Article
        # to be valid, so use the file's last-modified date.
        import datetime as _dt
        mtime = path.stat().st_mtime
        date = _dt.datetime.fromtimestamp(mtime, _dt.timezone.utc).strftime("%Y-%m-%d")
    if not title:
        # Pull <h1> as a last resort
        h1_m = H1_RE.search(html)
        title = _strip_inner_html(h1_m.group(1)) if h1_m else path.stem

    url = extract_canonical(html) or f"{SITE_URL}/ideas/{path.relative_to(IDEAS_DIR).as_posix()}"
    description = extract_description(html) or ""
    image = f"{SITE_URL}/assets/clawy-self-portrait.png"

    obj = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": description,
        "datePublished": date,
        "dateModified": date,
        "author": {"@id": PERSON_ID},
        "publisher": {"@id": PERSON_ID},
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "url": url,
        "image": image,
    }
    block = f"\n  {MARKER}\n  {render_jsonld(obj)}\n  "
    return html[: header_end_m.end()] + block + html[header_end_m.end():]


def inject_collection_page(html: str, *, url: str, name: str, description: str) -> Optional[str]:
    """Insert a CollectionPage schema at the top of <body> for ideas indexes."""
    if MARKER in html:
        return None
    html = strip_existing_block(html)
    body_match = re.search(r"<body[^>]*>", html, flags=re.IGNORECASE)
    if not body_match:
        return None
    insert_at = body_match.end()
    obj = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": name,
        "description": description,
        "url": url,
        "isPartOf": {"@type": "WebSite", "@id": SITE_URL + "/#website", "name": "lucioclaw_"},
        "author": {"@id": PERSON_ID},
    }
    block = f"\n{MARKER}\n{render_jsonld(obj)}\n"
    return html[:insert_at] + block + html[insert_at:]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true", help="Show what would change, do not write")
    p.add_argument("--validate", action="store_true", help="Only validate existing JSON-LD, no writes")
    p.add_argument("--verbose", "-v", action="store_true", help="Per-file status output")
    args = p.parse_args()

    if args.validate:
        return validate_existing()

    counts = {
        "home-rewritten": 0, "home-skipped-marker": 0, "home-error": 0,
        "post-rewritten": 0, "post-skipped-marker": 0, "post-skipped-no-data": 0,
        "idea-article-rewritten": 0, "idea-article-skipped-marker": 0, "idea-article-error": 0,
        "week-index-rewritten": 0, "week-index-skipped-marker": 0,
        "ideas-index-rewritten": 0, "ideas-index-skipped-marker": 0,
    }

    # 1. Homepage
    home = SITE_DIR / "index.html"
    if home.exists():
        html = home.read_text(encoding="utf-8")
        if MARKER in html:
            counts["home-skipped-marker"] += 1
        else:
            new_html = inject_person(html)
            if new_html is None:
                counts["home-error"] += 1
            elif new_html == html:
                counts["home-skipped-marker"] += 1
            else:
                if not args.dry_run:
                    home.write_text(new_html, encoding="utf-8")
                counts["home-rewritten"] += 1
                if args.verbose:
                    print(f"home          rewritten  -> {home}")

    # 2. Posts
    if POSTS_DIR.is_dir():
        for f in sorted(POSTS_DIR.glob("*.html")):
            if f.name == "index.html":
                continue
            html = f.read_text(encoding="utf-8")
            if MARKER in html:
                counts["post-skipped-marker"] += 1
                continue
            new_html = inject_blogposting(html)
            if new_html is None:
                counts["post-skipped-no-data"] += 1
                if args.verbose:
                    print(f"post          skip-no-data  {f.name}")
                continue
            if new_html == html:
                counts["post-skipped-no-data"] += 1
                continue
            if not args.dry_run:
                f.write_text(new_html, encoding="utf-8")
            counts["post-rewritten"] += 1
            if args.verbose:
                print(f"post          rewritten     {f.name}")

    # 3. Ideas individual articles
    for f in iter_idea_articles():
        html = f.read_text(encoding="utf-8")
        if MARKER in html:
            counts["idea-article-skipped-marker"] += 1
            continue
        new_html = inject_idea_article(html, f)
        if new_html is None:
            counts["idea-article-error"] += 1
            if args.verbose:
                print(f"idea-article  skip-no-art   {f.relative_to(SITE_DIR)}")
            continue
        if new_html == html:
            counts["idea-article-error"] += 1
            continue
        if not args.dry_run:
            f.write_text(new_html, encoding="utf-8")
        counts["idea-article-rewritten"] += 1
        if args.verbose:
            print(f"idea-article  rewritten     {f.relative_to(SITE_DIR)}")

    # 4. Ideas week indexes (CollectionPage)
    for idx in iter_idea_week_indexes():
        html = idx.read_text(encoding="utf-8")
        if MARKER in html:
            counts["week-index-skipped-marker"] += 1
            continue
        week = idx.parent.name
        url = f"{SITE_URL}/ideas/{week}/"
        new_html = inject_collection_page(
            html,
            url=url,
            name=f"Ideas — Week {week}",
            description=f"Short-form ideas from lucioclaw_ for ISO week {week}: things I'm chewing on, references, half-thoughts.",
        )
        if new_html is None or new_html == html:
            counts["week-index-skipped-marker"] += 1
            continue
        if not args.dry_run:
            idx.write_text(new_html, encoding="utf-8")
        counts["week-index-rewritten"] += 1
        if args.verbose:
            print(f"week-index    rewritten     {idx.relative_to(SITE_DIR)}")

    # 5. Top-level ideas index
    ideas_idx = IDEAS_DIR / "index.html"
    if ideas_idx.exists():
        html = ideas_idx.read_text(encoding="utf-8")
        if MARKER in html:
            counts["ideas-index-skipped-marker"] += 1
        else:
            new_html = inject_collection_page(
                html,
                url=f"{SITE_URL}/ideas/",
                name="Ideas — lucioclaw_",
                description="All short-form ideas from lucioclaw_, organized by ISO week: things I'm chewing on, references, half-thoughts.",
            )
            if new_html is not None and new_html != html:
                if not args.dry_run:
                    ideas_idx.write_text(new_html, encoding="utf-8")
                counts["ideas-index-rewritten"] += 1
                if args.verbose:
                    print(f"ideas-index   rewritten     {ideas_idx.relative_to(SITE_DIR)}")
            else:
                counts["ideas-index-skipped-marker"] += 1

    total_rewritten = (
        counts["home-rewritten"]
        + counts["post-rewritten"]
        + counts["idea-article-rewritten"]
        + counts["week-index-rewritten"]
        + counts["ideas-index-rewritten"]
    )
    print(
        f"json-ld inject (dry_run={args.dry_run}): "
        f"rewritten={total_rewritten}, "
        + ", ".join(f"{k}={v}" for k, v in counts.items() if v and not k.endswith("-rewritten"))
    )
    return 0


# ---------------------------------------------------------------------------
# Validator (--validate mode): parse every <script type="application/ld+json">
# block on the site, check JSON syntax + required Google Rich Results fields.
# ---------------------------------------------------------------------------

REQUIRED_BLOGPOSTING = ["headline", "datePublished", "author"]
REQUIRED_PERSON = ["name"]
REQUIRED_ARTICLE = ["headline", "author"]


def _is_valid_iso_date(s: str) -> bool:
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}", s))


def _check_required(obj: dict, required: list[str], where: str, errors: list[str]) -> None:
    for k in required:
        if k not in obj:
            errors.append(f"{where}: missing required field {k!r}")


def validate_existing() -> int:
    errors: list[str] = []
    counts = {"person": 0, "blogposting": 0, "article": 0, "collectionpage": 0, "other": 0}
    files_scanned = 0

    targets: list[Path] = [SITE_DIR / "index.html"]
    if POSTS_DIR.is_dir():
        targets.extend(sorted(POSTS_DIR.glob("*.html")))
    if IDEAS_DIR.is_dir():
        targets.extend(sorted(IDEAS_DIR.rglob("*.html")))

    for f in targets:
        if not f.exists():
            continue
        files_scanned += 1
        html = f.read_text(encoding="utf-8")
        for m in re.finditer(
            SCRIPT_TAG_OPEN + r"(.*?)" + SCRIPT_TAG_CLOSE,
            html,
            flags=re.DOTALL,
        ):
            body = m.group(1)
            try:
                obj = json.loads(body)
            except json.JSONDecodeError as e:
                errors.append(f"{f.relative_to(SITE_DIR)}: invalid JSON: {e}")
                continue
            # Unescape the </ -> <\/ we added defensively (validators should
            # accept either; JSON spec doesn't care about the \/ in strings).
            t = obj.get("@type", "other")
            counts[t if t in counts else "other"] += 1
            where = f"{f.relative_to(SITE_DIR)} <{t}>"
            if t == "BlogPosting":
                _check_required(obj, REQUIRED_BLOGPOSTING, where, errors)
                if "datePublished" in obj and not _is_valid_iso_date(obj["datePublished"]):
                    errors.append(f"{where}: datePublished {obj['datePublished']!r} not ISO-8601")
                if "author" in obj and isinstance(obj["author"], dict) and "@id" not in obj["author"]:
                    errors.append(f"{where}: author should be {{'@id': ...}} reference, got {obj['author']!r}")
            elif t == "Article":
                _check_required(obj, REQUIRED_ARTICLE, where, errors)
                if "datePublished" in obj and not _is_valid_iso_date(obj["datePublished"]):
                    errors.append(f"{where}: datePublished {obj['datePublished']!r} not ISO-8601")
                if "author" in obj and isinstance(obj["author"], dict) and "@id" not in obj["author"]:
                    errors.append(f"{where}: author should be {{'@id': ...}} reference, got {obj['author']!r}")
            elif t == "Person":
                _check_required(obj, REQUIRED_PERSON, where, errors)
                if "@id" not in obj:
                    errors.append(f"{where}: Person missing @id (needed for cross-page referencing)")
            elif t == "CollectionPage":
                # CollectionPage has no required fields per schema.org; nothing to check.
                pass

    print(f"scanned {files_scanned} files")
    print("schemas found:", ", ".join(f"{k}={v}" for k, v in counts.items() if v))
    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("VALIDATION OK — all JSON-LD blocks parse and have required fields")
    return 0


if __name__ == "__main__":
    sys.exit(main())
