#!/bin/bash
# seo-check.sh — Post-build automated SEO validation
# Runs after scripts/build.sh. Verifies the SEO pipeline left the site in a
# healthy state. Catches regressions that individual idempotent scripts might
# miss (e.g. a script that runs cleanly but produces 0 markers because a regex
# drifted).
#
# Checks (in order):
#   1. sitemap.xml: parses, has URLs, every URL corresponds to an existing file
#   2. Description coverage: every HTML page has <meta name="description">
#   3. Title uniqueness: no two pages share a <title>
#   4. Canonical coverage: every page has <link rel="canonical">
#   5. og:type coverage: every page has <meta property="og:type">
#   6. JSON-LD coverage: index.html has Person, post pages have BlogPosting,
#      idea pages have Article, ideas index has CollectionPage
#   7. Favicon coverage: every HTML page has <link rel="icon" href="/favicon.ico">
#   8. Perf coverage: pages with style.css also have preconnect to fonts.googleapis
#   9. JSON-LD parse: every <script type="application/ld+json"> block is valid JSON
#
# Exit code: 0 = all checks pass, 1 = at least one failure
set -uo pipefail

SITE_DIR="/var/www/guoliangchen.com"
SCRIPTS_DIR="$SITE_DIR/scripts"

# Find all HTML files
mapfile -t HTML_FILES < <(find "$SITE_DIR" -name "*.html" -not -path "*/__pycache__/*" -not -path "*/.git/*" | sort)
TOTAL=${#HTML_FILES[@]}

PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  ⚠️  $1"; WARN=$((WARN + 1)); }

echo "=== SEO Check: $TOTAL HTML files ==="

# ---------- 1. sitemap.xml ----------
echo ""
echo "[1] sitemap.xml"
SITEMAP="$SITE_DIR/sitemap.xml"
if [[ ! -f "$SITEMAP" ]]; then
  fail "sitemap.xml missing"
elif ! python3 -c "import xml.etree.ElementTree as ET; ET.parse('$SITEMAP')" 2>/dev/null; then
  fail "sitemap.xml is not valid XML"
else
  URL_COUNT=$(grep -c '<loc>' "$SITEMAP")
  ok "sitemap.xml parses, $URL_COUNT URLs"
  # Spot-check: do all sitemap URLs have a corresponding file?
  MISSING=0
  while IFS= read -r url; do
    # url is like https://guoliangchen.com/posts/foo.html
    path="${url#https://guoliangchen.com}"
    if [[ -z "$path" || "$path" == "/" ]]; then
      continue
    fi
    # For directory paths (ending in /), the file is index.html inside
    if [[ "$path" == */ ]]; then
      check_path="${path}index.html"
    else
      check_path="$path"
    fi
    if [[ ! -f "$SITE_DIR$check_path" ]]; then
      MISSING=$((MISSING + 1))
      if [[ $MISSING -le 3 ]]; then
        fail "sitemap references missing file: $check_path"
      fi
    fi
  done < <(grep -oE '<loc>[^<]+</loc>' "$SITEMAP" | sed -E 's|</?loc>||g')
  if [[ $MISSING -eq 0 ]]; then
    ok "all $URL_COUNT sitemap URLs resolve to existing files"
  else
    fail "$MISSING sitemap URLs reference missing files"
  fi
fi

# ---------- 2. Description coverage ----------
echo ""
echo "[2] <meta name=\"description\"> coverage"
NO_DESC=()
for f in "${HTML_FILES[@]}"; do
  if ! grep -q '<meta name="description"' "$f"; then
    NO_DESC+=("${f#$SITE_DIR/}")
  fi
done
if [[ ${#NO_DESC[@]} -eq 0 ]]; then
  ok "all $TOTAL pages have a description"
else
  fail "${#NO_DESC[@]} pages missing description:"
  for f in "${NO_DESC[@]:0:5}"; do echo "       - $f"; done
  if [[ ${#NO_DESC[@]} -gt 5 ]]; then echo "       ... and $(( ${#NO_DESC[@]} - 5 )) more"; fi
fi

# ---------- 3. Title uniqueness ----------
# Warning, not failure: same idea legitimately re-curated across multiple
# weeks (e.g. an idea first appears in 26W18, gets re-featured in 26W19 and
# 26W23) means the title pattern "Idea #N: ..." will repeat. This is content
# design, not a script bug. The check still surfaces the duplicates so they're
# visible, but it does not block the build.
echo ""
echo "[3] <title> uniqueness (warning-only)"
declare -A TITLE_TO_FILES
DUPES=()
for f in "${HTML_FILES[@]}"; do
  # Extract <title>...</title>
  title=$(grep -oE '<title>[^<]+</title>' "$f" | head -1 | sed -E 's|</?title>||g')
  if [[ -z "$title" ]]; then
    DUPES+=("NO-TITLE: ${f#$SITE_DIR/}")
    continue
  fi
  if [[ -n "${TITLE_TO_FILES[$title]:-}" ]]; then
    DUPES+=("DUP: '$title' in ${TITLE_TO_FILES[$title]} AND ${f#$SITE_DIR/}")
  else
    TITLE_TO_FILES[$title]="${f#$SITE_DIR/}"
  fi
done
if [[ ${#DUPES[@]} -eq 0 ]]; then
  ok "all $((${#TITLE_TO_FILES[@]})) titles are unique"
else
  warn "${#DUPES[@]} title duplicates (review for intentional curation vs accidental copy):"
  for d in "${DUPES[@]:0:5}"; do echo "       - $d"; done
  if [[ ${#DUPES[@]} -gt 5 ]]; then echo "       ... and $(( ${#DUPES[@]} - 5 )) more"; fi
fi

# ---------- 4. Canonical coverage ----------
echo ""
echo "[4] <link rel=\"canonical\"> coverage"
NO_CANON=()
for f in "${HTML_FILES[@]}"; do
  if ! grep -qE 'rel=["'\'']canonical["'\'']' "$f"; then
    NO_CANON+=("${f#$SITE_DIR/}")
  fi
done
if [[ ${#NO_CANON[@]} -eq 0 ]]; then
  ok "all $TOTAL pages have a canonical link"
else
  fail "${#NO_CANON[@]} pages missing canonical:"
  for f in "${NO_CANON[@]:0:5}"; do echo "       - $f"; done
  if [[ ${#NO_CANON[@]} -gt 5 ]]; then echo "       ... and $(( ${#NO_CANON[@]} - 5 )) more"; fi
fi

# ---------- 5. og:type coverage ----------
echo ""
echo "[5] <meta property=\"og:type\"> coverage"
NO_OG=()
for f in "${HTML_FILES[@]}"; do
  if ! grep -q 'property="og:type"' "$f"; then
    NO_OG+=("${f#$SITE_DIR/}")
  fi
done
if [[ ${#NO_OG[@]} -eq 0 ]]; then
  ok "all $TOTAL pages have an og:type meta"
else
  fail "${#NO_OG[@]} pages missing og:type:"
  for f in "${NO_OG[@]:0:5}"; do echo "       - $f"; done
  if [[ ${#NO_OG[@]} -gt 5 ]]; then echo "       ... and $(( ${#NO_OG[@]} - 5 )) more"; fi
fi

# ---------- 6. JSON-LD presence by page type ----------
echo ""
echo "[6] JSON-LD coverage by page type"
HOME_FILE="$SITE_DIR/index.html"
POSTS_DIR="$SITE_DIR/posts"
IDEAS_DIR="$SITE_DIR/ideas"

# Home: Person
if grep -q '"@type":"Person"' "$HOME_FILE" 2>/dev/null; then
  ok "homepage has Person JSON-LD"
else
  fail "homepage missing Person JSON-LD"
fi

# Posts: BlogPosting (or skip listings)
NO_POST_LD=()
while IFS= read -r f; do
  fname=$(basename "$f")
  if [[ "$fname" == "index.html" ]]; then continue; fi  # listing page
  if ! grep -q '"@type":"BlogPosting"' "$f"; then
    NO_POST_LD+=("${f#$SITE_DIR/}")
  fi
done < <(find "$POSTS_DIR" -name "*.html")
if [[ ${#NO_POST_LD[@]} -eq 0 ]]; then
  ok "all post pages have BlogPosting JSON-LD"
else
  fail "${#NO_POST_LD[@]} posts missing BlogPosting JSON-LD:"
  for f in "${NO_POST_LD[@]:0:5}"; do echo "       - $f"; done
fi

# Ideas: Article on individual, CollectionPage on indexes
NO_IDEA_LD=()
while IFS= read -r f; do
  fname=$(basename "$f")
  # If it's a listing (index.html at week root or ideas root), expect CollectionPage
  if [[ "$fname" == "index.html" ]]; then
    if ! grep -q '"@type":"CollectionPage"' "$f"; then
      NO_IDEA_LD+=("${f#$SITE_DIR/} (expected CollectionPage)")
    fi
  else
    if ! grep -q '"@type":"Article"' "$f"; then
      NO_IDEA_LD+=("${f#$SITE_DIR/} (expected Article)")
    fi
  fi
done < <(find "$IDEAS_DIR" -name "*.html")
if [[ ${#NO_IDEA_LD[@]} -eq 0 ]]; then
  ok "all idea pages have JSON-LD (Article or CollectionPage)"
else
  fail "${#NO_IDEA_LD[@]} idea pages missing JSON-LD:"
  for f in "${NO_IDEA_LD[@]:0:5}"; do echo "       - $f"; done
  if [[ ${#NO_IDEA_LD[@]} -gt 5 ]]; then echo "       ... and $(( ${#NO_IDEA_LD[@]} - 5 )) more"; fi
fi

# ---------- 7. Favicon coverage ----------
echo ""
echo "[7] <link rel=\"icon\"> coverage"
NO_FAV=()
for f in "${HTML_FILES[@]}"; do
  if ! grep -q 'rel="icon"' "$f"; then
    NO_FAV+=("${f#$SITE_DIR/}")
  fi
done
if [[ ${#NO_FAV[@]} -eq 0 ]]; then
  ok "all $TOTAL pages have a favicon link"
else
  fail "${#NO_FAV[@]} pages missing favicon link:"
  for f in "${NO_FAV[@]:0:5}"; do echo "       - $f"; done
fi

# ---------- 8. Perf coverage (preconnect on pages that load style.css) ----------
echo ""
echo "[8] Perf coverage (preconnect on style.css-loading pages)"
NO_PERF=()
for f in "${HTML_FILES[@]}"; do
  if grep -q 'href="/assets/style\.css' "$f"; then
    if ! grep -q 'preconnect.*fonts.googleapis' "$f"; then
      NO_PERF+=("${f#$SITE_DIR/}")
    fi
  fi
done
if [[ ${#NO_PERF[@]} -eq 0 ]]; then
  ok "all style.css-loading pages have preconnect"
else
  fail "${#NO_PERF[@]} pages with style.css but no preconnect:"
  for f in "${NO_PERF[@]:0:5}"; do echo "       - $f"; done
fi

# ---------- 9. JSON-LD parses ----------
echo ""
echo "[9] JSON-LD parse validity"
BAD_LD=()
for f in "${HTML_FILES[@]}"; do
  # Extract every <script type="application/ld+json">...</script> block
  python3 - "$f" <<'PY' || BAD_LD+=("$1")
import sys, re, json
path = sys.argv[1]
text = open(path, encoding='utf-8').read()
blocks = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.DOTALL | re.IGNORECASE)
for i, b in enumerate(blocks):
    try:
        json.loads(b)
    except json.JSONDecodeError as e:
        print(f"{path}: block {i+1} invalid: {e}", file=sys.stderr)
        sys.exit(1)
sys.exit(0)
PY
done
if [[ ${#BAD_LD[@]} -eq 0 ]]; then
  ok "all JSON-LD blocks parse cleanly"
else
  fail "${#BAD_LD[@]} files have invalid JSON-LD:"
  for f in "${BAD_LD[@]:0:5}"; do echo "       - $f"; done
fi

# ---------- Summary ----------
echo ""
echo "=== SEO Check Summary ==="
echo "  ✅ $PASS passed"
[[ $WARN -gt 0 ]] && echo "  ⚠️  $WARN warnings"
[[ $FAIL -gt 0 ]] && echo "  ❌ $FAIL failed"

if [[ $FAIL -gt 0 ]]; then
  echo ""
  echo "FAILED — fix issues above, then re-run."
  exit 1
fi

echo ""
echo "OK — site passes all SEO checks."
exit 0
