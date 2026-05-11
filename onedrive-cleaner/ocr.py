import pytesseract
from PIL import Image
import io
import re

CHAT_KEYWORDS = [
    "delivered",
    "read",
    "typing",
    "imessage",
    "whatsapp",
    "messenger",
    "signal",
    "snapchat",
    "telegram",
    "sent",
    "seen",
    "online",
    "active now",
    "text message",
    "sms",
    "mms",
    "chat",
    "group",
    "reply",
    "forwarded",
]


def extract_text(image_bytes: bytes) -> str:
    try:
        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return text.strip()
    except Exception as e:
        return ""


def score_chat_screenshot(text: str) -> int:
    if not text:
        return 0

    text_lower = text.lower()
    score = 0

    for keyword in CHAT_KEYWORDS:
        if keyword.lower() in text_lower:
            score += 10

    time_patterns = [
        r"\d{1,2}:\d{2}\s*(AM|PM)",
        r"\d{1,2}:\d{2}",
    ]
    for pattern in time_patterns:
        if re.search(pattern, text):
            score += 10

    date_patterns = [
        r"\w+day",  # Monday, Tuesday, etc.
        r"\d{1,2}/\d{1,2}/\d{2,4}",
    ]
    for pattern in date_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += 5

    lines = text.strip().split("\n")
    if len(lines) >= 3:
        score += 5

    avg_line_len = sum(len(l) for l in lines) / max(len(lines), 1)
    if 10 <= avg_line_len <= 80:
        score += 5

    return min(score, 50)


def run_ocr(image_bytes: bytes) -> tuple[str, int]:
    text = extract_text(image_bytes)
    score = score_chat_screenshot(text)
    return text, score
