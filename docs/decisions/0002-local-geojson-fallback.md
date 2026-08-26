# ADR-0002: The app runs with nothing plugged in

**Status:** accepted · 2026-08-25

## Context

The road network, the evacuation centers and their map layers were read
exclusively from Supabase, with the connection string — password included —
hardcoded as a fallback default. When that project became unreachable, the app still started — and
served an empty graph, no destinations, and a map with no roads. Nothing said
anything was wrong until a route request returned nothing.

For a thesis this is fatal in a specific way: the demonstration happens on
someone else's schedule, in a room whose wifi you do not control.

## Decision

Every remote source has a bundled fallback in `backend/data/geojson/`, and each
loader falls back on its own:

- an unreachable database is logged and the file is read instead;
- a query that returns nothing is treated the same way, because an empty result
  and a failed connection are indistinguishable to a user;
- `USE_LOCAL_DATA=1` skips the database entirely, which also skips ~20 seconds
  of connection timeouts at startup.

Amended 2026-08-26: `DATABASE_URL` now has no default at all. Unset, the app
reads the bundled files — so the offline path is what a fresh clone gets,
rather than something you have to know to ask for. The credential that used to
sit in `database.py` is gone from the source; see
`tests/test_no_committed_secrets.py`.

## Consequences

- The app starts and routes with no network at all. Only the Esri basemap tiles
  and the JAXA rainfall fetch still need the internet, and neither blocks
  routing.
- The bundled files can go stale against the database. They are the same
  exports the upload script pushes, so the fix is to re-export, and
  `tests/test_offline_data.py` checks they are structurally usable.
- Silence is the risk: an app that quietly runs on fallback data looks
  identical to one that does not. The startup log says which source won.
