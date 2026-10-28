"""Save a snapshot of every page in the rotation to cache/pages.json.

Runs in GitHub Actions (which can reach the website) on the 1st of each month, before the
Claude maintenance agent runs in the cloud (which can't). The tools read this snapshot.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import daily_post as dp  # noqa: E402

urls = dp.sitemap_urls()
wanted = [u for u in urls if dp.group_of(u)]
pages, failed = {}, []
for u in wanted:
    for attempt in range(5):
        try:
            f = dp.page_facts(u)
            pages[u] = {"title": f["title"], "meta": f["meta"], "text": f["text"]}
            break
        except Exception:
            time.sleep(6 * (attempt + 1))
    else:
        failed.append(u)
    time.sleep(1)

out = ROOT / "cache" / "pages.json"
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps({"taken": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "sitemap": urls, "pages": pages}, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"{len(pages)} pages saved, {len(failed)} failed")
if failed:
    print("failed:", *failed, sep="\n  ")
