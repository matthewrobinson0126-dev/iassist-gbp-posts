# iAssist Repair – daily Google Business Profile post

Every morning at 08:00 (South Africa time) GitHub runs `scripts/daily_post.py`:

1. Reads the live sitemap of iassist.net.za and picks the next page, rotating
   iPhone → PlayStation → iPad → controllers → MacBook → Xbox → Apple Watch → Switch → iMac/Mac mini → areas.
   Every page in a group is used once before any repeat (progress is in `state.json`).
2. Claude (`claude-opus-5-5`) writes the post from that page only – no invented prices or stories,
   no phone numbers. If Claude is unavailable, a plain post is built from the page's own description.
3. Draws a branded 1200×900 image into `posts/` (served by GitHub Pages).
4. Sends the post to a Make.com webhook, which publishes it on the Google Business Profile
   with a Book / Learn more button linking to the page (with UTM tags).

Secrets: `ANTHROPIC_API_KEY`, `MAKE_WEBHOOK_URL`.
Pause: switch the Make.com scenario off. Test: Actions → Daily Google post → Run workflow
(untick "Send" to only make the post and image).
