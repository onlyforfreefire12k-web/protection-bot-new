#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🛡️ GROUP PROTECTOR BOT v3 (Telethon + Flask)
- Urdu/Arabic/Tamil/Telugu (script) messages -> delete
- Tanglish promo phrases (mood ah irukkura boys vanga type) -> delete
- Family abuse combo (dirty word + family word) -> delete
- Adult bait (teen boy here, bull here, secret chat, koi ladki...) -> delete
- 3+ emoji -> delete + name/bio check (Urdu/Arabic script in name/bio -> permanent delete list)
- Paid/scam promo -> auto gmute (English reason)
- Bio/Name/Username scam words -> auto gmute
- f2f, state+couple -> delete
- /gunmute (admins only, emoji-watch bhi clear karta hai) | /start DM menu
Deploy: Render Web Service -> Start Command: python bot.py
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
OWNER_ID = int(os.environ.get("OWNER_ID", "0") or 0)
LOG_CHANNEL = int(os.environ.get("LOG_CHANNEL", "0") or 0)

EMOJI_LIMIT = 3
ARABIC_MIN_CHARS = 2
TAMIL_MIN_CHARS = 2
TELUGU_MIN_CHARS = 2
NAME_SCRIPT_MIN_CHARS = 2      # name/bio me itne Urdu/Arabic chars -> emoji-watch
NOTICE_COOLDOWN = 15

BIO_RECHECK_HOURS = 6
BIO_EMPTY_RECHECK_MIN = 30
BIO_FAIL_RECHECK_MIN = 10

DELETE_GMUTED_ADMINS = os.environ.get("DELETE_GMUTED_ADMINS", "0") == "1"

DATA_DIR = "data"
GMUTE_FILE = os.path.join(DATA_DIR, "gmute_list.json")
BIOCHECK_FILE = os.path.join(DATA_DIR, "bio_checked.json")
EMOJIWATCH_FILE = os.path.join(DATA_DIR, "emoji_watch.json")   # 🆕
SESSION_PATH = os.path.join(DATA_DIR, "protector_session")

os.makedirs(DATA_DIR, exist_ok=True)

# ================== SCRIPT RANGES ==================
ARABIC_RANGES = ((0x0600, 0x06FF), (0x0750, 0x077F), (0x08A0, 0x08FF),
                 (0xFB50, 0xFDFF), (0xFE70, 0xFEFF))
TAMIL_RANGES = ((0x0B80, 0x0BFF),)
TELUGU_RANGES = ((0x0C00, 0x0C7F),)

# ================== TANGLISH PROMO (🆕 sirf ye phrases — broad lists HATA DI) ==================
# Normal roman hindi messages ab safe hain. Sirf ye promo phrases delete honge:
TANGLISH_PROMO_PATTERNS = [
    r"\bm[o0][o0]d\s*a+h?\s*ir?u?k?k?u\w*",                      # mood ah irukkura / mood a irukura
    r"\bir?u?k?k?u\w*\s*boys?\s*va?ng[a@]",                      # irukkura boys vanga
    r"\bboys?\s*va?ng[a@]",                                      # boys vanga
    r"\bva?ng[a@]\s*boys?",                                      # vanga boys
    r"\bm[o0][o0]d\s*ir?u?k?k?u\w*",                             # mood irukura
]
TANGLISH_PROMO_RE = re.compile("|".join(TANGLISH_PROMO_PATTERNS))

# ================== GMUTE RULES (message) ==================
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

# ============ BIO/NAME SIMPLE WORD LIST (NO CHANGES — same as before) ============
BIO_BAN_PATTERNS = [
    ("service",   re.compile(r"\bserv[i1]c[e3]s?\b")),
    ("100%",      re.compile(r"1[o0]0\s*%|1[o0]0\s*percent")),
    ("callgirl",  re.compile(r"\bcall\s*girls?\b|\bcallgirls?\b")),
    ("real meet", re.compile(r"\bre[a@]l\s+m[e3][e3]t\b")),
    ("provider",  re.compile(r"\bprov[i1]d[e3]r?s?\b")),
    ("demo",      re.compile(r"\bd[e3]m[o0]s?\b")),
    ("come",      re.compile(r"\bc[o0]m[e3]\b")),
]

# ============ FAMILY ABUSE COMBO (NO CHANGES) ============
FAMILY_WORDS = [
    "mummy", "mom", "mommy", "mother", "maa", "ma", "mama", "ammi", "amma",
    "behen", "behn", "bhen", "sister", "sis", "didi",
    "bhabhi", "bhabi", "wife", "biwi", "patni", "gharwali", "saali", "saala",
    "beti", "beta", "daughter", "son", "bacha", "bachchi",
    "chachi", "mausi", "mousi", "bua", "aunty", "aanti", "anti",
    "nani", "nana", "dadi", "dada", "bhai", "bhaiya", "brother", "cousin",
    "jija", "jeth", "devar", "nanad", "family",
]
DIRTY_PATTERNS = [
    r"\bch[o0]d\w*", r"\bchud\w*", r"\bch[u1]t\w*", r"\bch[u1]ch[i1]\b",
    r"\bg[a@][a@]?nd\w*", r"\bbh[o0]sd\w*", r"\bchutiy[a@]\w*",
    r"\bfu?c?k\w*", r"\bsex\b|\bsexx+\b",
    r"\b(?:sexy?|hot|dirt[iy])\s+(?:baat\w*|chat|talk|video|pic[sz]?|photo[sz]?|call|service)\b",
    r"\bgand[iy]+\s+baat\w*",
    r"\bra?p[e3]\w*",
    r"\b(?:lund|la?w?d[a@]|l[o0]d[a@]|l[o0]d[e3])\b",
    r"\b(?:raand|rand[i1])\b",
    r"\bb[o0][o0]bs?\b",
    r"\b(?:nud[e3]s?|nangi)\b",
    r"\b(?:kamin[e3]|haram[i1]|haramzad[a@]|kut[i1]y[a@]|kutt[e3]|kutt[i1])\b",
    r"\bpelu?nga\b|\bpel\s?diya\b|\bpel\s?denge\b",
]

# ============ ADULT BAIT (NO CHANGES) ============
BAIT_DELETE_RULES = [
    (re.compile(r"\bteens?\s+bo[iy]s?\b|\bteens?\s+girls?\b"), "adult bait (teen)"),
    (re.compile(r"\bbulls?\s*(?:here|for|available|needed|wanted|cpl|couple|ready|cuckold)\b|\bcuckold\s+bulls?\b"), "adult bait (bull)"),
    (re.compile(r"\bsec[r3][e3]c?ts?\s*cha?ts?\b|\bsecret\s*cha?ts?\b"), "adult bait (secret chat)"),
]
GIRL_BAIT_RE = re.compile(
    r"\b(?:koi|any|koyi?)\s+(?:ladki|larki|girl|girls|aunty|bhabhi|lady|ladies|mausi)\b"
    r"|\b(?:ladki|girls?)\s+(?:here|available|online)\b")
SEXT_CONTEXT_RE = re.compile(
    r"\b(?:secret\s*cha?t|cha?t\s+kare\w*|dm|inbox|msg|baat\s+kare\w*|available|online|here|join|karo|karlo|karegi|karenge|ban[ea]gi|ban[ea]nge|hongi|honge)\b")

# ============ STATES + CITIES (NO CHANGES) ============
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

FAMILY_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(w) for w in sorted(set(FAMILY_WORDS), key=len, reverse=True)) + r")(?![a-z])")
DIRTY_RE = re.compile("|".join(DIRTY_PATTERNS))

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

gmute_db = load_json(GMUTE_FILE, {})
bio_checked = load_json(BIOCHECK_FILE, {})
emoji_watch = load_json(EMOJIWATCH_FILE, {})   # 🆕 uid -> {"reason":..., "time":...}

BIO_LOCK = threading.Lock()
BIO_DIRTY = threading.Event()
BIO_INFLIGHT = set()
EW_LOCK = threading.Lock()
EW_INFLIGHT = set()
admin_cache = {}
last_notice = {}

def is_gmuted(uid):
    return str(uid) in gmute_db

def add_gmute(uid, reason):
    gmute_db[str(uid)] = {"reason": reason, "time": time.time(), "by": "auto"}
    save_json(GMUTE_FILE, gmute_db)

def remove_gmute(uid):
    existed = gmute_db.pop(str(uid), None) is not None
    save_json(GMUTE_FILE, gmute_db)
    return existed

def is_emoji_watched(uid):
    return str(uid) in emoji_watch

def add_emoji_watch(uid, reason):
    emoji_watch[str(uid)] = {"reason": reason, "time": time.time()}
    save_json(EMOJIWATCH_FILE, emoji_watch)

def remove_emoji_watch(uid):
    return emoji_watch.pop(str(uid), None) is not None

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
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("\u00a0", " ")
    t = re.sub(r"[\u200b-\u200f\u2060-\u2064\ufeff\u00ad]", "", t)
    return t.lower()

def deleet_text(t):
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
    s = re.sub(r"[\U0001F3FB-\U0001F3FF\uFE0F\u200D\u20E3]", "", text)
    flags = len(re.findall(r"[\U0001F1E6-\U0001F1FF]{2}", s))
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
    now = time.time()
    if now - last_notice.get(chat_id, 0.0) < NOTICE_COOLDOWN:
        return
    last_notice[chat_id] = now
    mention = f'<a href="tg://user?id={uid}">{html_mod.escape(str(name))}</a>'
    text = (f"🚫 <b>GLOBAL MUTE</b>\n"
            f"👤 User: {mention} (<code>{uid}</code>)\n"
            f"🧾 Reason: {html_mod.escape(str(reason))}\n"
            f"🤐 All messages from this user will now be auto-deleted.\n"
            f"💡 Admins can undo: reply <code>/gunmute</code>")
    try:
        await client.send_message(chat_id, text, parse_mode="html", link_preview=False)
    except Exception as e:
        print("[notice-err]", e)

# ========================= BIO / NAME SCANNER (NO CHANGES) =========================
async def fetch_bio(uid):
    try:
        ent = await client.get_entity(uid)
        full = await client(GetFullUserRequest(ent))
        return full.full_user.about or ""
    except Exception as e:
        print(f"[bio-fetch-err {uid}] {type(e).__name__}")
        return None

def profile_text(user, bio):
    uname = getattr(user, "username", None) or ""
    parts = [getattr(user, "first_name", "") or "",
             getattr(user, "last_name", "") or "",
             uname.replace("_", " ").replace("-", " "),
             bio or ""]
    return " ".join(p for p in parts if p)

def bio_is_scam(text):
    if not text:
        return None
    t = norm_text(text)
    t = re.sub(r"[_\-./|\\]+", " ", t)
    t2 = deleet_text(t)
    for word, rx in BIO_BAN_PATTERNS:
        if rx.search(t) or rx.search(t2):
            return f"scam bio/name detected ('{word}')"
    return None

async def scan_bio(user, chat_id, event=None):
    uid = getattr(user, "id", None)
    if uid is None or is_gmuted(uid):
        return
    key = str(uid)
    now = time.time()
    with BIO_LOCK:
        rec = bio_checked.get(key)
        if isinstance(rec, dict):
            last, st = rec.get("t", 0), rec.get("s", "ok")
        elif isinstance(rec, (int, float)):
            last, st = float(rec), "ok"
        else:
            last, st = 0, ""
    if last:
        gap = {"ok": BIO_RECHECK_HOURS * 3600,
               "empty": BIO_EMPTY_RECHECK_MIN * 60,
               "fail": BIO_FAIL_RECHECK_MIN * 60}.get(st, BIO_RECHECK_HOURS * 3600)
        if now - last < gap:
            return
    if key in BIO_INFLIGHT:
        return
    BIO_INFLIGHT.add(key)
    try:
        bio = await fetch_bio(uid)
        st = "ok" if bio and bio.strip() else ("empty" if bio is not None else "fail")
        with BIO_LOCK:
            bio_checked[key] = {"t": now, "s": st}
            BIO_DIRTY.set()
        why = bio_is_scam(profile_text(user, bio))
        print(f"[bio-scan] uid={uid} state={st} bad={why}")
        if why and not is_gmuted(uid):
            add_gmute(uid, why)
            name = getattr(user, "first_name", None) or "user"
            await notify_gmute(chat_id, uid, name, why)
            if event is not None:
                await safe_delete(event)
            await log_action(f"🚫 <b>GMUTE (bio/name)</b> <code>{uid}</code> — {html_mod.escape(why)}")
    except Exception as e:
        print("[bio-scan-err]", e)
    finally:
        BIO_INFLIGHT.discard(key)

# ========================= 🆕 EMOJI WATCH (name/bio Urdu-Arabic check) =========================
def name_has_arabic(user):
    """Naam me Urdu/Arabic script hai ya nahi."""
    name = ((getattr(user, "first_name", "") or "") + " " +
            (getattr(user, "last_name", "") or "")).strip()
    return script_count(name, ARABIC_RANGES) >= NAME_SCRIPT_MIN_CHARS

async def emoji_watch_check(user, chat_id):
    """3+ emoji bhejne par: naam/bio me Urdu/Arabic hai -> permanent delete list."""
    uid = getattr(user, "id", None)
    if uid is None or is_emoji_watched(uid) or is_gmuted(uid):
        return
    if name_has_arabic(user):
        add_emoji_watch(uid, "3+ emoji + Urdu/Arabic name detected")
        print(f"[emoji-watch] uid={uid} -> name has Urdu/Arabic script")
        await log_action(f"👁️ <b>Emoji watch (name)</b> <code>{uid}</code> — Urdu/Arabic name + 3+ emojis")
        return
    key = str(uid)
    if key in EW_INFLIGHT:
        return
    EW_INFLIGHT.add(key)
    try:
        bio = await fetch_bio(uid)
        if bio and script_count(bio, ARABIC_RANGES) >= NAME_SCRIPT_MIN_CHARS:
            add_emoji_watch(uid, "3+ emoji + Urdu/Arabic bio detected")
            print(f"[emoji-watch] uid={uid} -> bio has Urdu/Arabic script")
            await log_action(f"👁️ <b>Emoji watch (bio)</b> <code>{uid}</code> — Urdu/Arabic bio + 3+ emojis")
    except Exception as e:
        print("[emoji-watch-err]", e)
    finally:
        EW_INFLIGHT.discard(key)

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

    gmuted = is_gmuted(uid)
    admin = await is_group_admin(event.chat_id, uid)

    # pehle se gmute -> silent delete
    if gmuted:
        if admin and not DELETE_GMUTED_ADMINS:
            return
        await safe_delete(event)
        return

    # 🆕 emoji-watch list (3+ emoji + Urdu/Arabic naam/bio wale) -> silent delete har message
    if is_emoji_watched(uid):
        await safe_delete(event)
        return

    # bio/name scam scan (sab users, admins bhi)
    client.loop.create_task(scan_bio(sender, event.chat_id, None if admin else event))

    if admin:
        return  # admin immunity

    text = event.raw_text or ""
    if not text.strip():
        return
    t = norm_text(text)
    t2 = deleet_text(t)
    def hit(rx):
        return rx.search(t) or rx.search(t2)

    # 1) instant GMUTE
    for rx, reason in GMUTE_RULES:
        if hit(rx):
            await safe_delete(event)
            if not is_gmuted(uid):
                add_gmute(uid, reason)
            name = getattr(sender, "first_name", None) or "user"
            await notify_gmute(event.chat_id, uid, name, reason)
            await log_action(f"🚫 <b>GMUTE</b> <code>{uid}</code> — {html_mod.escape(reason)}")
            print(f"[gmute] uid={uid} reason={reason}")
            return

    # 2) Urdu / Arabic
    if script_count(t, ARABIC_RANGES) >= ARABIC_MIN_CHARS:
        await safe_delete(event)
        print(f"[delete] urdu/arabic uid={uid}")
        return

    # 3) Tamil script
    if script_count(t, TAMIL_RANGES) >= TAMIL_MIN_CHARS:
        await safe_delete(event)
        print(f"[delete] tamil uid={uid}")
        return

    # 4) Telugu script
    if script_count(t, TELUGU_RANGES) >= TELUGU_MIN_CHARS:
        await safe_delete(event)
        print(f"[delete] telugu uid={uid}")
        return

    # 🆕 5) Tanglish promo phrases (sirf ye — broad roman lists HATA DI)
    if hit(TANGLISH_PROMO_RE):
        await safe_delete(event)
        print(f"[delete] tanglish-promo uid={uid}")
        return

    # 🆕 6) 3+ emojis -> delete + naam/bio check (Urdu/Arabic -> permanent list)
    if emoji_count(text) >= EMOJI_LIMIT:
        await safe_delete(event)
        print(f"[delete] 3+ emojis uid={uid}")
        client.loop.create_task(emoji_watch_check(sender, event.chat_id))
        return

    # 7) f2f
    if hit(F2F_RE):
        await safe_delete(event)
        print(f"[delete] f2f uid={uid}")
        return

    # 8) FAMILY ABUSE COMBO
    if DIRTY_RE.search(t) and FAMILY_RE.search(t):
        await safe_delete(event)
        print(f"[delete] family-abuse uid={uid}")
        return

    # 9) ADULT BAIT
    for rx, reason in BAIT_DELETE_RULES:
        if hit(rx):
            await safe_delete(event)
            print(f"[delete] {reason} uid={uid}")
            return
    if GIRL_BAIT_RE.search(t) and SEXT_CONTEXT_RE.search(t):
        await safe_delete(event)
        print(f"[delete] adult bait (girl/secret chat) uid={uid}")
        return

    # 10) State/City + couple
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

# ========================= /gunmute (emoji-watch bhi clear) =========================
@client.on(events.NewMessage(pattern=r"^/gunmute(?:@\S+)?(?:\s+(.+))?$", incoming=True))
async def on_gunmute(event):
    if event.is_group:
        allowed = await is_group_admin(event.chat_id, event.sender_id)
        if not allowed:
            await event.reply("⛔ Only group admins can use /gunmute.")
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
        await event.reply("ℹ️ Reply to a user's message with <code>/gunmute</code>, "
                          "or use <code>/gunmute &lt;user_id|@username&gt;</code>", parse_mode="html")
        return
    removed_gm = remove_gmute(target_id)
    removed_ew = remove_emoji_watch(target_id)
    name = str(target_id)
    try:
        ent = await client.get_entity(target_id)
        name = getattr(ent, "first_name", None) or name
    except Exception:
        pass
    mention = f'<a href="tg://user?id={target_id}">{html_mod.escape(name)}</a>'
    if removed_gm and removed_ew:
        await event.reply(f"✅ {mention} removed from <b>both</b> the global mute list "
                          f"and the emoji-watch list.", parse_mode="html")
    elif removed_gm:
        await event.reply(f"✅ {mention} removed from the global mute list. "
                          f"Their messages will no longer be deleted.", parse_mode="html")
    elif removed_ew:
        await event.reply(f"✅ {mention} removed from the emoji-watch list. "
                          f"Their messages will no longer be deleted.", parse_mode="html")
    else:
        await event.reply(f"ℹ️ {mention} was not in any list — all clean.", parse_mode="html")

# ========================= DM /start UI (English) =========================
START_TEXT = (
    "🛡️ <b>GROUP PROTECTOR BOT</b> — Features\n\n"
    "🧹 <b>AUTO-DELETE</b>\n"
    "• Urdu / Arabic / Tamil / Telugu messages → deleted instantly\n"
    "• Tanglish promo phrases (<i>mood ah irukkura boys vanga</i>...) → deleted\n"
    "• State/City + <i>couple</i> promos → deleted\n"
    "• <code>f2f</code> messages → deleted\n"
    "• 3+ emojis in one message → deleted\n"
    "  ↳ 🔎 If that user's <b>name or bio has Urdu/Arabic script</b>, they are added to the "
    "<b>emoji-watch list</b> — ALL their messages will keep getting deleted\n"
    "• Family abuse (dirty talk + mother/sister/family names) → deleted\n"
    "• Adult bait (<i>teen boy here, bull here, koi ladki secret chat karegi</i>) → deleted\n\n"
    "🤐 <b>AUTO GLOBAL-MUTE</b>\n"
    "• Scam promos: <i>come boys dm, free show, child porn, paid service, video call service…</i> "
    "→ gmuted with a short English reason\n"
    "• <b>Bio/Name Scanner 🔎</b>: words like <i>free, dm, service, 100%, callgirl, "
    "real meet, provider, demo, come</i> in a user's bio/name → gmuted, all messages auto-deleted "
    "(works with any styled font)\n\n"
    "♻️ All lists are permanent — they survive restarts.\n\n"
    "⚙️ <b>COMMAND</b>\n"
    "• <code>/gunmute</code> — reply to a user's message to remove them from ALL lists (admins only)\n"
    "• <code>/start</code> — this menu (DM only)\n\n"
    "📌 <b>Setup:</b> Make the bot an <b>Admin</b> with <b>Delete Messages</b> permission.\n"
    "💬 Deletes are silent — a short English reason is posted only when someone is gmuted."
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

# ========================= GROUP INTRO (English) =========================
GROUP_INTRO = (
    "🛡️ <b>Group Protector activated!</b>\n"
    "⚠️ Make me an <b>Admin</b> with <b>Delete Messages</b> permission, or I can't delete/gmute.\n"
    "✅ Urdu/Arabic/Tamil/Telugu delete • scam promo auto-gmute • bio/name scanner • "
    "emoji + name/bio check • family-abuse & adult-bait filter\n"
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
        if is_gmuted(uid) or is_emoji_watched(uid):
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
            f"Gmuted: {len(gmute_db)} | Emoji-watch: {len(emoji_watch)} | Bio scanned: {len(bio_checked)}</p>")

@app.route("/health")
def health():
    return jsonify({"ok": True, "gmuted": len(gmute_db), "emoji_watch": len(emoji_watch),
                    "bio_scanned": len(bio_checked),
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
    client.start(bot_token=BOT_TOKEN)
    me = client.loop.run_until_complete(client.get_me())
    ME_ID = me.id
    ME_USERNAME = me.username or ""
    print(f"✅ Bot started as @{ME_USERNAME} (id={ME_ID}) | Flask on port {PORT}")
    client.run_until_disconnected()

if __name__ == "__main__":
    main()
