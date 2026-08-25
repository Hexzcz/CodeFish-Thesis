# ADR-0004: Rainfall comes from GSMaP_NOW, and is observed, not forecast

**Status:** accepted · 2026-08-25

## Context

The rainfall fetch asked JAXA's FTP server for `/forecast/archive/`. That path
does not exist and never did: every request returned `550 No such file or
directory`, the exception handler swallowed it, and the UI displayed the
resulting 0.0 as `0.00 mm/hr` — indistinguishable from a dry day.

The UI offered a 1–6 hour "short range" forecast and a 1–5 day "medium range"
forecast built on top of this.

## Decision

Read GSMaP_NOW from `/now/latest/`, which is real and holds half-hourly
**observed** rain rate for the last 24 hours (`gsmap_now.YYYYMMDD.HHNN.dat.gz`,
UTC start time).

That product has no forecast lead time, so the UI changed to match the data:
the step selector walks *back* in hours from the newest file (Now, −1h … −5h)
and the medium range is gone. Failures raise 502.

## Consequences

- The panel shows what is falling now, not what will fall later. The tab is
  labelled LATEST rather than FORECAST because claiming a forecast we do not
  have is worse than not having one.
- Genuine forecast lead times would mean a different product —
  `/riken_nowcast/` publishes hourly `gsmap_rnc_*` files — and a different
  decision record.
- `/realtime/archive/` still serves the historical tab. It lags by about a day,
  so "today" returns 550, which now surfaces as an error rather than as no rain.
