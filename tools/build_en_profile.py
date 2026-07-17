#!/usr/bin/env python3
"""Generate the English documentation-link profile from the canonical XML."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "ACUSTEME_profile.xml"
OUTPUT = ROOT / "ACUSTEME_profile_EN.xml"
ITALIAN_WIKI_PREFIX = "https://wiki.acusteme.org/it/"
ENGLISH_WIKI_PREFIX = "https://wiki.acusteme.org/en/"


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    if ITALIAN_WIKI_PREFIX not in source:
        raise SystemExit(f"No Italian documentation URLs found in {SOURCE}")
    generated = source.replace(ITALIAN_WIKI_PREFIX, ENGLISH_WIKI_PREFIX)
    OUTPUT.write_text(generated, encoding="utf-8")
    print(f"Generated {OUTPUT} from {SOURCE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
