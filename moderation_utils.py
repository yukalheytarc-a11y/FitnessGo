import re

# =================================================
# 1️⃣ ROOT PROFANITY WORDS (BASE ONLY)
#    👉 DO NOT ADD VARIANTS HERE
# =================================================
ROOT_PROFANITY = [

    # =================================================
    # FILIPINO / TAGALOG (CORE & COMMON)
    # =================================================
    "tangina",
    "puta",
    "gago",
    "tanga",
    "bobo",
    "ulol",
    "tarantado",
    "inutil",
    "siraulo",
    "hayop",
    "bwisit",
    "leche",
    "lintik",
    "punyeta",
    "demonyo",
    "walanghiya",
    "pokpok",
    "animal",
    "yawa",
    "pakyu",

    # =================================================
    # TAGLISH / FILIPINO-STYLE PHONETIC
    # =================================================
    "fakyu",        # fuck you
    "pakyu",
    "fakyou",
    "shuta",        # puta / shit hybrid
    "sheyt",
    "gagi",
    "ulul",
    "bubu",
    "engk",
    "engot",
    "bobita",
    "bobong",
    "tangina mo",
    "gago ka",

    # =================================================
    # ENGLISH – CORE PROFANITY
    # =================================================
    "fuck",
    "fucker",
    "motherfucker",
    "shit",
    "bullshit",
    "bitch",
    "asshole",
    "dick",
    "cock",
    "pussy",
    "cunt",
    "whore",
    "slut",
    "bastard",

    # =================================================
    # ENGLISH – INSULTS / HARASSMENT ROOTS
    # =================================================
    "idiot",
    "moron",
    "retard",
    "stupid",
    "dumb",
    "loser",
    "worthless",
    "useless",
    "trash",
    "garbage",
    "pathetic",

    # =================================================
    # VIOLENCE / EXTREME HARASSMENT (OPTIONAL BUT COMMON)
    # =================================================
    "kill",
    "die",
    "suicide",
]

# =================================================
# 2️⃣ HARASSMENT PHRASES (DIRECT ATTACKS)
# =================================================
HARASSMENT_PHRASES = [

    # =========================
    # FILIPINO
    # =========================
    "bobo ka",
    "tanga ka",
    "gago ka",
    "ulol ka",
    "wala kang kwenta",
    "walang silbi",
    "ang pangit mo",
    "mamatay ka",
    "bwisit ka",

    # =========================
    # TAGLISH
    # =========================
    "bobo mo bro",
    "tanga mo pre",
    "gago ka dude",
    "fuck you pre",

    # =========================
    # ENGLISH
    # =========================
    "you are stupid",
    "you are useless",
    "you are worthless",
    "everyone hates you",
    "nobody wants you",
    "go die",
]

# =================================================
# 3️⃣ TEXT NORMALIZATION
# =================================================
CHAR_SUBS = {
    '0': 'o',
    '1': 'i',
    '3': 'e',
    '4': 'a',
    '5': 's',
    '7': 't',
    '@': 'a',
    '!': 'i',
    '$': 's',
}

def normalize_text(text: str) -> str:
    text = text.lower()

    # replace character obfuscations
    for k, v in CHAR_SUBS.items():
        text = text.replace(k, v)

    # keep letters, numbers, symbols, spaces
    text = re.sub(r'[^a-z0-9\s\*\+\!\@\#\$\_\-]', ' ', text)

    # collapse repeated letters (puuuuta → puta)
    text = re.sub(r'(.)\1{2,}', r'\1', text)

    # normalize spaces
    text = re.sub(r'\s+', ' ', text).strip()

    return f" {text} "

# =================================================
# 4️⃣ AUTO-GENERATE REGEX FROM ROOT WORDS
#    👉 THIS IS THE MAGIC
# =================================================
def build_root_patterns(words):
    patterns = []

    for word in words:
        # normal pattern
        pattern = ""
        for ch in word:
            pattern += ch + r"[\W_]*"
        patterns.append(pattern)

        # reversed pattern
        reversed_word = word[::-1]
        rev_pattern = ""
        for ch in reversed_word:
            rev_pattern += ch + r"[\W_]*"
        patterns.append(rev_pattern)

    return patterns

OBFUSCATED_PATTERNS = build_root_patterns(ROOT_PROFANITY)

# =================================================
# 5️⃣ PROFANITY CHECK (SPELLING-PROOF)
# =================================================
def has_profanity(text: str) -> bool:
    if not text:
        return False

    clean = normalize_text(text)

    for pattern in OBFUSCATED_PATTERNS:
        if re.search(pattern, clean):
            return True

    return False

# =================================================
# 6️⃣ HARASSMENT CHECK
# =================================================
def has_harassment(text: str) -> bool:
    if not text:
        return False

    clean = normalize_text(text)

    for phrase in HARASSMENT_PHRASES:
        if phrase in clean:
            return True

    return False

# =================================================
# 7️⃣ FINAL DECISION FUNCTION
# =================================================
def is_offensive(text: str) -> bool:
    """
    FINAL RULE:
    - Any profanity (even obfuscated)
    - Any direct harassment
    """
    return has_profanity(text) or has_harassment(text)