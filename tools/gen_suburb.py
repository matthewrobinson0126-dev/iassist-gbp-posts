"""Suburb x device posts for the 'Apple Repair <area>' pages.

Every part below was written for these posts; each post combines one version of each part
with that suburb page's own facts (name, distance, drive time), so no two posts are the same.
"""
import hashlib
import re

DEV = {"iphone": "iPhone", "ipad": "iPad", "macbook": "MacBook", "watch": "Apple Watch", "desktop": "iMac & Mac mini"}

OPENERS = {
    "iphone": [
        "Cracked iPhone screen, a battery that's flat by lunch, or a phone that only charges at a certain angle?",
        "Is your iPhone struggling: slow, dying early, or showing a cracked screen every time you pick it up?",
        "Dropped your iPhone? Whether it's the screen, the back glass or the camera, it can usually be fixed for far less than a new phone.",
        "iPhone not charging, Face ID not working, or a battery that needs a power bank to get through the day?",
        "Don't replace your iPhone just because the screen cracked or the battery is tired.",
    ],
    "ipad": [
        "Cracked iPad screen, a battery that drains too quickly, or a charging port that's stopped working?",
        "Has your iPad survived a few drops, but now the glass is cracked or the touch has stopped responding?",
        "iPad slow to charge, or not charging at all? It's often the port, and that can be repaired.",
        "Kids' iPad cracked again? On many models we can replace just the glass, which costs less than a full screen.",
        "An iPad that won't charge, won't hold a charge or has a shattered screen is usually worth repairing.",
    ],
    "macbook": [
        "MacBook running hot with a loud fan, a battery that won't last, or a keyboard that's started playing up?",
        "Spilled something on your MacBook? Switch it off and get it to a technician as soon as you can.",
        "Cracked MacBook screen, sticky keys or a trackpad that won't click? These are everyday repairs for us.",
        "MacBook not charging, not turning on, or showing a 'Service Battery' warning?",
        "A slow, overheating or dead MacBook is usually worth repairing before you spend on a new one.",
    ],
    "watch": [
        "Apple Watch screen cracked, battery fading by the afternoon, or the heart rate sensor stopped reading?",
        "Is your Apple Watch not lasting a full day any more, or not charging at all?",
        "Cracked the glass on your Apple Watch? On many models we can replace just the glass.",
        "Digital Crown stuck, side button not clicking, or straps that won't lock in? Small Apple Watch faults are quick fixes.",
        "Apple Watch screen lifting off the case? That can be a swollen battery, so stop wearing it and get it checked.",
    ],
    "desktop": [
        "Slow iMac, a Mac mini that won't start, or a desktop Mac that's started overheating?",
        "Older iMac taking minutes to start up? An SSD upgrade usually makes it feel like a new computer.",
        "iMac screen cracked, not powering on, or shutting down by itself?",
        "Mac mini not booting, ports not working, or running out of storage?",
        "Before replacing your iMac or Mac mini, find out whether a repair or upgrade will do the job.",
    ],
}

LOCAL = [
    "Our workshop at Silvercrest Shopping Centre in Silvamonte is about {km} km from {area}, roughly {mins} minutes' drive. You don't have to make the trip, though: for a flat R300 we collect from your door and bring it back once it's fixed, insured both ways.",
    "{area} is about {km} km from our workshop at Silvercrest Shopping Centre in Silvamonte, roughly {mins} minutes away. If you'd rather not drive, we collect from {area} for a flat R300 and return your {dev} when it's done, fully insured.",
    "We're about {km} km from {area}, roughly {mins} minutes' drive to Silvercrest Shopping Centre in Silvamonte. Or use our R300 door-to-door collection instead: we collect, repair and return, insured both ways.",
    "From {area} it's about {km} km to our workshop at Silvercrest Shopping Centre in Silvamonte, roughly {mins} minutes' drive. Or skip the traffic: our courier collects from your door for a flat R300 and brings it back once it's repaired.",
]

LOCAL_FAR = [
    "{area} is outside our Gauteng collection area, but your {dev} can still come to us. The Courier Guy collects from your door, we repair it at our lab in Silvamonte, Johannesburg, and they deliver it back to you.",
    "Wherever you are in {area}, The Courier Guy can collect your {dev} from your door, bring it to our lab in Silvamonte, Johannesburg, and deliver it back once it's repaired.",
]

SERVICE = {
    "iphone": [
        "We repair iPhone screens, batteries, charging ports, cameras, back glass and Face ID, and we do board-level work that many repairers send away.",
        "Screens, batteries, charging ports, cameras, Face ID and water damage: we handle iPhone repairs at component level in our static-safe lab.",
        "From a new battery or screen to charging IC and logic board faults, we repair iPhones at component level.",
    ],
    "ipad": [
        "We repair iPad screens, including glass-only repairs on many models, as well as batteries, charging ports and cameras.",
        "Screens, batteries, charging ports, cameras and buttons: we repair every iPad, from older models to the latest iPad Pro.",
        "Charging ports are repaired with micro-soldering, so your data stays in place, and on many models we replace just the cracked glass.",
    ],
    "macbook": [
        "We repair MacBook screens, batteries, keyboards, trackpads and charging ports, and we handle liquid damage and logic board faults at component level.",
        "Batteries, screens, keyboards, charging ports, liquid damage and SSD upgrades: we repair MacBook Air and MacBook Pro at component level in our static-safe lab.",
        "From a new battery or keyboard to liquid damage and logic board repairs, we fix MacBooks properly, at component level.",
    ],
    "watch": [
        "We repair every Apple Watch from Series 1 to Ultra: screens, batteries, back glass and health sensors, crowns, buttons and band lugs, finished with a cold-press reseal.",
        "Screens, batteries, back glass, health sensors, crowns and buttons: we repair every Apple Watch model and reseal it properly afterwards.",
        "From a cracked screen or tired battery to heart rate and ECG sensor faults, we repair Apple Watch Series, SE and Ultra models.",
    ],
    "desktop": [
        "We repair and upgrade iMacs and Mac minis: SSD and RAM upgrades, cooling services, power supplies, liquid damage and logic board faults.",
        "SSD upgrades, thermal services, power supply and logic board repairs, data recovery and macOS upgrades: we keep iMacs and Mac minis running.",
        "From an SSD upgrade that brings an old iMac back to life to chip-level logic board repairs, we handle desktop Macs at component level.",
    ],
}

TRUST = [
    "Every repair starts with a free diagnostic, so you know what's wrong and what it costs before any work begins. Repairs carry a 6-month warranty.",
    "The diagnostic is free, you get the price before we start, and every repair carries a 6-month warranty.",
    "Every job starts with a free diagnostic and a clear price, and comes with a 6-month warranty.",
]

CLOSE = [
    "Tap Learn more for {area} collection details.",
    "Tap Learn more to see how collection from {area} works.",
    "Tap Learn more for Apple repairs in {area}.",
]

SUBLINE = [
    "We collect from {area} for a flat R300",
    "{km} km away, or we collect for R300",
    "Free diagnostic and a 6-month warranty",
]
SUBLINE_FAR = ["Courier collection anywhere in {area}", "Free diagnostic and a 6-month warranty"]


def pick(options, key, salt):
    h = int(hashlib.md5(f"{key}|{salt}".encode()).hexdigest(), 16)
    return options[h % len(options)]


def area_of(title):
    t = re.sub(r"^Apple Repair\s*(in\s*)?", "", title.split("|")[0].split(" — ")[0]).strip(" -–")
    return t or "your area"


def distance(text):
    m = re.search(r"(\d+)\s?km\s*·\s*~?(\d+)\s?min", text)
    return (m.group(1), m.group(2)) if m else (None, None)


LOCAL_GAUTENG = [
    "We collect anywhere in Gauteng for a flat R300, door to door and insured both ways. Or drop your {dev} off at our workshop at Silvercrest Shopping Centre in Silvamonte.",
    "Wherever you are in Gauteng, our courier collects your {dev} for a flat R300 and returns it once it's repaired. Prefer to drop it off yourself? We're at Silvercrest Shopping Centre in Silvamonte.",
]
LOCAL_NATIONAL = [
    "Not in Gauteng? The Courier Guy collects your {dev} from anywhere in South Africa, we repair it at our lab in Silvamonte, Johannesburg, and they deliver it back. In Gauteng we collect for a flat R300.",
    "From Cape Town to Polokwane, The Courier Guy can collect your {dev} from your door and bring it to our lab in Silvamonte, Johannesburg. Once it's repaired, it's delivered straight back to you.",
]
AREA_OVERRIDE = {"locations-gauteng": "Gauteng", "national-courier-repairs": "South Africa"}


def build(name, url, device, facts):
    slug = url.rstrip("/").rsplit("/", 1)[-1]
    area = AREA_OVERRIDE.get(slug) or area_of(facts["title"])
    km, mins = distance(facts["text"] + " " + facts["meta"])
    dev = DEV[device]
    if area == "Gauteng":
        local, head = pick(LOCAL_GAUTENG, name, "l"), f"{dev} Repairs Across Gauteng"
        sub, close = "R300 collection anywhere in Gauteng", pick(CLOSE[:2], name, "c")
    elif area == "South Africa":
        local, head = pick(LOCAL_NATIONAL, name, "l"), f"{dev} Repairs Nationwide"
        sub, close = "Courier collection anywhere in South Africa", "Tap Learn more for how nationwide courier repairs work."
    elif km:
        local, head = pick(LOCAL, name, "l"), f"{dev} Repairs for {area}"
        sub, close = pick(SUBLINE, name, "u"), pick(CLOSE, name, "c")
    else:  # a province outside Gauteng
        if area in ("Western Cape", "Eastern Cape", "Northern Cape", "Free State", "North West"):
            area = "the " + area
        local, head = pick(LOCAL_FAR, name, "l"), f"{dev} Repairs in {area}"
        sub, close = pick(SUBLINE_FAR, name, "u"), pick(CLOSE[1:], name, "c")
    local = local.format(area=area, km=km, mins=mins, dev=dev)
    body = "\n\n".join([
        pick(OPENERS[device], name, "o"),
        local[0].upper() + local[1:],
        pick(SERVICE[device], name, "s"),
        pick(TRUST, name, "t"),
        close.format(area=area),
    ])
    return head, sub.format(area=area, km=km), body
