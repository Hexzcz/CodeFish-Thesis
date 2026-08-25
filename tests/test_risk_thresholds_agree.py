"""The two views must not disagree about what counts as risky.

The engine labels a route Low/Medium/High from its flood exposure
(`domain/routing/scoring/topsis.py`). The resident view decides between a
green reassurance, an amber caution and a red warning from the same numbers
(`frontend/js/simple/plain_language.js`).

They are written in different languages and cannot import each other, so
nothing stops one from being retuned without the other — leaving a route the
engine calls High while the card says it avoids flooding. This test is the
thing that stops it.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOPSIS = ROOT / "backend" / "domain" / "routing" / "scoring" / "topsis.py"
PLAIN_LANGUAGE = ROOT / "frontend" / "js" / "simple" / "plain_language.js"


def _constant(path: pathlib.Path, name: str) -> float:
    match = re.search(rf"^\s*(?:const\s+)?{name}\s*=\s*([0-9.]+)", path.read_text(), re.MULTILINE)
    assert match, f"{name} not found in {path.name} — was it renamed?"
    return float(match.group(1))


def test_low_risk_boundary_matches():
    assert _constant(TOPSIS, "_LOW_RISK_BELOW") == _constant(PLAIN_LANGUAGE, "SOME_RISK_EXPOSURE")


def test_high_risk_boundary_matches():
    assert _constant(TOPSIS, "_MEDIUM_RISK_BELOW") == _constant(PLAIN_LANGUAGE, "HIGH_RISK_EXPOSURE")


def test_pagasa_thresholds_match_the_rainfall_rule():
    """The simulator's mm/hr bands are the same PAGASA numbers the engine uses."""
    rule = ROOT / "backend" / "domain" / "prediction" / "rainfall_scenario.py"
    assert _constant(rule, "HEAVY_RAIN_MM_HR") == 30.0
    assert _constant(rule, "MODERATE_RAIN_MM_HR") == 7.5
