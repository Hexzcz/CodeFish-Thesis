"""English and Filipino must stay in step.

The resident's view exists to be understood. A key added in English and
forgotten in Filipino leaves a Filipino speaker reading one English sentence in
the middle of their own language — and nothing else would notice, because the
lookup falls back to English on purpose so a missing string is legible rather
than a raw key.

The dictionaries live in JavaScript, so this reads them as text. That is
deliberate: the alternative is a build step, and this app does not have one.
"""
import pathlib
import re

import pytest

I18N = pathlib.Path(__file__).resolve().parent.parent / "frontend" / "js" / "i18n.js"


def _table(language: str) -> dict:
    """Pull one language's key/value pairs out of the STRINGS object."""
    source = I18N.read_text()
    start = source.index(f"    {language}: {{")
    depth = 0
    for index in range(start, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                block = source[start:index]
                break

    # key: 'value' or key: "value" — values may contain escaped quotes.
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"^\s{8}(\w+):\s*'((?:[^'\\]|\\.)*)'", block, re.MULTILINE)
    }


ENGLISH = _table("en")
FILIPINO = _table("fil")


def test_both_dictionaries_were_actually_read():
    """Guards the parser itself — an empty table would pass everything below."""
    assert len(ENGLISH) > 40
    assert len(FILIPINO) > 40


def test_every_english_string_has_a_filipino_one():
    missing = sorted(set(ENGLISH) - set(FILIPINO))
    assert not missing, f"no Filipino translation for: {missing}"


def test_no_filipino_string_is_left_over():
    """A stale key is a string nobody shows and nobody maintains."""
    extra = sorted(set(FILIPINO) - set(ENGLISH))
    assert not extra, f"Filipino has keys English does not: {extra}"


@pytest.mark.parametrize("key", sorted(ENGLISH))
def test_placeholders_survive_translation(key):
    """A dropped {count} silently removes the number from the sentence."""
    english = set(re.findall(r"\{(\w+)\}", ENGLISH[key]))
    filipino = set(re.findall(r"\{(\w+)\}", FILIPINO.get(key, "")))
    assert english == filipino, (
        f"'{key}' uses {english or 'no placeholders'} in English "
        f"but {filipino or 'none'} in Filipino"
    )


def test_no_translation_was_left_as_english():
    """Catches a key copied across and never actually translated.

    A handful legitimately match — "Advanced view" is the label of an English
    interface, and it stays English on purpose.
    """
    allowed_to_match = {"advanced_view"}
    identical = [
        key for key, value in ENGLISH.items()
        if key not in allowed_to_match and FILIPINO.get(key) == value
    ]
    assert not identical, f"these are still English in the Filipino table: {identical}"
