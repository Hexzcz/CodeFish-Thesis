# ADR-0006: Installable, and honest about being offline

**Status:** accepted · 2026-08-26

## Context

The likeliest moment someone needs this app is the worst moment to be loading
a website: a phone, a browser tab nobody bookmarked, and a network that is
degrading along with the weather. The interface was also desktop-first by
decision ([ADR-0005](0005-two-views.md)), which left the resident's view — the
one a stranger meets — unusable on the device most residents own.

## Decision

**A phone layout for the resident's view.** Below 768px the answer card becomes
a bottom sheet: the map keeps the top of the screen, the answer sits under a
thumb, tap targets are at least 48px, and the map fit pads whichever edge the
panel is actually on. The console gets a small-screen notice that offers the
resident's view instead, and stacks into one column for anyone who dismisses
it. Layer controls and a decision matrix do not belong on 375px, and saying so
beats shipping a broken console.

**A progressive web app.** A manifest, icons, and a service worker, so it can
be installed to a home screen and opened like an app.

**Leaflet is vendored**, not loaded from unpkg. An installable app that needs a
CDN to draw a map is not installable.

## What offline actually means here

Routing is a `POST` to the server. No cache can fake it, and pretending
otherwise would be the worst kind of failure — a confident wrong answer during
a flood. So the service worker never touches `/route`. What it does buy:

- the app opens instantly, and opens at all, with no signal
- the district boundary, road network and evacuation centers are already there
- basemap tiles already looked at still draw (a capped 300-tile cache)
- **the last route stays readable.** The page keeps its most recent answer in
  `localStorage` for twelve hours, so someone who asked before losing signal
  can still read where they were told to go — always labelled with its age and
  a warning that conditions may have changed.

A banner states plainly when the app is offline, rather than letting the
"find my route" button fail silently.

## Consequences

- The precache list is maintained by hand and will rot the first time a file
  is renamed. `tests/test_pwa_assets.py` fails when it does — it caught the
  console's eight stylesheets missing from the list on the first run.
- App JS and CSS are served network-first, not cache-first. They are requested
  with a `?v=` cache-buster the precache does not carry, and matching loosely
  enough to find them would also match a *stale* version after a change. The
  cache is the offline copy, not the fast path.
- **Service workers need HTTPS** (or localhost). Served over plain HTTP from
  another machine, registration silently does not happen and this is a normal
  website — no install, no offline. Deploying behind TLS is what turns the
  feature on.
- Showing an old route is a real risk, accepted deliberately: it is dated,
  captioned, and offered only when a fresh one cannot be fetched. The
  alternative — a blank screen for someone in a flood — is worse.
