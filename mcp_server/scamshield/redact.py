"""Strip personal details from email text before it reaches the model.

Best-effort and regex-based, which is enough for the MVP: email addresses, URLs,
phone numbers, long digit runs (account / card numbers), the name after a
greeting ("Dear Margaret Smith"), and any names we already know for this user.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_PHONE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)")
# 6+ digits, optionally broken up by spaces or dashes (account, card, routing numbers).
# Commas and dots are not separators, so money amounts like "$10,000.00" survive.
_DIGIT_RUN = re.compile(r"(?<![\w$])\d(?:[ -]?\d){5,}(?!\w)")
_GREETING_NAME = re.compile(
    r"\b(Dear|Hi|Hello|Hey|Attn:?|Attention:?)(\s+)"
    r"(?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?"
    r"[A-Z][a-zA-Z'’-]+(?:\s+[A-Z][a-zA-Z'’-]+){0,2}"
)


def redact(text: str, known_names: Iterable[str] = ()) -> str:
    if not text:
        return text
    out = _EMAIL.sub("[email]", text)
    out = _URL.sub("[link]", out)
    out = _PHONE.sub("[phone]", out)
    out = _DIGIT_RUN.sub("[number]", out)
    out = _GREETING_NAME.sub(lambda m: f"{m.group(1)}{m.group(2)}[name]", out)
    for name in known_names:
        for part in {name.strip(), *name.split()}:
            if len(part) >= 2:
                out = re.sub(rf"\b{re.escape(part)}\b", "[name]", out, flags=re.IGNORECASE)
    return out
