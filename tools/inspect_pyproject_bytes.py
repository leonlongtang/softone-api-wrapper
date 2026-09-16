from __future__ import annotations

from pathlib import Path


def main() -> None:
    p = Path("pyproject.toml")
    b = p.read_bytes()
    print("first_20_bytes:", b[:20])
    print("first_10_ints:", list(b[:10]))


if __name__ == "__main__":
    main()

