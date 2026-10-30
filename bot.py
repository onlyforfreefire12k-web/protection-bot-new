#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ GROUP PROTECTOR BOT (Telethon + Flask)
Deploy: Render Web Service -> Start Command: python bot.py  (gunicorn ki zaroorat NAHI)

Run: python bot.py
"""

import html as html_mod
import json
import os
import re
import threading
import time
import unicodedata

from flask import Flask, jsonify

from telethon import Button, TelegramClient, events
from telethon.tl.functions.users import GetFullUserRequest

# ========================= CONFIG =========================
API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
PORT = int(os.environ.get("PORT", "10000"))
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)      # optional: extra /gunmute authority
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0") or 0)  # optional: -100xxxx log channel

EMOJI_LIMIT = 3          # 3 ya usse zyada emojis -> delete
ARABIC_MIN_CHARS = 2     # urdu/arabic script kitne chars par delete
TAMIL_MIN_CHARS = 2
BIO_RECHECK_DAYS = 7     # bio 7 din me ek baar dobara check
NOTICE_COOLDOWN = 15     # group me notices ka spam control (seconds)

DATA_DIR = "data"
GMUTE_FILE = os.path.join(DATA_DIR, "gmute_list.json")
BIOCHECK_FILE = os.path.join(DATA_DIR, "bio_checked.json")
SESSION_PATH = os.path.join(DATA_DIR, "protector_session")

os.makedirs(DATA_DIR, exist_ok=True)

# ================== WORD LISTS (YAHIN EDIT KARO) ==================
# Urdu aur Arabic dono Arabic-script use karte hain -> ek hi range se pakde jaate hain
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                 (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
TAMIL_RANGES = ((0x0B80, 0x0BFF),)

# Roman Tamil / Tanglish — 1 strong word ya 2 weak words -> delete
TAMIL_STRONG_WORDS = [
    "vanakkam", "vanakam", "epdi", "eppadi", "epadi", "machi", "machan", "machaan",
    "ennada", "enna da", "enna ve", "puriyala", "puriyale", "puriyathu", "mudinchu",
    "mudiyala", "mudila", "saptiya", "sapten", "saptacha", "saptengala", "oombu",
    "oombura", "thevudiya", "thevidiya", "punda", "pundai", "labbehen", "labben",
    "labam", "labudus", "kandupidi", "kandupidippa", "edhuku", "ethuku", "ethukku",
    "yaaru", "yaru", "theriyala", "theriyume", "theriyathu", "panra", "panre",
    "panren", "pannitu", "pogala", "pogalae", "pogalaam", "poitu", "poitutu",
    "poittu", "vanthuten", "vandhuten", "vantuten", "irukku", "eruku", "iruke",
    "irukum", "semma", "semme", "semeya", "mokka", "kiruku", "kirukku", "loosu",
    "paitiyam", "paithyam", "bejara", "kudukara", "kuduthutu", "aaprom", "appuram",
    "solren", "sollren", "ketkala", "ketkate", "vendaam", "venam", "vennum",
    "thangachi", "thambi", "polappa", "romba", "konjam", "nallaa", "seri da",
    "sari da", "paaru", "paru", "vanthuru", "enna panra", "enna panre",
]
TAMIL_WEAK_WORDS = [
    "enna", "illa", "ama", "seri", "sari", "nalla", "anna", "akka", "thala",
    "thalaiva", "thalapathy", "ponnu", "payan", "aambala", "figure", "vaa",
    "inga", "anga", "edu", "ethu", "avan", "aval", "amma", "appa", "kelvi",
    "innum", "veedu", "ooru", "oorula", "adhu", "idhu", "indha", "andha",
    "unakku", "enakku", "irukenga", "vanten", "poren", "sollu", "aachu", "pocha",
]

# Instant GMUTE rules (message content) — (regex, chhota english reason)
GMUTE_RULES = [
    (re.compile(r"\bc[o0]me\s+(?:[o0]n\s+)?b[o0]ys?\b"), "promo message (come boys)"),
    (re.compile(r"\bb[o0]ys?\s+(?:come|dm|inbox|join)\b|\b(?:come|join)\s+(?:b[o0]ys?|dears?)\b"), "promo message (boys come/dm)"),
    (re.compile(r"\bdm\b[^.\n]{0,40}\b(?:b[o0]ys?|dears?)\b|\b(?:b[o0]ys?|dears?)\b[^.\n]{0,40}\bdm\b"), "promo message (boys + dm)"),
    (re.compile(r"\bfree\s+(?:sh[o0]w|vide[o0]\s*call|vide[o0]\s*sh[o0]w|full\s*sh[o0]w|vc\b|meet|service|call)\b"), "promo message (free show/vc)"),
    (re.compile(r"\b(?:full|hot|live|privat[e3]|paid|premium)\s+sh[o0]w\b"), "promo message (paid/hot show)"),
    (re.compile(r"child\s*[-._\s]*p[a@o0]r?n"), "banned content (child porn)"),
    (re.compile(r"\bcp\s+(?:link|group|vide[o0]|viral|pack)\b"), "banned content (cp)"),
    (re.compile(r"\b(?:paid|premium)\s+(?:vide[o0]\s*call|vc\b|meet|service|call|fun|time)\b"), "paid service promo"),
    (re.compile(r"\bvide[o0]\s*call\s+(?:service|available|paid|premium)\b|\bvc\s+service\b"), "video call service promo"),
    (re.compile(r"\bprivate\s+vide[o0]\s*call\b"), "private video call promo"),
    (re.compile(r"\b(?:100\s*%?|100\s*percent|hundred\s*percent)\s*(?:real|authentic|genuine)\b"), "100% real promo"),
    (re.compile(r"\b(?:real|genuine)\s+meet\b|\bmeet\s+service\b|\bhome\s+meet\b|\bdoor\s+step\b|\bdoor\s+to\s+door\b"), "real meet promo"),
    (re.compile(r"\bauthentic\s+(?:service|call)\b"), "authentic service promo"),
    (re.compile(r"\bdm\s+me\s+(?:now|fast|fastly|baby|jaan|hun|dear|immediately|urgent)\b"), "dm me promo"),
    (re.compile(r"\b(?:dm|inbox|pm)\b[^.\n]{0,40}\b(?:paid|service|booking|available|advance)\b|\b(?:paid|service|booking|advance)\b[^.\n]{0,40}\b(?:dm|inbox|pm)\b"), "dm for paid service"),
    (re.compile(r"\bn[o0]\s+dem[o0]\b"), "no demo scam promo"),
    (re.compile(r"\btake\s+dem[o0]\b"), "take demo scam promo"),
    (re.compile(r"\bmake\s+sure\s+the\s+service\b"), "service scam promo"),
    (re.compile(r"\bservice\s+dm\b|\bdm\s+for\s+service\b|\bservice\s+available\b"), "service dm promo"),
]

# Bio strong rules — direct hit -> gmute
BIO_STRONG_RULES = [
    (re.compile(r"private\s+vide[o0]\s*call"), "scam bio (private video call)"),
    (re.compile(r"vide[o0]\s*call\s+(?:service|available|paid)"), "scam bio (vc service)"),
    (re.compile(r"\bvc\s+service\b"), "scam bio (vc service)"),
    (re.compile(r"\btake\s+dem[o0]\b|\bmak[e3]\s+sur[e3]\s+th[e3]\s+s[e3]rvic[e3]\b"), "scam bio (take demo / make sure the service)"),
    (re.compile(r"\bn[o0]\s+dem[o0]\b"), "scam bio (no demo)"),
    (re.compile(r"\b(?:100\s*%?|100\s*percent)\s*real\b"), "scam bio (100% real)"),
    (re.compile(r"\b(?:real|genuine)\s+meet\b|\bmeet\s+service\b|\bdoor\s+step\b"), "scam bio (real meet)"),
    (re.compile(r"\bdm\s+me\s+now\b"), "scam bio (dm me now)"),
    (re.compile(r"\bservice\s+dm\b|\bdm\s+for\s+service\b"), "scam bio (service dm)"),
    (re.compile(r"\bpaid\s+(?:service|sh[o0]w|meet|vide[o0]\s*call)\b|\bpremium\s+service\b"), "scam bio (paid service)"),
    (re.compile(r"\bfree\s+(?:sh[o0]w|vide[o0]\s*call|meet)\b"), "scam bio (free show)"),
    (re.compile(r"child\s*[-._\s]*p[a@o0]r?n"), "banned content in bio"),
    (re.compile(r"\bc[o0]me\s+b[o0]ys?\b"), "scam bio (come boys)"),
]

# Bio weak red-flag words — COMBO detection (BIO_WEAK_MIN ya zyada -> gmute)
BIO_WEAK_WORDS = [
    "video call", "vc", "dm me", "dm now", "100%", "100 percent", "real",
    "authentic", "genuine", "service", "demo", "meet", "private", "paid",
    "premium", "no advance", "full show", "come dm", "inbox me", "direct meet",
    "home meet", "available 24", "24/7", "boys", "show", "booking", "original",
]
BIO_WEAK_MIN = 4

# States + major cities (location + couple -> delete)
INDIA_LOCATIONS = [
    "andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa",
    "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala",
    "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland",
    "odisha", "orissa", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana",
    "tripura", "uttar pradesh", "uttaranchal", "uttarakhand", "west bengal", "delhi",
    "new delhi", "jammu & kashmir", "jammu and kashmir", "jammu", "kashmir", "ladakh",
    "chandigarh", "puducherry", "pondicherry", "andaman", "daman", "dadra",
    "mumbai", "pune", "nagpur", "nashik", "thane", "bangalore", "bengaluru", "mysore",
    "chennai", "coimbatore", "madurai", "hyderabad", "secunderabad", "vijayawada",
    "visakhapatnam", "kochi", "cochin", "trivandrum", "kolkata", "howrah",
    "ahmedabad", "surat", "vadodara", "rajkot", "jaipur", "jodhpur", "udaipur",
    "lucknow", "kanpur", "varanasi", "prayagraj", "agra", "noida", "gurgaon",
    "gurugram", "faridabad", "ghaziabad", "indore", "bhopal", "jabalpur", "patna",
    "ranchi", "guwahati", "bhubaneswar", "raipur", "dehradun", "shimla", "amritsar",
    "ludhiana", "jalandhar", "srinagar", "gorakhpur", "allahabad",
]
_LOC_SORTED = sorted(set(INDIA_LOCATIONS), key=len, reverse=True)
LOCATION_RE = re.compile(r"(?<![a-z])(?:" + "|".join(re.escape(x) for x in _LOC_SORTED) + r")(?![a-z])")
COUPLE_RE = re.compile(r"\bc(?:oupl|upl|opl|pl)[e3]s?\b|\bcpl[e3]s?\b")
F2F_RE = re.compile(r"\bf\s*2\s*f\b|\bf\s*to\s*f\b")

TAMIL_STRONG_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in sorted(set(TAMIL_STRONG_WORDS), key=len, reverse=True)) + r")(?![a-z])")
TAMIL_WEAK_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in sorted(set(TAMIL_WEAK_WORDS), key=len, reverse=True)) + r")(?![a-z])")
BIO_WEAK_RE = re.compile(
    r"(?<![a-z0-9])(?:" + "|".join(re.escape(w) for w in sorted(set(BIO_WEAK_WORDS), key=len, reverse=True)) + r")(?![a-z0-9])")

EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\U00002600-\U000026FF"
    "\U00002700-\U000027BF"
    "\U000023E9-\U000023FA"
    "\U00002B00-\U00002BFF"
    "\U0001F000-\U0001F02F"
    "\U0001F0A0-\U0001F0FF"
    "]")

# ========================= PERSISTENCE =========================
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception as e:
        print("[save-err]", e)

gmute_db = load_json(GMUTE_FILE, {})    # "uid" -> {"reason":..., "time":...}
bio_checked = load_json(BIOCHECK_FILE, {})  # "uid" -> last check timestamp

BIO_LOCK = threading.Lock()
BIO_DIRTY = threading.Event()
BIO_INFLIGHT = set()
admin_cache = {}          # (chat_id, uid) -> (ts, bool)
last_notice = {}          # chat_id -> ts

def is_gmuted(uid):
    return str(uid) in gmute_db

def add_gmute(uid, reason):
    gmute_db[str(uid)] = {"reason": reason, "time": time.time(), "by": "auto"}
    save_json(GMUTE_FILE, gmute_db)

def remove_gmute(uid):
    existed = gmute_db.pop(str(uid), None) is not None
    save_json(GMUTE_FILE, gmute_db)
    return existed

def dirty_saver():
    while True:
        BIO_DIRTY.wait()
        time.sleep(3)
        BIO_DIRTY.clear()
        with BIO_LOCK:
            save_json(BIOCHECK_FILE, bio_checked)

# ========================= CLIENT =========================
client = TelegramClient(SESSION_PATH, API_ID, API_HASH,
                        connection_retries=None, retry_delay=3)

ME_ID = 0
ME_USERNAME = ""

# ========================= HELPERS =========================
def norm_text(text):
    """𝗣𝗿𝗶𝘃𝗮𝘁𝗲 𝘃𝗶𝗱𝗲𝗼 𝗰𝗮𝗹𝗹 -> private video call  (koi bhi styled font plain ban jaata hai)"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u00a0", " ")
    t = re.sub(r"[\u200b-\u200f\u2060-\u2064\ufeff\u00ad]", "", t)  # zero-width evasion
    return t.lower()

def deleet_text(t):
    """p0rn / c0me / d0or type leet ko second pass me pakadne ke liye"""
    return t.translate(str.maketrans({"0": "o", "3": "e", "4": "a", "5": "s",
                                      "7": "t", "@": "a", "$": "s", "1": "i"}))

def script_count(text, ranges):
    n = 0
    for ch in text:
        cp = ord(ch)
        for lo, hi in ranges:
            if lo <= cp <= hi:
                n += 1
                break
    return n

def emoji_count(text):
    if not text:
        return 0
    s = re.sub(r"[\U0001F3FB-\U0001F3FF\uFE0F\u200D\u20E3]", "", text)  # modifiers hatao
    flags = len(re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", s))           # flag = 1 emoji
    s = re.sub(r"[\U0001F1E6-\U0001F1FF]{2}", "", s)
    return flags + len(EMOJI_RE.findall(s))

async def is_group_admin(chat_id, user_id):
    if OWNER_ID and user_id == OWNER_ID:
        return True
    key = (chat_id, user_id)
    now = time.time()
    cached = admin_cache.get(key)
    if cached and now - cached[0] < 600:
        return cached[1]
    res = False
    try:
        chat = await client.get_entity(chat_id)
        p = await client.get_permissions(chat, user_id)
        res = bool(p and (p.is_admin or p.is_creator))
    except Exception:
        res = False
    admin_cache[key] = (now, res)
    return res

async def safe_delete(event):
    try:
        await event.delete()
        return True
    except Exception as e:
        print(f"[delete-failed] {type(e).__name__}: {e} (bot ko admin banao!)")
        return False

async def log_action(text):
    if not LOG_CHANNEL:
        return
    try:
        await client.send_message(LOG_CHANNEL, text, parse_mode="html", link_preview=False)
    except Exception as e:
        print("[log-err]", e)

async def notify_gmute(chat_id, uid, name, reason):
    """Chhota notice + english reason — spam control ke sath."""
    now = time.time()
    if now - last_notice.get(chat_id, 0.0) < NOTICE_COOLDOWN:
        return
    last_notice[chat_id] = now
    mention = f'<a href="tg://user?id={uid}">{html_mod.escape(str(name))}</a>'
    text = (f"🚫 <b>GLOBAL MUTE</b>\n"
            f"👤 User: {mention} (<code>{uid}</code>)\n"
            f"🧾 Reason: {html_mod.escape(str(reason))}\n"
            f"🤐 Is user ke saare messages ab auto-delete honge.\n"
            f"💡 Admin undo: reply <code>/gunmute</code>")
    try:
        await client.send_message(chat_id, text, parse_mode="html", link_preview=False)
    except Exception as e:
        print("[notice-err]", e)

# ========================= BIO SCANNER =========================
async def fetch_bio(uid):
    try:
        ent = await client.get_entity(uid)
        full = await client(GetFullUserRequest(ent))
        return full.full_user.about or ""
    except Exception as e:
        print(f"[bio-fetch-err {uid}] {type(e).__name__}")
        return None

def bio_is_scam(bio):
    t = norm_text(bio)
    if not t:
        return False, None
    for rx, reason in BIO_STRONG_RULES:
        if rx.search(t):
            return True, reason
    hits = len(BIO_WEAK_RE.findall(t))
    if hits >= BIO_WEAK_MIN:  # word COMBINATION -> gmute
        return True, f"scam bio pattern combo ({hits} red flags)"
    return False, None

async def scan_bio(user, chat_id):
    uid = getattr(user, "id", None)
    if uid is None or is_gmuted(uid):
        return
    key = str(uid)
    now = time.time()
    with BIO_LOCK:
        last = bio_checked.get(key, 0)
    if now - last < BIO_RECHECK_DAYS * 86400 or key in BIO_INFLIGHT:
        return
    BIO_INFLIGHT.add(key)
    try:
        bio = await fetch_bio(uid)
        with BIO_LOCK:
            bio_checked[key] = now
            BIO_DIRTY.set()
        if bio:
            bad, why = bio_is_scam(bio)
            if bad and not is_gmuted(uid):
                add_gmute(uid, why)
                name = getattr(user, "first_name", None) or "user"
                await notify_gmute(chat_id, uid, name, why)
                await log_action(f"🚫 <b>GMUTE (bio)</b> <code>{uid}</code> — {html_mod.escape(why)}")
    except Exception as e:
        print("[bio-scan-err]", e)
    finally:
        BIO_INFLIGHT.discard(key)

# ========================= MAIN MESSAGE LOGIC =========================
async def process_group_message(event):
    try:
        sender = await event.get_sender()
    except Exception:
        return
    if sender is None or getattr(sender, "bot", False):
        return
    uid = sender.id
    if uid == ME_ID:
        return
    if await is_group_admin(event.chat_id, uid):
        return  # admins ko kuch nahi hoga

    # 1) pehle se gmute hai -> silent delete
    if is_gmuted(uid):
        await safe_delete(event)
        return

    # 2) bio scan (har user ka, ek baar; 7 din me recheck)
    client.loop.create_task(scan_bio(sender, event.chat_id))

    text = event.raw_text or ""
    if not text.strip():
        return
    t = norm_text(text)
    t2 = deleet_text(t)

    # 3) instant GMUTE triggers (scam / paid promo / banned words)
    for rx, reason in GMUTE_RULES:
        if rx.search(t) or rx.search(t2):
            await safe_delete(event)
            if not is_gmuted(uid):
                add_gmute(uid, reason)
            name = getattr(sender, "first_name", None) or "user"
            await notify_gmute(event.chat_id, uid, name, reason)
            await log_action(f"🚫 <b>GMUTE</b> <code>{uid}</code> — {html_mod.escape(reason)}")
            print(f"[gmute] uid={uid} reason={reason}")
            return

    # 4) Urdu / Arabic script
    if script_count(t, ARABIC_RANGES) >= ARABIC_MIN_CHARS:
        await safe_delete(event)
        print(f"[delete] urdu/arabic uid={uid}")
        return

    # 5) Tamil script
    if script_count(t, TAMIL_RANGES) >= TAMIL_MIN_CHARS:
        await safe_delete(event)
        print(f"[delete] tamil-script uid={uid}")
        return

    # 6) Roman Tamil (Tanglish): 1 strong ya 2 weak words
    if TAMIL_STRONG_RE.search(t) or len(TAMIL_WEAK_RE.findall(t)) >= 2:
        await safe_delete(event)
        print(f"[delete] roman-tamil uid={uid}")
        return

    # 7) 3+ emojis combination
    if emoji_count(text) >= EMOJI_LIMIT:
        await safe_delete(event)
        print(f"[delete] 3+ emojis uid={uid}")
        return

    # 8) f2f
    if F2F_RE.search(t):
        await safe_delete(event)
        print(f"[delete] f2f uid={uid}")
        return

    # 9) State/City + couple
    if LOCATION_RE.search(t) and COUPLE_RE.search(t):
        await safe_delete(event)
        print(f"[delete] location+couple uid={uid}")
        return

@client.on(events.NewMessage(incoming=True))
async def on_new_message(event):
    if event.is_group:
        await process_group_message(event)

@client.on(events.MessageEdited(incoming=True))
async def on_edited_message(event):
    if event.is_group:
        await process_group_message(event)

# ========================= /gunmute =========================
@client.on(events.NewMessage(pattern=r"^/gunmute(?:@\S+)?(?:\s+(.+))?$", incoming=True))
async def on_gunmute(event):
    if event.is_group:
        allowed = await is_group_admin(event.chat_id, event.sender_id)
        if not allowed:
            await event.reply("⛔ Sirf group admins /gunmute use kar sakte hain.")
            return
    else:
        if not (OWNER_ID and event.sender_id == OWNER_ID):
            return
    target_id = None
    reply = await event.get_reply_message()
    if reply is not None and reply.sender_id and reply.sender_id != ME_ID:
        target_id = reply.sender_id
    arg = (event.pattern_match.group(1) or "").strip()
    if target_id is None and arg:
        try:
            ent = await client.get_entity(int(arg) if arg.lstrip("-").isdigit() else arg)
            target_id = ent.id
        except Exception:
            target_id = None
    if target_id is None:
        await event.reply("ℹ️ Kisi user ke message ko REPLY karke <code>/gunmute</code> likho, "
                          "ya <code>/gunmute &lt;user_id|@username&gt;</code>", parse_mode="html")
        return
    existed = remove_gmute(target_id)
    name = str(target_id)
    try:
        ent = await client.get_entity(target_id)
        name = getattr(ent, "first_name", None) or name
    except Exception:
        pass
    mention = f'<a href="tg://user?id={target_id}">{html_mod.escape(name)}</a>'
    if existed:
        await event.reply(f"✅ {mention} ko <b>global mute list</b> se hata diya gaya. "
                          f"Ab uske messages delete nahi honge.", parse_mode="html")
    else:
        await event.reply(f"ℹ️ {mention} mute list me tha hi nahi — sab clean hai.", parse_mode="html")

# ========================= DM /start UI =========================
START_TEXT = (
    "🛡️ <b>GROUP PROTECTOR BOT</b> — Feature Menu\n\n"
    "🧹 <b>AUTO-DELETE</b>\n"
    "• Urdu / Arabic messages → 🗑️ instant delete\n"
    "• Tamil (script) messages → 🗑️ instant delete\n"
    "• Roman Tamil / Tanglish → 🗑️ instant delete\n"
    "• State/City + <i>couple</i> promo → 🗑️ instant delete\n"
    "• <code>f2f</code> messages → 🗑️ instant delete\n"
    "• 3+ emojis ek message me → 🗑️ instant delete\n\n"
    "🤐 <b>AUTO GLOBAL-MUTE (gmute list)</b>\n"
    "• Scam / paid promo words: <i>come boys dm, free show, child porn, paid service, "
    "video call service, dm me now…</i> → gmute + chhota English reason\n"
    "• <b>Bio Scanner 🔎</b>: scam bio (<i>private video call, 100% real, take demo, no demo, "
    "service dm, dm me now…</i> — kisi bhi styled font me) → user gmute list me → "
    "uske saare messages auto-delete\n"
    "• Word combination yaad rehta hai — bio copy-paste na bhi ho to bhi pakda jayega\n\n"
    "♻️ Gmute list permanent — restart ke baad bhi active.\n\n"
    "⚙️ <b>COMMAND</b>\n"
    "• <code>/gunmute</code> — user ke message ko reply karke mute list se remove (admin only)\n"
    "• <code>/start</code> — ye menu (DM only)\n\n"
    "📌 <b>Setup:</b> Bot ko group me <b>Admin</b> banayein (Delete Messages ON).\n"
    "💬 Deletes silent hote hain, sirf gmute par chhota English reason aata hai."
)

@client.on(events.NewMessage(pattern=r"^/(start|help)(?:@\S+)?$", incoming=True))
async def on_start(event):
    if not event.is_private:
        return
    buttons = [[Button.inline("❌ Close", b"close")]]
    if ME_USERNAME:
        buttons = [[Button.url("➕ Add Me To Group", f"https://t.me/{ME_USERNAME}?startgroup=true")],
                   [Button.inline("❌ Close", b"close")]]
    await event.reply(START_TEXT, parse_mode="html", buttons=buttons, link_preview=False)

@client.on(events.CallbackQuery(data=b"close"))
async def on_close(event):
    try:
        await event.delete()
    except Exception:
        pass

# ========================= GROUP INTRO / NEW MEMBERS =========================
GROUP_INTRO = (
    "🛡️ <b>Group Protector activated!</b>\n"
    "⚠️ Mujhe <b>Admin</b> banao with <b>Delete Messages</b> permission, "
    "warna delete/gmute kaam nahi karega.\n"
    "✅ Urdu/Arabic/Tamil auto-delete • scam promo auto-gmute • bio scanner • "
    "3+ emoji delete • f2f delete • state+couple delete\n"
    "📩 Full menu: DM me <code>/start</code>"
)

@client.on(events.ChatAction())
async def on_chat_action(event):
    try:
        users = list(event.users or [])
    except Exception:
        users = []
    if not users:
        return
    for uid in users:
        if uid == ME_ID:
            try:
                await event.reply(GROUP_INTRO, parse_mode="html", link_preview=False)
            except Exception:
                pass
            continue
        if is_gmuted(uid):
            continue
        try:
            ent = await client.get_entity(uid)
        except Exception:
            continue
        client.loop.create_task(scan_bio(ent, event.chat_id))

# ========================= FLASK SERVER =========================
app = Flask(__name__)
START_TIME = time.time()

@app.route("/")
def home():
    return (f"<h2>🛡️ Group Protector Bot is running</h2>"
            f"<p>Uptime: {int(time.time() - START_TIME)}s | "
            f"Gmuted users: {len(gmute_db)} | Bio scanned: {len(bio_checked)}</p>")

@app.route("/health")
def health():
    return jsonify({"ok": True, "gmuted": len(gmute_db), "bio_scanned": len(bio_checked),
                    "uptime": int(time.time() - START_TIME)})

def run_flask():
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)

# ========================= MAIN =========================
def main():
    global ME_ID, ME_USERNAME
    if not (API_ID and API_HASH and BOT_TOKEN):
        raise SystemExit("❌ API_ID, API_HASH, BOT_TOKEN env variables set karo!")
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=dirty_saver, daemon=True).start()
    me = client.start(bot_token=BOT_TOKEN)
    ME_ID = me.id
    ME_USERNAME = me.username or ""
    print(f"✅ Bot started as @{ME_USERNAME} (id={ME_ID}) | Flask on port {PORT}")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
