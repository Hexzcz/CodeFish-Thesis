"""The engine depends on nothing.

`backend/domain/` holds the rules: what a route costs, which one wins, where a
point attaches to the network. None of that needs a web framework, a database,
a raster library or a socket — and if it ever imports one, the rules can no
longer be tested or reused without standing up the whole app.

This test is the enforcement. It is the reason the layout survives contact
with a deadline.
"""
import ast
import pathlib

import pytest

DOMAIN = pathlib.Path(__file__).resolve().parent.parent / "backend" / "domain"

# Frameworks and I/O the engine may never reach for. numpy and pandas are
# allowed: they compute, they do not talk to anything.
FORBIDDEN = {
    "fastapi", "starlette", "pydantic",       # the web edge
    "sqlalchemy", "psycopg2",                 # the database edge
    "rasterio", "rio_tiler", "geopandas",     # the raster/geo edge
    "matplotlib", "PIL",                      # the rendering edge
    "httpx", "ftplib", "requests",            # the network edge
    "joblib", "xgboost",                      # the model store edge
}


def domain_modules():
    return sorted(DOMAIN.rglob("*.py"))


def imported_roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text())
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


@pytest.mark.parametrize("module", domain_modules(), ids=lambda p: p.name)
def test_domain_imports_no_framework(module):
    offenders = imported_roots(module) & FORBIDDEN
    assert not offenders, (
        f"{module.relative_to(DOMAIN.parent.parent)} imports {sorted(offenders)}. "
        "Move the part that needs it into backend/adapters/ and let the engine "
        "take the result as an argument."
    )


@pytest.mark.parametrize("module", domain_modules(), ids=lambda p: p.name)
def test_domain_does_not_import_adapters_or_api(module):
    roots = {
        node.module for node in ast.walk(ast.parse(module.read_text()))
        if isinstance(node, ast.ImportFrom) and node.module
    }
    bad = {m for m in roots if m.startswith(("backend.adapters", "backend.api"))}
    assert not bad, f"{module.name} imports outward: {sorted(bad)}"
