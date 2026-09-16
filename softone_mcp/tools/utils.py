import re

def slug(s: str) -> str:
    s = s.strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "X"


def deterministic_suffix(s: str) -> str:
    total = sum(ord(c) for c in s)
    return f"{total % 10000:04d}"
