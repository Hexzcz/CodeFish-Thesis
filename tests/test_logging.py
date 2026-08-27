"""The app talks through logging, not print.

84 print calls meant no levels, no timestamps, and no way to quiet the
per-request scoring tables on a deployed server — a failure and a progress
message looked exactly alike.
"""
import logging
import pathlib
import subprocess
import sys

import pytest

from backend.core.logging import APP_LOGGER, REPORT_LOGGER, get_logger

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_nothing_in_the_backend_prints_any_more():
    offenders = []
    for path in (ROOT / "backend").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.strip().startswith("print("):
                offenders.append(f"{path.relative_to(ROOT)}:{number}")

    assert not offenders, f"these still print instead of logging: {offenders}"


def test_loggers_sit_under_the_app_namespace():
    """One namespace means one switch to turn the whole app up or down."""
    assert get_logger("backend.adapters.road_network").name.startswith(APP_LOGGER)
    assert get_logger().name == APP_LOGGER


def test_the_scoring_report_has_its_own_logger():
    """It is the one thing worth silencing without going deaf to the rest."""
    report = logging.getLogger(REPORT_LOGGER)
    assert report.name.startswith(APP_LOGGER)
    assert report.name != APP_LOGGER


def _run(code: str, **env_extra) -> str:
    """Run a snippet in a fresh interpreter — levels are read once at setup."""
    import os
    env = {**os.environ, **env_extra}
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                            cwd=ROOT, env=env)
    return result.stdout + result.stderr


SPEAK = (
    "from backend.core.logging import configure_logging, get_logger, REPORT_LOGGER;"
    "import logging;"
    "configure_logging();"
    "get_logger('backend.core.startup').info('APP-INFO');"
    "get_logger('backend.core.startup').warning('APP-WARNING');"
    "logging.getLogger(REPORT_LOGGER).info('REPORT-TABLE')"
)


def test_by_default_you_hear_everything():
    output = _run(SPEAK, LOG_LEVEL="INFO", REPORT_LEVEL="INFO")
    assert "APP-INFO" in output
    assert "REPORT-TABLE" in output


def test_the_report_can_be_silenced_on_its_own():
    """The reason the report has a separate logger at all."""
    output = _run(SPEAK, LOG_LEVEL="INFO", REPORT_LEVEL="WARNING")
    assert "APP-INFO" in output, "silencing the report should not silence the app"
    assert "REPORT-TABLE" not in output


def test_turning_the_app_down_keeps_the_problems():
    output = _run(SPEAK, LOG_LEVEL="WARNING", REPORT_LEVEL="WARNING")
    assert "APP-INFO" not in output
    assert "APP-WARNING" in output, "warnings must survive a quieter level"


def test_failures_are_logged_above_info():
    """A fallback to bundled data is a warning; nobody should have to grep."""
    source = (ROOT / "backend" / "adapters" / "road_network.py").read_text()
    assert "log.warning" in source or "log.error" in source
