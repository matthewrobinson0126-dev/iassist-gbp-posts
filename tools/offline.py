"""Make the tools read the website from cache/pages.json instead of the internet.

The cloud agent has no internet access to iassist.net.za; GitHub Actions saves a fresh snapshot
on the 1st of each month (tools/snapshot.py). Import this right after importing daily_post.
"""
import json
from pathlib import Path

import daily_post as dp

CACHE = Path(__file__).resolve().parent.parent / "cache" / "pages.json"

if CACHE.exists():
    _snap = json.loads(CACHE.read_text(encoding="utf-8"))
    _pages = _snap["pages"]
    _live_facts = dp.page_facts

    def page_facts(url):
        if url in _pages:
            return _pages[url]
        return _live_facts(url)  # not in the snapshot (e.g. a brand-new page): try the internet

    dp.sitemap_urls = lambda: list(_snap["sitemap"])
    dp.page_facts = page_facts
    TAKEN = _snap.get("taken")
else:
    TAKEN = None
