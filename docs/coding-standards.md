# Coding standards

Conventions this project follows. They complement — not replace — the rules in
[`architecture.md`](architecture.md).

## File size & modularity

- **Aim to keep source files under ~300 lines.**
- Split by **single responsibility**, not merely by line count. `scorer.py` was
  split because measuring a route, ranking routes against each other, and
  printing a table to a terminal are three jobs — not because it was long.
- **No "god files"** and no misc/util dumps. Every file has a nameable job.
- If a file deliberately exceeds ~300 lines, say why in the file.

## General

- **SOLID / DRY / KISS**; small, single-purpose functions.
- **Say it once.** The distance-only Dijkstra existed twice in `routes.py`,
  once returning a number and once returning a path, and the two had already
  started to drift. There is one copy now, in `domain/routing/distance.py`.
- **Validate untrusted input at the boundary.** Nominatim's results are
  untrusted input: every hit is re-checked against the district boundary in the
  handler before the browser sees it, never deeper in.
- **Errors are explicit and typed.** `RoutingError`, `NoRouteFound`,
  `RainfallUnavailable`, `GeocodingError`. Fail loudly rather than compute
  something silently wrong — a rainfall fetch that fails returns 502, not
  0.00 mm/hr, because "no rain" is a number a person will act on.
- **Say what the code cannot.** Comments explain *why*, especially where the
  obvious approach was wrong: why the graph is cloned per request, why
  predicted scenarios are tracked in a set rather than inferred from edges.
- **Remove dead code as you go.** The 74 KB `main.py` monolith at the repo root
  was superseded months before it was deleted, and every reader had to work
  out which of the two entry points was live.

## Properties of the product, not preferences

1. A pin that is not near a road is refused, never quietly moved somewhere else.
2. Flood risk outranks distance. If that ever stops being true, the weights in
   `DEFAULT_WEIGHTS` changed, and that is a thesis decision, not a tuning knob.
3. The app runs with no database and no internet.
4. Every number shown to a user comes from the engine, not from the view.

Each has a test. Changing one means changing the test deliberately.

## Accessibility

This is a public emergency tool, so these are requirements, not preferences:

- **Every control has a name a screen reader can read.** Icon-only buttons and
  map markers carry `aria-label` or `title`; Leaflet gives markers
  `role="button"` and nothing to name them with.
- **Anything the app tells you about your route is announced.** The verdict,
  the navigation status and errors are `role="status"` or `role="alert"` — a
  change of state that is only drawn is invisible to someone who cannot see it.
- **Everything works from a keyboard**, including the switches, which are
  styled `<div>`s upgraded in `js/ui/a11y.js` rather than rewritten.
- **Focus is visible.** One `:focus-visible` rule in `base.css`.

`tests/e2e/accessibility.test.js` runs axe over both views and then checks the
things axe cannot see: whether a control can be reached by keyboard, and
whether a status change is announced.

## The frontend

- One file per thing the user can see or do. A panel tab is a file.
- Functions stay on `window` — there is no bundler, and adding one would mean
  the app can no longer be opened from a folder.
- **Bump `?v=` in `index.html` when you change a `.js` or `.css` file.** The
  browser will happily serve yesterday's file otherwise, and you will debug
  code that is not running.
- Check `res.ok` before reading a response body. A 400 carries a sentence worth
  showing; ignoring it produces a `TypeError` three functions later.

## Gates (must pass before a commit is recommended)

| Area | Command |
|---|---|
| Dependency rule, routing, offline data | `.venv/bin/python -m pytest tests -q` |
| The resident's view in a real browser | `npm test --prefix tests/e2e` |
| App starts with nothing plugged in | `USE_LOCAL_DATA=1 .venv/bin/python -m uvicorn backend.main:app` |
| A route still comes back | `POST /route` with an origin inside District 1 |
