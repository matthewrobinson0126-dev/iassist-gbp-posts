"""What needs writing: simulate the rotation forward from state.json and list posts with no file in bank/.

Usage: python tools/plan.py [days]      (default 150)
Prints JSON: {"missing": [...], "needs_refresh": [...], "covered_until": "YYYY-MM-DD"}
Each missing item: {"date", "slot": "device"|"location", "name", "url", "device", "kind"}
kind = "suburb"        -> Apple suburb page x device: generate with tools/gen_suburb.py
       "iphone-suburb" -> iPhone suburb page: hand-write (see MAINTENANCE.md)
       "blog"          -> location blog post: hand-write
       "page"          -> device/service page: hand-write
"""
import copy
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import daily_post as dp  # noqa: E402

days = int(sys.argv[1]) if len(sys.argv) > 1 else 150
cache = dp.sitemap_urls()
dp.sitemap_urls = lambda: cache
state = copy.deepcopy(dp.load_state())
bank = dp.bank_slugs()
start = datetime.now(dp.SAST) + timedelta(days=1)
missing, seen, covered_until = [], set(), None


def kind_of(url):
    slug = dp.slug_of(url)
    if "/blogs/" in url:
        return "blog"
    if slug.startswith("iphone-repair-"):
        return "iphone-suburb"
    return "suburb"


for i in range(days):
    day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
    key, _, url, _ = dp.pick_topic(state, False)
    state["posted"].setdefault(key, []).append(url)
    slug = dp.slug_of(url)
    if slug not in bank and slug not in seen:
        missing.append({"date": day, "slot": "device", "name": slug, "url": url, "device": None, "kind": "page"})
        seen.add(slug)
    _, _, url2, device = dp.pick_topic(state, True)
    name = f"{dp.slug_of(url2)}--{device}"
    if name not in bank and dp.slug_of(url2) not in bank and name not in seen:
        missing.append({"date": day, "slot": "location", "name": name, "url": url2, "device": device, "kind": kind_of(url2)})
        seen.add(name)
    if not missing:
        covered_until = day

print(json.dumps({"missing": missing, "needs_refresh": state.get("needs_refresh", []),
                  "covered_until": covered_until}, indent=1))
