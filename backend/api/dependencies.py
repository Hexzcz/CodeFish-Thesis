"""Shared FastAPI dependencies.

`get_app_state` was copy-pasted into four routers. It lives here now.
"""
from fastapi import Request


def get_app_state(request: Request) -> dict:
    """The data assembled once at startup: graph, models, centers, layers."""
    return request.app.state.data
