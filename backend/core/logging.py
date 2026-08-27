"""Logging setup.

The app used to say everything with `print`: no levels, no timestamps, and no
way to quiet the per-request scoring tables once it was deployed. Worse, a
failure and a progress message looked identical in the output.

Two loggers matter:

  codefish          the app — startup, adapters, failures
  codefish.report   the scoring breakdown printed for each route request

The report is separated because it is the one thing you want to silence in
production without going deaf to everything else:

    LOG_LEVEL=INFO REPORT_LEVEL=WARNING   # keep the app talking, drop tables
"""
import logging
import os
import sys

APP_LOGGER = "codefish"
REPORT_LOGGER = "codefish.report"

_configured = False


def configure_logging() -> None:
    """Set up handlers once. Safe to call more than once."""
    global _configured
    if _configured:
        return
    _configured = True

    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    report_level = os.environ.get("REPORT_LEVEL", level).upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    app = logging.getLogger(APP_LOGGER)
    app.setLevel(getattr(logging, level, logging.INFO))
    app.handlers = [handler]
    app.propagate = False

    # The report is a table meant to be read as written, so it gets a handler
    # with no prefix of its own.
    plain = logging.StreamHandler(sys.stdout)
    plain.setFormatter(logging.Formatter("%(message)s"))

    report = logging.getLogger(REPORT_LOGGER)
    report.setLevel(getattr(logging, report_level, logging.INFO))
    report.handlers = [plain]
    report.propagate = False


def get_logger(name: str = "") -> logging.Logger:
    """A logger under the app's namespace. `get_logger(__name__)` is fine."""
    configure_logging()
    if not name or name == APP_LOGGER:
        return logging.getLogger(APP_LOGGER)
    short = name.replace("backend.", "").replace(".", "/")
    return logging.getLogger(f"{APP_LOGGER}.{short}")
