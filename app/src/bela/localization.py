"""Optional Croatian messages; engine and persistence use English by default."""

import json
from pathlib import Path
import re

CROATIAN = json.loads((Path(__file__).with_name("web") / "hr.json").read_text(encoding="utf-8"))
_PATTERN = re.compile("|".join(
    r"\b" + re.escape(key) + r"\b" if key.isalpha() else re.escape(key)
    for key in sorted(CROATIAN, key=len, reverse=True)))


def translate(message, language="en"):
    if language.split(",", 1)[0].split("-", 1)[0].lower() != "hr":
        return message
    return _PATTERN.sub(lambda match: CROATIAN[match[0]], message)
