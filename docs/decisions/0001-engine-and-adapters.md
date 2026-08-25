# ADR-0001: An engine that imports no framework

**Status:** accepted · 2026-08-25

## Context

The backend had grown into `backend/graph/`, `backend/routing/`,
`backend/prediction/`, `backend/tiles/` and `backend/api/`, split by *what kind
of thing* a module was rather than by what depends on what. The result:

- `api/routes.py` held 400 lines that were mostly routing logic, including two
  copies of a distance-only Dijkstra, so the routing could not be exercised
  without FastAPI.
- `graph/builder.py` defined the `Graph` data structure *and* queried Supabase,
  so using the graph meant importing sqlalchemy.
- `routing/scorer.py` computed TOPSIS rankings *and* printed 180 lines of
  terminal tables, so scoring a route had a side effect.

Testing any rule meant booting the application.

## Decision

Three layers, and dependencies point inward only:

```
   api  ─▶  adapters  ─▶  domain
```

- `domain/` — the rules. May import numpy and pandas. May not import any web,
  database, raster, rendering, network or model-loading library, and may not
  import `adapters` or `api`.
- `adapters/` — everything that talks to the outside: Supabase, GeoJSON files,
  rasters, the JAXA FTP server, Nominatim, the terminal.
- `api/` — HTTP. Parse, call a service, shape the answer, map errors to codes.

`tests/test_dependency_rule.py` walks the AST of every file in `domain/` and
fails if the rule is broken.

## Consequences

- Routing, scoring and snapping are testable in milliseconds with a four-node
  graph and no data files.
- Adding a second interface — a CLI for batch runs, a notebook for the thesis —
  means calling `plan_evacuation_routes`, not copying the endpoint.
- The cost is indirection: reading one request end to end now crosses three
  files instead of one. The 400-line handler was worse.
