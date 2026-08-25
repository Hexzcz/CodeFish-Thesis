# ADR-0005: Two views — a resident's and a console

**Status:** accepted · 2026-08-26

## Context

The app had one interface, and it was built for the person who wrote it. On
first load a resident met: a rainfall source toggle, forecast/historical tabs,
six observation-step pills, an FTP fetch button, an intensity readout in mm/hr,
a return-period mapping, seven raster layer toggles with opacity sliders, three
weight sliders, and — after routing — TOPSIS closeness coefficients, WSM costs
and per-segment XGBoost probability distributions. Seventy evacuation-center
pins were on the map before anything had been asked.

Every one of those controls earns its place for the thesis. None of them helps
somebody who wants to know where to walk.

## Decision

One page, two faces, chosen by `<html data-mode>`:

- **`simple`** (the default) asks one question — "Where are you right now?" —
  and answers it: destination, distance, walking time, and one sentence about
  flooding. The way there and the alternatives are one tap away. No layer
  controls, no weights, no model vocabulary, and no center pins until there is
  a route to show.
- **`admin`** is the console: the same three tabs regrouped as **Routing**
  (the task), **Layers** (what is drawn), and **Model** (what the router is
  told — rainfall source and criteria weights), plus the full analysis panel.

Reached with `?mode=admin`, then remembered in `localStorage`. There is no
password: the app exposes no private data, and a lock whose key sits in the
JavaScript would be theatre.

Both views share one map and one routing path — `requestRoutes()` — and both
set the origin through `setOrigin()`, which announces `codefish:origin-set`.
Neither view knows about the other's buttons.

## Consequences

- The engine's vocabulary now stops at one file. `plain_language.js` turns
  exposure and class counts into sentences; nothing else in the simple view
  formats a number. `tests/test_risk_thresholds_agree.py` fails the build if
  its risk bands drift from the engine's.
- The recommendation is often not the shortest route, which looks like a bug
  until it is explained. When every shorter alternative is riskier, the card
  says so: "Shorter ways exist, but they cross roads that may flood."
- Two views means two things to keep working. The simple view is the one a
  stranger meets, so it is the one to check first after a change.
- Desktop-first, per the brief. The layout does not yet reflow for phones —
  the likeliest device for an actual evacuation, and the obvious next step.
