# Deploying CodeFish

The app is one container. It carries its own data, so a deployment needs no
database, no object storage and no API keys — `docker run` and it works.

**Deploy it for one reason above all others: HTTPS.** Live location and
installing the app to a home screen are both refused by browsers on an
insecure origin, so on a laptop over `http://` — or over a self-signed
certificate on the local network — the two features the resident's view is
built around simply do not run. Every host below terminates TLS for you.

## Locally

```bash
docker build -t codefish .
docker run --rm -p 8000:8000 codefish
```

Then http://localhost:8000. `localhost` is treated as a secure origin, so
geolocation works there without a certificate.

## Fly.io

```bash
fly launch --copy-config --no-deploy   # reads fly.toml; pick your own app name
fly deploy
```

`fly.toml` asks for 1 GB in Singapore and keeps one machine warm. Roughly $5
a month at the time of writing.

## Render

Point a Blueprint deploy at the repo and `render.yaml` is picked up. The free
plan works but sleeps when idle, and waking costs a cold start — the app loads
three models and samples terrain for 3,137 edges before it answers. Fine for
coursework; change `plan` to `starter` before a live demo.

## What it needs

| | |
|---|---|
| Memory | **318 MB** measured in the container with everything loaded. 512 MB is the floor; 1 GB is comfortable. |
| Image | ~2.1 GB, dominated by scipy, pandas, xgboost and the geo stack |
| Startup | ~10 s — models load and every road edge is sampled against the rasters |
| Disk | none. Nothing is written at runtime, and the container runs as a non-root user |
| Network | none required. The map basemap and JAXA rainfall use it when it is there |

## Configuration

Nothing is required. Everything optional is in [`.env.example`](../.env.example):
`DATABASE_URL` to read the road network from Postgres instead of the bundled
files, and `JAXA_USER` / `JAXA_PASS` for live rainfall. Set them as secrets in
the host's dashboard — never in the image.

`PORT` is honoured if the platform sets it, which Render and Railway do.

Worth setting once it is live: `REPORT_LEVEL=WARNING` to drop the per-request
scoring tables from the logs, and `ROUTE_RATE_LIMIT` if 30 requests a minute
per caller turns out to be the wrong number.

## The one thing that will break a naive image

`python:3.12-slim` does not ship `libexpat1` or `libgomp1`, and the rasterio
and XGBoost wheels link against them. Without both, the app dies at import
with a missing `.so` and no other clue. They are installed in the runtime
stage of the Dockerfile, and the `docker` job in CI builds and boots the image
on every push so this cannot regress unnoticed.
