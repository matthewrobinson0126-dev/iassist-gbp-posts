# Monthly maintenance — instructions for the Claude agent

This repo posts two Google Business Profile updates a day for **iAssist Repair** (Apple + games-console
repairs, Shop 4, Silvercrest Shopping Centre, Silvamonte, Johannesburg; owner Matthew Robinson).
`scripts/daily_post.py` runs at 08:00 (device post) and 13:00 (location post) SAST and uses the
pre-written post in `bank/<name>.txt` for each topic. Your job each month is to keep `bank/` full and correct.
Matthew is not a coder and does not want to be asked anything — do the work, commit, push.

## Steps

1. `git pull --rebase`. No packages are needed (standard library only).
   **This cloud machine cannot reach iassist.net.za.** GitHub saves a snapshot of every page to
   `cache/pages.json` on the 1st of each month, and all tools read from it automatically. To read a page,
   run `python tools/page.py <slug-or-url>`. Don't try to fetch the website yourself.
2. `python tools/plan.py 150 > /tmp/plan.json` and read it.
   - `missing`: topics in the next 150 days with no post written.
   - `needs_refresh`: posts the robot skipped because a price in them is no longer on the live page.
3. **Refresh** every name in `needs_refresh`: read the page with `python tools/page.py <slug>`, rewrite the post with the
   current facts, then remove that name from `needs_refresh` in `state.json`.
4. **Write** posts for `missing` items, soonest dates first. Aim to keep at least ~120 days covered.
   - `kind: suburb` → run `python tools/make_suburb_posts.py /tmp/plan.json` (automatic).
   - `kind: page`, `iphone-suburb`, `blog` → write by hand (rules below). Read the page with `python tools/page.py <slug>` and use only its facts.
   If there is a lot, do the first ~60 days fully and as many more as you reasonably can; the robot falls back to a
   plain post for anything unwritten, so nothing breaks.
5. `python tools/check.py <every name you wrote or refreshed>` — fix every problem it reports, re-run until clean.
6. Commit only `bank/` and `state.json` (and nothing in `posts/`), `git pull --rebase`, `git push`.
   Commit message: `Monthly posts: N new, M refreshed`.
7. End with a short summary: how many written, refreshed, and the new `covered_until` date.

## File format (`bank/<name>.txt`)

```
Page: https://iassist.net.za/pages/<slug>
Headline: <big text on the picture, max ~40 chars>
Subline: <one short line under it, max ~55 chars>
Price: <lowest "from" price exactly as on the page, e.g. R1,200 — or empty>
Button: Learn more
---
<post text>
```
`<name>` = the page slug for device posts; `<slug>--<device>` for location posts (exactly as plan.py gives it).
The Button line is overridden by the robot's schedule; always write `Learn more`.

## Writing rules (follow existing files in bank/ as examples of the house style)

- South African English, plain and friendly, short paragraphs. 500–1100 characters.
- Structure for device pages: 1–2 short paragraphs on the real problems/repairs **from that page**, then:
  - `Bring it to our workshop at Silvercrest Shopping Centre in Silvamonte, or we collect anywhere in Gauteng for a flat R300, insured both ways.` (only if the page itself says R300; otherwise say "ask us about door-to-door collection" with no price)
  - `Every repair starts with a free diagnostic, so you know what's wrong and what it costs before any work begins. Repairs carry a 6-month warranty.`
  - `Tap Learn more for <Headline> prices and details.`
- iPhone suburb posts: open with the page's own local story (a landmark, the kind of people who live/work there),
  connect it to how iPhones get used/damaged there, list repairs, then collection + diagnostic/warranty + `Tap Learn more for iPhone repair for <Area>.`
- Only facts from the page. Never invent prices, turnaround times, distances, warranties, customer stories,
  or "we fixed X in this suburb" claims. If a page's facts look wrong or contradict another page, leave that fact out.
- No phone numbers, email addresses, web addresses, hashtags or emojis. No "best", "cheapest", "#1".
- Don't criticise other repair shops, even if the page does.
- Only use the `Price:` field on pages about one specific repair with a clear "from" price; leave it empty on hub/model pages.
- Every rand amount you write must appear on the live page (check.py enforces this).
