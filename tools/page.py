"""Print a page's title, description and text from the snapshot (cache/pages.json).

Usage: python tools/page.py <slug or full URL> [more ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import daily_post as dp  # noqa: E402
import offline  # noqa: E402,F401

for arg in sys.argv[1:]:
    url = arg if arg.startswith("http") else next(
        (u for u in dp.sitemap_urls() if dp.slug_of(u) == arg), f"{dp.SITE}/pages/{arg}")
    f = dp.page_facts(url)
    print(f"=== {url}\nTITLE: {f['title']}\nMETA: {f['meta']}\nTEXT: {f['text']}\n")
