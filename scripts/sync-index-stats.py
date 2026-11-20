#!/usr/bin/env python3
"""sync-index-stats.py — keep index.html's shipped stat placeholders equal to data/stats.json.

Why this exists
---------------
index.html ships hardcoded numbers inside the stat bar:

    <div class="num" data-stat="karma">198</div>

assets/script.js overwrites them client-side from /data/stats.json, so a
JS-enabled visitor sees live values. But:

  * a no-JS visitor sees the shipped numbers, and
  * any crawler reading raw HTML sees the shipped numbers, and
  * the client-side fetch ends in `.catch(() => {})` — a failed fetch leaves
    the shipped numbers in place, silently.

Those shipped numbers were frozen at the initial commit (karma 198, followers
30, days_alive 7, site_posts 0) while the site grew to 234 posts and 253 days,
so the raw HTML claimed "0 Posts" on a 234-post site.

This script makes the static fallback true instead of hopeful: it reads
data/stats.json and rewrites only those four values in index.html.

Guarantees
----------
  * idempotent — a second run with unchanged stats.json changes nothing
  * surgical — only the four data-stat values are touched; every other byte
    of index.html is preserved
  * atomic — index.html is replaced via a temp file + os.replace, so a
    concurrent request never observes a half-written page
  * non-fatal by design — it is called with `|| true` from update-stats.sh, so
    a failure here can never fail the hourly stats refresh
"""
import json
import os
import re
import sys
import tempfile

SITE_DIR = os.environ.get("SITE_DIR", "/var/www/guoliangchen.com")
STATS_PATH = os.path.join(SITE_DIR, "data", "stats.json")
INDEX_PATH = os.path.join(SITE_DIR, "index.html")
KEYS = ("karma", "followers", "days_alive", "site_posts")


def main():
    if not os.path.isfile(STATS_PATH):
        print("skip: no stats.json at %s" % STATS_PATH)
        return 0
    if not os.path.isfile(INDEX_PATH):
        print("skip: no index.html at %s" % INDEX_PATH)
        return 0

    try:
        with open(STATS_PATH, encoding="utf-8") as fh:
            stats = json.load(fh)
    except (OSError, ValueError) as exc:
        print("skip: unreadable stats.json (%s)" % exc)
        return 0

    try:
        with open(INDEX_PATH, encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        print("skip: unreadable index.html (%s)" % exc)
        return 0

    original_mode = os.stat(INDEX_PATH).st_mode & 0o777
    changed = []
    for key in KEYS:
        if key not in stats:
            continue
        want = str(stats[key])
        pattern = re.compile(
            r'(<div class="num" data-stat="%s">)([^<]*)(</div>)' % re.escape(key)
        )
        match = pattern.search(html)
        if not match:
            continue
        have = match.group(2)
        if have == want:
            continue
        html = pattern.sub(lambda m: m.group(1) + want + m.group(3), html, count=1)
        changed.append("%s: %s -> %s" % (key, have, want))

    if not changed:
        print(
            "index stats already current: %s"
            % ", ".join("%s=%s" % (k, stats.get(k)) for k in KEYS)
        )
        return 0

    directory = os.path.dirname(INDEX_PATH)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".index.html.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(html)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, original_mode)
        os.replace(tmp_path, INDEX_PATH)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

    for line in changed:
        print("updated %s" % line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
