"""The navigation endpoint: thin, and refuses what it cannot answer."""
import pytest
from fastapi.testclient import TestClient

from backend.main import app

ROUTE = [[121.0200, 14.6200], [121.0209, 14.6200], [121.0209, 14.6218]]


@pytest.fixture(scope="module")
def client():
    # No lifespan: these endpoints read nothing from app state, and booting the
    # graph and the models for a geometry check would be a slow lie about what
    # this test covers.
    return TestClient(app)


def test_progress_reports_position_along_the_route(client):
    res = client.post("/navigation/progress",
                      json={"lat": 14.6200, "lon": 121.0200, "route": ROUTE})
    assert res.status_code == 200

    body = res.json()
    assert body["off_route"] is False
    assert body["arrived"] is False
    assert body["remaining_m"] > 0
    assert body["off_route_threshold_m"] > 0


def test_progress_flags_a_position_off_the_route(client):
    res = client.post("/navigation/progress",
                      json={"lat": 14.6260, "lon": 121.0200, "route": ROUTE})
    assert res.status_code == 200
    assert res.json()["off_route"] is True


def test_a_route_with_one_point_is_rejected(client):
    res = client.post("/navigation/progress",
                      json={"lat": 14.62, "lon": 121.02, "route": [[121.02, 14.62]]})
    assert res.status_code == 400


def test_coordinates_outside_the_world_are_rejected(client):
    res = client.post("/navigation/progress",
                      json={"lat": 99.0, "lon": 121.02, "route": ROUTE})
    assert res.status_code == 400


def test_an_absurdly_long_route_is_refused_rather_than_chewed_on(client):
    huge = [[121.0 + i * 1e-6, 14.6] for i in range(5001)]
    res = client.post("/navigation/progress",
                      json={"lat": 14.6, "lon": 121.0, "route": huge})
    assert res.status_code == 413


def test_navigation_does_not_reach_into_routing(client):
    """Rerouting is POST /route's job; this endpoint must not grow its own."""
    # Read the published schema rather than app.routes: this FastAPI version
    # wraps included routers, so the child paths are not on app.routes at all.
    paths = app.openapi()["paths"]
    navigation_paths = sorted(p for p in paths if p.startswith("/navigation"))
    assert navigation_paths == ["/navigation/progress"]
