"""Write bank posts for 'suburb' items from tools/plan.py output (Apple suburb page x device).

Usage: python tools/plan.py > /tmp/plan.json && python tools/make_suburb_posts.py /tmp/plan.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tools"))
import daily_post as dp  # noqa: E402
import offline  # noqa: E402,F401  (read pages from cache/pages.json)
import gen_suburb as g  # noqa: E402

plan = json.load(open(sys.argv[1]))
done = 0
for item in plan["missing"]:
    if item["kind"] != "suburb":
        continue
    facts = dp.page_facts(item["url"])
    head, sub, body = g.build(item["name"], item["url"], item["device"], facts)
    (dp.BANK / f"{item['name']}.txt").write_text(
        f"Page: {item['url']}\nHeadline: {head}\nSubline: {sub}\nPrice: \nButton: Learn more\n---\n{body}\n",
        encoding="utf-8")
    done += 1
    time.sleep(0.5)
print(done, "suburb posts written")
