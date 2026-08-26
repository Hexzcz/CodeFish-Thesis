"""The big payloads are sent once, not on every page load.

/roads is 1.7 MB of GeoJSON that changes when the road network is re-exported
— about once a semester — and it was re-serialised and re-sent every time
anyone opened the app. On mobile data during a flood that is the slowest thing
between a resident and their route.
"""
import pytest
from fastapi.testclient import TestClient

from backend.api import caching
from backend.main import app


@pytest.fixture(scope="module")
def client():
    # These endpoints read from app.state, so the lifespan has to run — which
    # samples rasters for every edge. Once per module, not once per test.
    with TestClient(app) as started:
        yield started


@pytest.mark.parametrize("path,name", [
    ("/roads", "roads"),
    ("/boundary", "boundary"),
    ("/evacuation-centers", "evacuation centers"),
])
def test_large_payloads_are_cacheable(client, path, name):
    response = client.get(path)
    assert response.status_code == 200
    assert response.headers.get("etag"), f"{name} has no ETag"
    assert "max-age" in response.headers.get("cache-control", ""), f"{name} is not cacheable"


def test_a_browser_that_already_has_it_gets_a_304(client):
    first = client.get("/roads")
    again = client.get("/roads", headers={"If-None-Match": first.headers["etag"]})

    assert again.status_code == 304
    assert not again.content, "a 304 should carry no body"


def test_a_stale_etag_gets_the_data(client):
    response = client.get("/roads", headers={"If-None-Match": '"not-the-current-one"'})
    assert response.status_code == 200
    assert response.content


def test_the_body_is_serialised_once_not_per_request(client):
    """The saving is not only bandwidth: 1.7 MB of JSON was rebuilt per call."""
    client.get("/roads")
    _, first_body, _ = caching._serialised["roads"]

    client.get("/roads")
    _, second_body, _ = caching._serialised["roads"]

    assert first_body is second_body, "the payload was re-serialised"


def test_reloaded_data_gets_a_new_etag(client):
    """A cached body must never outlive the object it was built from."""
    original = app.state.data["boundary_geojson"]
    before = client.get("/boundary").headers["etag"]

    try:
        # Stand in for a restart that produced different data.
        app.state.data["boundary_geojson"] = {"type": "FeatureCollection", "features": []}
        after = client.get("/boundary").headers["etag"]
    finally:
        # The client is shared across this module; put it back.
        app.state.data["boundary_geojson"] = original

    assert before != after


def test_map_tiles_are_cacheable_too(client):
    """They were explicitly no-store, and the frontend added a cache-buster on
    top, so every pan re-rendered pictures that had not changed."""
    response = client.get("/tiles/terrain-rgb/14/13699/7518.png")
    assert response.status_code == 200
    assert "max-age" in response.headers.get("cache-control", "")
    assert "no-store" not in response.headers.get("cache-control", "")
