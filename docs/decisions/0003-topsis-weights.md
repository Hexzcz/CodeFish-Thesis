# ADR-0003: Flood risk outranks distance, 0.764 to 0.112

**Status:** accepted · superseded weights recorded below

## Context

A route has three criteria in tension: how flooded it is, how long it is, and
what class of road it uses. Something has to say which matters more, and the
answer is the thesis's central claim — not a tuning knob.

## Decision

TOPSIS ranks the candidate routes, with weights:

| Criterion | Weight |
|---|---|
| Flood exposure | 0.764 |
| Road class | 0.124 |
| Distance | 0.112 |

The same weights drive the WSM edge cost inside Dijkstra, so the path search
and the final ranking agree on what "better" means. They live in
`DEFAULT_WEIGHTS` in `domain/services/route_planner.py`; the API accepts an
override per request, which exists for sensitivity analysis, not for users.

## Consequences

- The router will accept a substantially longer route to avoid water. On the
  test network a 400 m dry route beats a 200 m flooded one — that is the
  behaviour, and `tests/test_routing.py` asserts it in both directions.
- Anyone changing these numbers is making a claim about evacuation policy.
  Record why here.
