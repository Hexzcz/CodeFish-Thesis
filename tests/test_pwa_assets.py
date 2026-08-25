"""The installable app must not promise files that are not there.

The service worker precaches a list of URLs by hand. Rename a stylesheet and
the list still looks fine — the install step skips what it cannot fetch, and
the app silently loses its offline copy of that file. Nothing fails until
someone is standing in the rain with no signal.

These tests read the list and check it against the tree.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
SERVICE_WORKER = FRONTEND / "sw.js"
MANIFEST = FRONTEND / "manifest.webmanifest"
INDEX = FRONTEND / "index.html"


def precached_paths() -> list:
    text = SERVICE_WORKER.read_text()
    block = text[text.index("const SHELL = ["):text.index("];", text.index("const SHELL = ["))]
    return re.findall(r"'([^']+)'", block)


def test_every_precached_file_exists():
    missing = []
    for path in precached_paths():
        if path == '/':
            continue  # served by the StaticFiles html=True mount
        if not (FRONTEND / path.lstrip('/')).exists():
            missing.append(path)
    assert not missing, f"service worker precaches files that do not exist: {missing}"


def test_scripts_the_page_loads_are_precached():
    """Every app script in index.html should survive going offline."""
    html = INDEX.read_text()
    scripts = re.findall(r'<script src="(js/[^"?]+)', html)
    precached = {p.lstrip('/') for p in precached_paths()}
    missing = [s for s in scripts if s not in precached]
    assert not missing, f"scripts loaded by index.html but not precached: {missing}"


def test_stylesheets_the_page_loads_are_precached():
    html = INDEX.read_text()
    sheets = re.findall(r'<link rel="stylesheet" href="(css/[^"?]+)', html)
    precached = {p.lstrip('/') for p in precached_paths()}
    missing = [s for s in sheets if s not in precached]
    assert not missing, f"stylesheets loaded by index.html but not precached: {missing}"


def test_manifest_is_valid_and_its_icons_exist():
    manifest = json.loads(MANIFEST.read_text())

    for field in ("name", "short_name", "start_url", "display", "icons"):
        assert manifest.get(field), f"manifest is missing {field}"

    sizes = set()
    for icon in manifest["icons"]:
        assert (FRONTEND / icon["src"]).exists(), f"missing icon {icon['src']}"
        sizes.add(icon["sizes"])

    # Chrome wants both to offer installation; Android needs the maskable one
    # or it puts a white box behind the icon.
    assert {"192x192", "512x512"} <= sizes
    assert any(icon.get("purpose") == "maskable" for icon in manifest["icons"])


def test_page_links_the_manifest_and_a_theme_colour():
    html = INDEX.read_text()
    assert 'rel="manifest"' in html
    assert 'name="theme-color"' in html
    assert 'rel="apple-touch-icon"' in html


def test_leaflet_is_local_not_a_cdn():
    """A CDN dependency is a dependency the app cannot install with."""
    html = INDEX.read_text()
    assert 'unpkg.com' not in html, "index.html still loads Leaflet from a CDN"
    assert (FRONTEND / "vendor" / "leaflet" / "leaflet.js").exists()
