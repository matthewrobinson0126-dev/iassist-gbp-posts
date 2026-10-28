"""Check written posts before committing: prices on the live page, no phone numbers/links, length.

Usage: python tools/check.py [name ...]     (no names = check every file in bank/)
Exits 1 if anything fails, listing each problem.
"""
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import daily_post as dp  # noqa: E402
import offline  # noqa: E402,F401  (read pages from cache/pages.json)

names = sys.argv[1:] or sorted(p.stem for p in dp.BANK.glob("*.txt"))
facts_cache, problems = {}, []
for name in names:
    path = dp.BANK / f"{name}.txt"
    text = path.read_text(encoding="utf-8")
    head, sep, body = text.partition("\n---")
    body = body.strip()
    page = re.search(r"^Page: *(.+)$", head, re.M)
    if not sep or not page:
        problems.append((name, "missing 'Page:' line or '---' separator"))
        continue
    for field in ("Headline", "Subline", "Price", "Button"):
        if not re.search(rf"^{field}:", head, re.M):
            problems.append((name, f"missing '{field}:' line"))
    if len(body) > 1450:
        problems.append((name, f"body too long ({len(body)} chars, max 1450)"))
    if re.search(r"0[67]\d ?\d{3} ?\d{4}|https?://|www\.", body):
        problems.append((name, "phone number or link in the text"))
    url = page.group(1).strip()
    if url not in facts_cache:
        for attempt in range(4):
            try:
                facts_cache[url] = dp.page_facts(url)
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        time.sleep(0.5)
    facts = facts_cache.get(url)
    if not facts:
        problems.append((name, f"could not fetch {url}"))
        continue
    stale = dp.stale_prices(body, facts)
    if stale:
        problems.append((name, "prices not on the live page: " + ", ".join(stale)))
    price = re.search(r"^Price: *(.*)$", head, re.M).group(1).strip()
    if price and "R" + re.sub(r"\D", "", price) not in re.sub(r"[^\dR]", "", facts["text"] + facts["meta"]):
        problems.append((name, f"picture price {price} not on the live page"))

print(f"checked {len(names)} posts, {len(problems)} problems")
for p in problems:
    print(" ", p)
sys.exit(1 if problems else 0)
