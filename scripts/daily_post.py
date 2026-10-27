"""Build and send iAssist Repair's daily Google Business Profile post.

Runs from GitHub Actions in two phases:
  build  - pick today's page from the live sitemap, write the post (Claude),
           draw the branded image, save posts/<date>-<slug>.jpg + post.json + state.json
  send   - wait until the image is live on GitHub Pages, then hand the post to Make.com,
           which publishes it on the Google Business Profile.

Topics rotate through device groups (iPhone, PlayStation, iPad, controllers, ...) so the
same kind of post never runs two days in a row. Every page is used once before any repeats.
"""
import json
import os
import re
import sys
import time
import html as htmlmod
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SITE = "https://iassist.net.za"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "state.json"
POST = ROOT / "post.json"
POSTS_DIR = ROOT / "posts"
ASSETS = ROOT / "assets"
BANK = ROOT / "bank"  # pre-written posts, one <page-slug>.txt each (synced from Google Drive)
PAGES_BASE = os.environ.get("PAGES_BASE", "https://matthewrobinson0126-dev.github.io/iassist-gbp-posts")
SAST = timezone(timedelta(hours=2))
UA = {"User-Agent": "iAssist-GBP-poster/1.0 (+https://iassist.net.za)"}

# Device groups. On device days the next group is picked in proportion to how many pages it
# has (smooth weighted round-robin), so every device page is covered in the same overall cycle
# while the groups stay mixed.
GROUPS = [
    ("iphone", "iPhone Repairs"),
    ("playstation", "PlayStation Repairs"),
    ("ipad", "iPad Repairs"),
    ("controllers", "Controller Repairs"),
    ("macbook", "MacBook Repairs"),
    ("xbox", "Xbox Repairs"),
    ("watch", "Apple Watch Repairs"),
    ("switch", "Nintendo Switch Repairs"),
    ("desktop", "iMac & Mac mini Repairs"),
]
MIN_WEIGHT = 15
AREAS_LABEL = "Areas We Serve"
LOCATION_DAYS = {1, 3, 5}  # Tuesday, Thursday, Saturday (Monday=0)
# Suburb pages about Apple repair are paired with each of these in turn.
APPLE_DEVICES = [("iphone", "iPhone"), ("ipad", "iPad"), ("macbook", "MacBook"),
                 ("watch", "Apple Watch"), ("desktop", "iMac & Mac mini")]
SKIP_SLUGS = {"contact", "shop", "matthew-robinson"}

# Brand (from the live theme): dark slate, tan buttons, white text, Jost.
SLATE = (28, 34, 40)
SLATE_2 = (50, 56, 65)
TAN = (183, 172, 162)
TAN_LIGHT = (194, 183, 172)
WHITE = (255, 255, 255)
ADDRESS = "Shop 4, Silvercrest Shopping Centre  ·  iassist.net.za"


# ---------- topics ----------

def fetch(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def sitemap_urls():
    index = fetch(f"{SITE}/sitemap.xml")
    urls = []
    for sm in re.findall(r"<loc>([^<]+)</loc>", index):
        sm = htmlmod.unescape(sm)
        if "sitemap_pages" in sm or "sitemap_articles" in sm:
            urls += re.findall(r"<loc>([^<]+)</loc>", fetch(sm))
    return sorted(set(urls))


def group_of(url):
    path = url.split(SITE, 1)[-1]
    if path.startswith("/blogs/locations/"):
        return "areas"
    if path.startswith("/blogs/"):
        return None  # general news/advice blogs aren't part of the rotation
    slug = path.rsplit("/", 1)[-1]
    if slug in SKIP_SLUGS:
        return None
    if (slug.startswith(("apple-repair-", "iphone-repair-", "locations-"))
            or slug in ("national-courier-repairs",)):
        return "areas"
    if "controller" in slug or "joy-con" in slug:
        return "controllers"
    if slug.startswith(("ps4", "ps5", "playstation")):
        return "playstation"
    if slug.startswith("xbox"):
        return "xbox"
    if slug.startswith(("switch", "nintendo")):
        return "switch"
    if slug.startswith("iphone"):
        return "iphone"
    if slug.startswith("ipad"):
        return "ipad"
    if slug.startswith("apple-watch"):
        return "watch"
    if slug.startswith("macbook"):
        return "macbook"
    if slug.startswith(("imac", "mac-mini", "mac-studio")):
        return "desktop"
    return None  # general pages (shop, android, etc.) stay out of the rotation


def slug_of(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def bank_slugs():
    return {p.stem for p in BANK.glob("*.txt")}


def load_state():
    try:
        return json.loads(STATE.read_text())
    except (OSError, ValueError):
        return {"day": 0, "posted": {}, "history": []}


def pages_by_group():
    by_group = {}
    for url in sitemap_urls():
        g = group_of(url)
        if g:
            by_group.setdefault(g, []).append(url)
    return by_group


def suburb_of(url, title=""):
    slug = slug_of(url)
    for prefix in ("apple-repair-", "iphone-repair-"):
        if slug.startswith(prefix):
            name = slug[len(prefix):].replace("-", " ").title()
            return name.replace("Cbd", "CBD")
    return title or slug.replace("-", " ").title()


def blog_device(slug):
    """Location blogs are already about one device - read it from the start of the slug."""
    for prefix, key in (("apple-watch", "watch"), ("ipad", "ipad"), ("macbook", "macbook"),
                        ("imac", "desktop"), ("mac-mini", "desktop")):
        if slug.startswith(prefix):
            return key
    return "iphone"


def location_combos(areas):
    """Every (area page, device) pair, in the order they get posted."""
    multi = sorted(u for u in areas if "/pages/" in u and not slug_of(u).startswith("iphone-repair-"))
    iphone = sorted(u for u in areas if slug_of(u).startswith("iphone-repair-"))
    iphone = iphone[len(iphone) // 2:] + iphone[:len(iphone) // 2]  # so the same suburb isn't posted twice in a row
    blogs = sorted(u for u in areas if "/blogs/" in u)
    first = []
    for i in range(max(len(multi), len(iphone), len(blogs))):
        if i < len(multi):
            first.append((multi[i], APPLE_DEVICES[i % len(APPLE_DEVICES)][0]))
        if i < len(iphone):
            first.append((iphone[i], "iphone"))
        if i < len(blogs):
            first.append((blogs[i], blog_device(slug_of(blogs[i]))))
    later = [(u, APPLE_DEVICES[(i + r) % len(APPLE_DEVICES)][0])
             for r in range(1, len(APPLE_DEVICES)) for i, u in enumerate(multi)]
    return first + later


def pick_location(state, areas):
    combos = location_combos(areas)
    done = set(state.setdefault("areas_done", []))
    fresh = [c for c in combos if f"{slug_of(c[0])}--{c[1]}" not in done]
    if not fresh:  # every suburb has had every device - start again
        state["areas_done"], fresh = [], combos
    url, device = fresh[0]
    state["areas_done"].append(f"{slug_of(url)}--{device}")
    return url, device


def pick_device_group(state, by_group):
    """Smooth weighted round-robin: bigger groups come up more often, never in long runs.
    Small groups (consoles, controllers) get a minimum weight so they still come round often."""
    live = [(k, l) for k, l in GROUPS if by_group.get(k)]
    weight = {k: max(len(by_group[k]), MIN_WEIGHT) for k, _ in live}
    total = sum(weight.values())
    credits = state.setdefault("credits", {})
    for k, _ in live:
        credits[k] = credits.get(k, 0) + weight[k]
    key, label = max(live, key=lambda g: credits[g[0]])
    credits[key] -= total
    return key, label


def pick_topic(state, location_day):
    """Returns (group, label, url, device). device is set only for location posts."""
    by_group = pages_by_group()
    wanted = os.environ.get("PAGE", "").strip().rstrip("/").rsplit("/", 1)[-1]
    if wanted:  # a specific page was asked for on a manual run
        for key, pages in by_group.items():
            for url in pages:
                if slug_of(url) == wanted:
                    if key == "areas":
                        return key, AREAS_LABEL, url, os.environ.get("DEVICE") or "iphone"
                    return key, dict(GROUPS)[key], url, None
        raise RuntimeError(f"Page '{wanted}' is not in the sitemap or not in a posting group")
    if location_day and by_group.get("areas"):
        url, device = pick_location(state, by_group["areas"])
        return "areas", AREAS_LABEL, url, device
    key, label = pick_device_group(state, by_group)
    pages = by_group[key]
    done = set(state["posted"].get(key, []))
    fresh = [u for u in pages if u not in done]
    if not fresh:  # whole group used - start that group's next round
        state["posted"][key] = []
        fresh = pages
    written = bank_slugs()
    fresh.sort(key=lambda u: slug_of(u) not in written)  # pre-written posts go first
    return key, label, fresh[0], None


# ---------- page reading ----------

def page_facts(url):
    raw = fetch(url)
    title = htmlmod.unescape((re.search(r"<title>(.*?)</title>", raw, re.S) or [None, ""])[1]).strip()
    meta = re.search(r'<meta name="description" content="([^"]*)"', raw)
    meta = htmlmod.unescape(meta.group(1)) if meta else ""
    body = raw.split("<main", 1)[-1].split("</main>", 1)[0]
    body = re.sub(r"<(script|style|svg|noscript)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    text = htmlmod.unescape(re.sub(r"<[^>]+>", " ", body))
    text = re.sub(r"\s+", " ", text).strip()
    return {"title": title.split("|")[0].strip(), "meta": meta, "text": text[:15000]}


# ---------- writing ----------

POST_SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string", "description": "Image headline, max 34 characters"},
        "subline": {"type": "string", "description": "Image sub-line, max 60 characters"},
        "price_from": {"type": "string", "description": "Lowest price exactly as written on the page, e.g. 'R1,299', or '' if none"},
        "summary": {"type": "string", "description": "The Google post text, 600-1200 characters"},
        "cta": {"type": "string", "enum": ["BOOK", "LEARN_MORE"]},
    },
    "required": ["headline", "subline", "price_from", "summary", "cta"],
    "additionalProperties": False,
}

SYSTEM = """You write daily Google Business Profile posts for iAssist Repair, an Apple device and \
games-console repair shop at Shop 4, Silvercrest Shopping Centre, Johannesburg (owner and technician: \
Matthew Robinson). Write in South African English for local customers.

Rules:
- Use only facts found on the page you are given. Never invent prices, turnaround times, warranties, \
parts, models or customer stories.
- Be specific about the repair or device the page is about - name the model and the fault.
- If the page is about an area or suburb, say that iAssist serves that area and mention it once, \
naturally. Do not claim a job was done there.
- No phone numbers, no email addresses, no web addresses, no hashtags, no emojis.
- No "best", "#1", "cheapest" or similar unprovable claims.
- 600-1200 characters, short paragraphs, end with a plain call to action that matches the button.
- price_from: copy the lowest price exactly as it appears on the page (e.g. "R1,299"), or "" if the \
page shows no price.
- cta: BOOK when the page is about a specific repair, LEARN_MORE for model, hub or area pages."""


def write_with_claude(label, url, facts):
    import anthropic

    client = anthropic.Anthropic()
    msg = client.beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": POST_SCHEMA}},
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Topic group: {label}\nPage: {url}\nTitle: {facts['title']}\n"
                       f"Meta description: {facts['meta']}\n\nPage text:\n{facts['text']}",
        }],
    )
    if msg.stop_reason != "end_turn":
        raise RuntimeError(f"Claude stopped with {msg.stop_reason}")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)


def read_bank(slug):
    """Read bank/<slug>.txt:  'Field: value' lines, a line of ---, then the post text."""
    path = BANK / f"{slug}.txt"
    if not path.exists():
        return None
    head, _, body = path.read_text(encoding="utf-8").partition("\n---")
    fields = {}
    for line in head.splitlines():
        name, sep, value = line.partition(":")
        if sep:
            fields[name.strip().lower()] = value.strip()
    button = fields.get("button", "").lower().replace(" ", "")
    return {
        "headline": fields.get("headline", ""),
        "subline": fields.get("subline", ""),
        "price_from": fields.get("price", ""),
        "summary": body.strip(),
        "cta": "BOOK" if button == "book" else "LEARN_MORE",
    }


def write_location_fallback(url, device, facts):
    """Plain area post from the page's own description, used if no post was written for it."""
    dev = dict(APPLE_DEVICES)[device]
    area = suburb_of(url, facts["title"])
    headline = facts["title"] if "/blogs/" in url else f"{dev} Repairs for {area}"
    return {
        "headline": headline,
        "subline": "Shop 4, Silvercrest Shopping Centre, Silvamonte",
        "price_from": "",
        "summary": f"Live or work in {area}? iAssist Repair handles {dev} repairs at our workshop in "
                   f"Silvercrest Shopping Centre, Silvamonte.\n\n{facts['meta']}\n\n"
                   "Every repair starts with a free diagnostic, so you know the cost before any work begins.",
        "cta": "LEARN_MORE",
    }


def write_fallback(label, facts):
    """Plain post from the page's own title + description, used if Claude is unavailable."""
    title = facts["title"] or label
    return {
        "headline": title,
        "subline": label,
        "price_from": "",  # can't tell a "from" price apart from other numbers without Claude
        "summary": f"{title} at iAssist Repair, Silvercrest Shopping Centre.\n\n{facts['meta']}\n\n"
                   "Pop in or book online - we'll check your device and quote before any work starts.",
        "cta": "LEARN_MORE",
    }


PHONE = re.compile(r"(\+27|\b0)[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{4}\b")
WEB = re.compile(r"\b(https?://\S+|www\.\S+|\S+\.(co\.za|net\.za|com)\S*)", re.I)
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")


def clean(post, facts):
    s = PHONE.sub("", post["summary"])
    s = WEB.sub("", s)
    s = EMOJI.sub("", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    post["summary"] = re.sub(r"\n[ \t]+", "\n", s).strip()[:1450]
    price = post.get("price_from", "").strip()
    digits = re.sub(r"\D", "", price)
    page_digits = re.sub(r"[^\dR]", "", facts["text"])
    if not digits or digits not in page_digits:
        price = ""  # never show a price that isn't on the live page
    post["price_from"] = price
    if post.get("cta") not in ("BOOK", "LEARN_MORE"):
        post["cta"] = "LEARN_MORE"
    return post


# ---------- image ----------

def font(size, weight=500):
    f = ImageFont.truetype(str(ASSETS / "Jost.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=fnt) <= width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def icon(draw, key, box, color):
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    lw = 10
    if key in ("iphone", "areas"):
        pw, ph = int(w * 0.48), int(h * 0.92)
        draw.rounded_rectangle([cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2], 46, outline=color, width=lw)
        draw.rounded_rectangle([cx - 45, cy - ph // 2 + 26, cx + 45, cy - ph // 2 + 50], 12, fill=color)
        if key == "areas":  # map pin inside the phone
            r = 52
            draw.ellipse([cx - r, cy - r - 30, cx + r, cy + r - 30], outline=color, width=lw)
            draw.polygon([(cx - 44, cy - 2), (cx + 44, cy - 2), (cx, cy + 90)], fill=color)
            draw.ellipse([cx - 18, cy - 48, cx + 18, cy - 12], fill=SLATE)
    elif key == "ipad":
        pw, ph = int(w * 0.74), int(h * 0.92)
        draw.rounded_rectangle([cx - pw // 2, cy - ph // 2, cx + pw // 2, cy + ph // 2], 40, outline=color, width=lw)
        draw.ellipse([cx - 9, cy - ph // 2 + 22, cx + 9, cy - ph // 2 + 40], fill=color)
    elif key == "watch":
        bw = int(w * 0.36)
        draw.rounded_rectangle([cx - bw // 2 + 14, y0, cx + bw // 2 - 14, y1], 30, outline=color, width=lw)
        draw.rounded_rectangle([cx - bw // 2 - 20, cy - 120, cx + bw // 2 + 20, cy + 120], 56, outline=color, width=lw, fill=SLATE)
        draw.rounded_rectangle([cx + bw // 2 + 18, cy - 40, cx + bw // 2 + 40, cy + 10], 8, fill=color)
    elif key == "macbook":
        sw, sh = int(w * 0.78), int(h * 0.5)
        draw.rounded_rectangle([cx - sw // 2, cy - sh // 2 - 40, cx + sw // 2, cy + sh // 2 - 40], 24, outline=color, width=lw)
        draw.rounded_rectangle([cx - sw // 2 - 50, cy + sh // 2 - 30, cx + sw // 2 + 50, cy + sh // 2], 12, fill=color)
    elif key == "desktop":
        sw, sh = int(w * 0.84), int(h * 0.56)
        draw.rounded_rectangle([cx - sw // 2, y0 + 30, cx + sw // 2, y0 + 30 + sh], 26, outline=color, width=lw)
        draw.polygon([(cx - 50, y0 + 30 + sh), (cx + 50, y0 + 30 + sh), (cx + 80, y0 + sh + 150), (cx - 80, y0 + sh + 150)], outline=color, width=lw)
        draw.rounded_rectangle([cx - 130, y0 + sh + 140, cx + 130, y0 + sh + 160], 8, fill=color)
    elif key in ("controllers", "playstation", "xbox", "switch"):
        gw, gh = int(w * 0.9), int(h * 0.48)
        draw.rounded_rectangle([cx - gw // 2, cy - gh // 2, cx + gw // 2, cy + gh // 2], gh // 2, outline=color, width=lw)
        # d-pad
        dx, dy = cx - gw // 4, cy - 10
        draw.rectangle([dx - 40, dy - 12, dx + 40, dy + 12], fill=color)
        draw.rectangle([dx - 12, dy - 40, dx + 12, dy + 40], fill=color)
        # buttons
        bx, by = cx + gw // 4, cy - 10
        for ox, oy in ((0, -34), (34, 0), (0, 34), (-34, 0)):
            draw.ellipse([bx + ox - 13, by + oy - 13, bx + ox + 13, by + oy + 13], fill=color)


def slugify(text):
    text = text.lower().replace("&", "and").replace("+", "plus")
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:90]


SHOP_GPS = (-26.1367857, 28.1159056)  # Shop 4, Silvercrest Shopping Centre


def dms(value):
    value = abs(value)
    d = int(value)
    m = int((value - d) * 60)
    return (float(d), float(m), round((value - d - m / 60) * 3600, 2))


def image_exif(meta):
    """Title, description (alt text), keywords, author, copyright and the shop's location."""
    exif = Image.Exif()
    utf16 = lambda s: s.encode("utf-16-le") + b"\x00\x00"
    exif[0x010E] = meta["alt"]                          # ImageDescription
    exif[0x013B] = "Matthew Robinson, iAssist Repair"   # Artist
    exif[0x8298] = f"Copyright {datetime.now(SAST).year} iAssist Repair, iassist.net.za"  # Copyright
    exif[0x9C9B] = utf16(meta["title"])                 # XPTitle
    exif[0x9C9C] = utf16(meta["alt"])                   # XPComment
    exif[0x9C9E] = utf16(";".join(meta["keywords"]))    # XPKeywords
    lat, lon = SHOP_GPS
    exif.get_ifd(0x8825).update({1: "S" if lat < 0 else "N", 2: dms(lat), 3: "E" if lon > 0 else "W", 4: dms(lon)})
    return exif


def render(key, label, post, out_path, meta=None):
    W, H = 1200, 900
    img = Image.new("RGB", (W, H), SLATE)
    d = ImageDraw.Draw(img)
    for y in range(H):  # soft vertical gradient
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(SLATE[i] + (SLATE_2[i] - SLATE[i]) * t) for i in range(3)))

    # device icon on the right, faint
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    icon(ImageDraw.Draw(layer), key, (760, 200, 1120, 640), TAN + (70,))
    img.paste(layer, (0, 0), layer)
    d = ImageDraw.Draw(img)

    logo = Image.open(ASSETS / "logo.png").convert("RGBA")
    logo.thumbnail((250, 142))
    img.paste(logo, (64, 52), logo)

    # group chip
    chip_f = font(26, 500)
    chip = label.upper()
    cw = int(d.textlength(chip, font=chip_f)) + 44
    d.rounded_rectangle([64, 250, 64 + cw, 298], 24, outline=TAN, width=2)
    d.text((86, 256), chip, font=chip_f, fill=TAN_LIGHT)

    # headline
    size = 84
    while True:
        hf = font(size, 700)
        lines = wrap(d, post["headline"], hf, 700)
        if len(lines) <= 3 or size <= 56:
            break
        size -= 6
    y = 340
    for line in lines[:3]:
        d.text((64, y), line, font=hf, fill=WHITE)
        y += int(size * 1.12)

    sf = font(36, 400)
    for line in wrap(d, post["subline"], sf, 700)[:2]:
        d.text((64, y + 28), line, font=sf, fill=TAN_LIGHT)
        y += 48

    if post["price_from"]:
        pf = font(40, 600)
        ptxt = f"From {post['price_from']}"
        pw = int(d.textlength(ptxt, font=pf)) + 56
        py = min(max(712, y + 56), 744)
        d.rounded_rectangle([64, py, 64 + pw, py + 64], 10, fill=TAN)
        d.text((92, py + 6), ptxt, font=pf, fill=SLATE)

    d.rectangle([0, H - 72, W, H], fill=(20, 25, 30))
    d.text((64, H - 54), ADDRESS, font=font(28, 400), fill=TAN_LIGHT)
    extra = {"exif": image_exif(meta)} if meta else {}
    img.save(out_path, "JPEG", quality=90, **extra)


# ---------- phases ----------

CONTACT = f"{SITE}/pages/contact"
CALL_DAY = datetime(2026, 10, 29).date()  # first Call now day; then every 3rd day after it
CTA_ENDINGS = {
    "LEARN_MORE": "Tap Learn more for prices and details.",
    "CALL": "Tap Call now to speak to us about your repair.",
    "BOOK": "Tap Book to arrange your repair with us.",
}


def choose_cta(now):
    """Mondays: Book (contact page). Every 3rd day: Call now. Otherwise: Learn more.
    Goes by the calendar, so extra manual posts don't shift the rhythm."""
    forced = os.environ.get("BUTTON", "").strip().upper()
    if forced in CTA_ENDINGS:
        return forced
    if now.weekday() == 0:
        return "BOOK"
    if now.date().toordinal() % 3 == CALL_DAY.toordinal() % 3:
        return "CALL"
    return "LEARN_MORE"


def set_ending(summary, cta, original_cta):
    """Make the last 'Tap ...' line match the button actually shown."""
    if cta == original_cta and summary.rstrip().split("\n")[-1].startswith("Tap "):
        return summary
    paras = summary.rstrip().split("\n\n")
    if paras[-1].startswith("Tap "):
        paras = paras[:-1]
    return "\n\n".join(paras + [CTA_ENDINGS[cta]])


def utm(url, slug):
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}utm_source=google&utm_medium=organic&utm_campaign=gbp_post&utm_content={slug}"


def build():
    state = load_state()
    now = datetime.now(SAST)
    key, label, url, device = pick_topic(state, now.weekday() in LOCATION_DAYS)
    slug = slug_of(url)
    name = f"{slug}--{device}" if device else slug  # bank file / image name
    facts = page_facts(url)
    post, writer = read_bank(name) or (read_bank(slug) if device else None), "bank"
    if not post or not post["summary"]:
        writer = "claude"
        try:
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise RuntimeError("no pre-written post and no ANTHROPIC_API_KEY")
            topic = f"{dict(APPLE_DEVICES)[device]} repairs for people in this area" if device else label
            post = write_with_claude(topic, url, facts)
        except Exception as exc:
            print(f"::warning::Using the plain backup post ({type(exc).__name__}: {exc})")
            post = write_location_fallback(url, device, facts) if device else write_fallback(label, facts)
            writer = "fallback"
    post = clean(post, facts)
    if device:
        post["price_from"] = ""  # suburb pages list many prices; the picture shows device + area instead
    cta = choose_cta(now)
    post["summary"] = set_ending(post["summary"], cta, post["cta"])
    post["cta"] = cta
    used = {h.get("name", slug_of(h["page"])) for h in state["history"]} | {name}
    print(f"Post written by: {writer}. Pre-written posts not used yet: {len(bank_slugs() - used)}")

    today = now.strftime("%Y-%m-%d")
    POSTS_DIR.mkdir(exist_ok=True)
    if device:
        area = suburb_of(url, facts["title"])
        subject = f"{dict(APPLE_DEVICES)[device]} repair {area}" if "/blogs/" not in url else post["headline"]
    else:
        subject = f"{post['headline']} Johannesburg"
    img_name = f"{today}-{slugify(subject)}.jpg"
    alt = f"{post['headline']} at iAssist Repair, Shop 4, Silvercrest Shopping Centre, Silvamonte, Johannesburg"
    render(device or key, label, post, POSTS_DIR / img_name,
           meta={"title": post["headline"], "alt": alt, "keywords": [post["headline"], label, "iAssist Repair", "Johannesburg"]})

    payload = {
        "topic": post["headline"][:58],
        "summary": post["summary"],
        "image_url": f"{PAGES_BASE}/posts/{img_name}",
        "cta_type": post["cta"],
        "cta_url": utm(CONTACT if post["cta"] == "BOOK" else url, name),
        "image_alt": alt,
    }
    POST.write_text(json.dumps(payload, indent=2) + "\n")

    if device:
        if name not in state.setdefault("areas_done", []):  # manual runs skip pick_location
            state["areas_done"].append(name)
    else:
        state["posted"].setdefault(key, []).append(url)
    entry = {"date": today, "group": key, "page": url, "name": name, "writer": writer}
    state["history"] = (state["history"] + [entry])[-400:]
    STATE.write_text(json.dumps(state, indent=2) + "\n")
    print(json.dumps(payload, indent=2))


def send():
    hook = os.environ.get("MAKE_WEBHOOK_URL")
    if not hook:
        sys.exit("::error::MAKE_WEBHOOK_URL secret is not set")
    payload = json.loads(POST.read_text())
    for _ in range(40):  # wait up to ~10 minutes for GitHub Pages to publish the image
        try:
            with urllib.request.urlopen(urllib.request.Request(payload["image_url"], headers=UA), timeout=20) as r:
                if r.status == 200:
                    break
        except Exception:
            pass
        time.sleep(15)
    else:
        sys.exit(f"::error::Image never went live: {payload['image_url']}")
    req = urllib.request.Request(hook, data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        print(f"Make.com replied {r.status}: {r.read().decode()[:200]}")


if __name__ == "__main__":
    {"build": build, "send": send}[sys.argv[1] if len(sys.argv) > 1 else "build"]()
