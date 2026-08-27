"""One caller must not be able to starve everyone else of routing.

/route runs Dijkstra, Yen's k-shortest-paths and XGBoost inference across
3,137 edges. Address search has been rate limited since it was written; the
expensive endpoint was not, and during a flood it is the one that has to stay
answering.
"""
import time

import pytest
from fastapi.testclient import TestClient

from backend.api import routes as routes_api
from backend.core.rate_limit import RateLimiter
from backend.main import app

ORIGIN = {"origin_lat": 14.6357, "origin_lon": 121.0219, "scenario": "25yr"}


# ── The limiter itself ──────────────────────────────────────────────────────

def test_it_allows_the_first_n_then_refuses():
    limiter = RateLimiter(max_requests=3, window_seconds=60)

    assert [limiter.allows("caller") for _ in range(3)] == [True, True, True]
    assert limiter.allows("caller") is False


def test_callers_do_not_share_an_allowance():
    """One noisy client must not lock out everybody behind the same server."""
    limiter = RateLimiter(max_requests=1, window_seconds=60)

    assert limiter.allows("first") is True
    assert limiter.allows("first") is False
    assert limiter.allows("second") is True


def test_the_window_moves():
    limiter = RateLimiter(max_requests=2, window_seconds=0.3)

    assert limiter.allows("caller") and limiter.allows("caller")
    assert limiter.allows("caller") is False

    time.sleep(0.35)
    assert limiter.allows("caller") is True, "the allowance never came back"


def test_retry_after_is_a_usable_number():
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    limiter.allows("caller")
    limiter.allows("caller")

    retry = limiter.retry_after("caller")
    assert 1 <= retry <= 61, "Retry-After should be within the window"


def test_a_caller_under_the_limit_is_told_to_come_straight_back():
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    limiter.allows("caller")
    assert limiter.retry_after("caller") == 1


# ── The endpoint ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as started:
        yield started


@pytest.fixture(autouse=True)
def forget_this_test_client():
    """Every test starts with a full allowance, and leaves one behind."""
    routes_api._limiter.forget("testclient")
    yield
    routes_api._limiter.forget("testclient")


def test_routing_answers_normally_under_the_limit(client):
    assert client.post("/route", json=ORIGIN).status_code == 200


def test_too_many_requests_are_refused_with_a_way_back(client):
    limit = routes_api._limiter.max_requests
    for _ in range(limit):
        client.post("/route", json=ORIGIN)

    refused = client.post("/route", json=ORIGIN)

    assert refused.status_code == 429
    assert "Retry-After" in refused.headers
    assert int(refused.headers["Retry-After"]) >= 1
    # The message has to tell a person what to do, not just that they failed.
    assert "try again" in refused.json()["detail"].lower()


def test_the_limit_is_generous_enough_for_a_person(client):
    """Someone comparing routes should never meet this."""
    assert routes_api._limiter.max_requests >= 20
