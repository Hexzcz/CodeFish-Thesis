# ADR-0007: Live navigation, and a second map for 3D

**Status:** accepted · 2026-08-26

## Context

The resident's view answered "where do I go" and then stopped. Someone who
starts walking has different questions — am I still on the right road, how much
further, what if I take a wrong turn — and a flat overview map answers none of
them well while moving.

Leaflet, which the app has always used, cannot tilt or rotate. That is not a
setting; it has no camera pitch at all.

## Decision

**MapLibre GL JS as a second map, not a replacement.** The 2D Leaflet map is
untouched and remains the view for reading a whole route and the flood picture.
3D is a separate `#map-3d` container, created on demand and lazily loaded, so
the resident's first paint never pays for 800 KB of WebGL library. Switching
hides one and shows the other; the app's state lives in neither.

**No new map data provider.** The 3D view draws the same Esri basemap and takes
its terrain from CodeFish's own DEM through a new `/tiles/terrain-rgb`
endpoint, rendered by the existing rio-tiler adapter. No API key, no vector
tile subscription, and terrain that works offline once cached.

Buildings are not included. There are no footprints in the repo, and District 1
is dense enough that fetching them would add megabytes to a phone install. The
3D value here is the tilted, heading-up camera, not the skyline — District 1
rises about 20 m across 7 km, which is why terrain is exaggerated 3×.

**Where you are along the route is decided by the backend.**
`backend/domain/navigation/progress.py` computes distance from the route,
distance remaining and arrival; `POST /navigation/progress` exposes it. The
browser sends a position and gets an answer — it does not carry a second copy
of the geometry, and there is no second definition of "off route" to drift.

Calls are throttled to one per 2 seconds *and* 15 m moved, which at walking
pace is roughly one every ten seconds rather than one per GPS fix.

**Rerouting is the existing router.** A confirmed deviation calls the same
`POST /route`, with the same weights and the same ranking that chose the first
route. Nothing in the navigation code selects a path. A shortest-distance
fallback is never substituted: if rerouting fails, the previous safe route
stays on screen and the app says it could not update.

## Consequences

- **Three GPS fixes off-route before rerouting**, with a 20-second cooldown. A
  single stray fix is not a wrong turn, and a phone that reroutes on jitter is
  worse than one that waits.
- **Losing 3D does not cost live tracking.** If the 3D map cannot start —
  no usable WebGL, or a page that began hidden, which suspends the animation
  frames MapLibre needs — navigation continues on the flat map with the same
  marker and following, and says so once. A 15-second timeout enforces this;
  without it, navigation waits forever for a map that is never coming.
- **Offline, the app follows but stops checking.** Distance remaining and
  off-route warnings come from the server, so both pause with the connection.
  The status says so rather than showing a stale number or an unearned "on
  track". Rerouting offline is impossible and is never implied.
- Continuous GPS costs battery. The watcher starts only on *Start navigation*,
  stops on *Stop*, on `pagehide`, and when the page is hidden.
- Geolocation and service workers both need HTTPS. On plain http from another
  machine, live tracking does not start and the error says why.
