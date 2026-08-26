"""Conditional responses for the large payloads the map needs.

`/roads` is 1.7 MB of GeoJSON and every page load asked for all of it again.
It changes when the road network is re-exported — roughly once a semester — so
almost every one of those transfers was waste, paid for by whoever is on
mobile data during a flood.

Two things happen here. The body is serialised once per process rather than
per request, and it carries an ETag so a browser that already has it gets a
304 and transfers nothing.
"""
import hashlib
import json
from typing import Any, Dict, Tuple

from fastapi import Request, Response

# A day. The data is static for the life of the process, and the ETag catches
# the case where it is not.
DEFAULT_MAX_AGE = 86400

# name -> (etag, body, the object it was built from)
_serialised: Dict[str, Tuple[str, bytes, Any]] = {}


def json_response(request: Request, name: str, payload: Any, max_age: int = DEFAULT_MAX_AGE) -> Response:
    """Serve `payload` as JSON with an ETag, honouring If-None-Match.

    `name` identifies the payload across requests. The cached body is reused
    only while it was built from the very same object, so a restart or a
    reload of the data produces a new ETag rather than a stale hit.
    """
    etag, body = _body_for(name, payload)

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=_headers(etag, max_age))

    return Response(
        content=body,
        media_type="application/json",
        headers=_headers(etag, max_age),
    )


def _body_for(name: str, payload: Any) -> Tuple[str, bytes]:
    cached = _serialised.get(name)
    if cached is not None and cached[2] is payload:
        return cached[0], cached[1]

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    etag = '"' + hashlib.sha256(body).hexdigest()[:32] + '"'
    _serialised[name] = (etag, body, payload)
    return etag, body


def _headers(etag: str, max_age: int) -> Dict[str, str]:
    return {
        "ETag": etag,
        # `must-revalidate` keeps a browser from serving a stale road network
        # once the age is up: it asks, and usually gets a 304 back.
        "Cache-Control": f"public, max-age={max_age}, must-revalidate",
    }
