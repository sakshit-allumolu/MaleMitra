# MaleMitra: 5-minute demo script

**One line:** during Bengaluru monsoon flooding, a citizen report becomes a verified road closure, and every commuter's route changes within seconds — using real roads and live traffic, not a toy map.

**Public URL:** https://malemitra.onrender.com (Render free plan). It sleeps after ~15 min idle and the first request takes 30-60 s, so open `/api/v1/health` in a browser 5 minutes before you present. Data resets on every restart; the 2 demo incidents are re-seeded. The local steps below are the fallback if the venue Wi-Fi is bad.

## Before you go on stage (10 min, do it the day before and again an hour before)

```bash
export PATH=$HOME/.rd/bin:$PATH          # Rancher Desktop only
lsof -nP -iTCP:8000 -sTCP:LISTEN          # must show only an 'ssh ... rancher-desktop' line (Docker's port forward); kill any Python/uvicorn
docker compose up -d                      # app + PostgreSQL + OSRM (first run downloads the map: minutes)
docker compose exec malemitra python -m backend.scripts.reset_demo   # known starting state
```

Checklist (all must be true):

- [ ] `http://localhost:8000` opens the login page; `docker compose ps` shows `malemitra-app` **healthy**.
- [ ] Banner shows **"Live Traffic:"** after a route search. If it says **"Typical Traffic:"**, the TomTom key is missing or the Wi-Fi blocks TomTom — the demo still works, just say it is the fallback.
- [ ] Browser hard-refreshed (Cmd+Shift+R) so you have the latest UI.
- [ ] Browser zoom 100%, window wide enough for the map to sit below the route cards.
- [ ] Stay in `DEMO_MODE=true`. Do **not** switch to production mode before the demo.

Log in with the one-click demo buttons on the login page (password `demo123`):
`citizen@malemitra.in` · `admin@malemitra.in` · `responder1@malemitra.in`.

## The story (follow the **Demo Guide** button in the top bar)

The orange **Demo Guide** button walks all 8 steps and switches users for you. If time is short, do steps 1–5 and skip 6–8.

| # | Say | Click | What the audience sees |
|---|-----|-------|------------------------|
| 1 | "A commuter sees Sony World underpass submerged and reports it." | Demo Guide → **1. Submit Citizen Report** | New incident on the map, status *reported* |
| 2 | "The control room triages and dispatches a team." | **2. Review & Assign Team Alpha** | Incident → *assigned*, team busy |
| 3 | "A responder on site confirms the road is impassable." | **3. Submit Field Verification** | Incident → *field verified*, hazard confidence rises |
| 4 | "Only an administrator can close a road." | **4. Authorize Road Blockage** | Road closed, **graph version increments** in the top bar |
| 5 | "Now watch what happens to a commuter's route." | **5. Compare Risk-Aware Routes** | Silk Board → Indiranagar: a second, risk-aware route that detours around the closed road (the guide uses this trip; a trip that starts *at* Sony World has nothing to avoid) |
| 6 | "The ripple engine shows where displaced traffic piles up." | **6. Run Ripple Simulation** | Congestion deltas on the parallel corridors |
| 7–8 | "Pumping is done; the loop closes." | **7**, then **8** | Road reopens, routes return to normal |

## The part to slow down on: live traffic + the route toggle (90 seconds)

Log in as the **citizen** and search a real corridor (type or use the Quick Corridors chips):

- **Sony World Junction → Indiranagar**, or **MG Road → Sony World**.

Then say and do:

1. "Roads come from our own OpenStreetMap routing server — real street names, turn by turn." Point at the **Real roads** badge and the directions list.
2. "Travel time uses **live** traffic, not a fixed rush-hour guess." Point at the **Live Traffic** banner and the **Live traffic delay** line on each card.
3. "Two routes: the standard one, and the MaleMitra risk-aware one that also prices flooding and closures." **Click each card** — the map shows only the one you pick, and the turn-by-turn list, voice and ETA follow it.
4. Turn on **Voice** for ten seconds if the room is quiet.

## Likely questions (honest answers)

- **"Is the traffic real?"** Yes: live travel times from the TomTom Routing API, used as a live-vs-free-flow ratio applied to our own road-following route. It does not change which roads are chosen. When TomTom is unreachable the banner says "Typical Traffic" and we use a time-of-day model.
- **"What about outside Bengaluru?"** Not supported; the app tells you ("outside the Bengaluru area MaleMitra can route in") rather than returning a wrong route.
- **"Does it scale?"** PostgreSQL holds the data, workers share state through it, and the test suite (234 tests) passes on SQLite and PostgreSQL. It has **not** been load-tested.
- **"Is the watsonx Orchestrate agent live?"** The agent tools and guardrails are tested here; the connection to a live Orchestrate instance has not been verified.
- **"Can anyone close a road?"** No. Citizen reports only add a routing *penalty*, scaled by reputation; only an admin closes a road.

## If something breaks on stage

| Symptom | Fix |
|---------|-----|
| Page won't load | `docker compose ps`; `docker compose restart malemitra` |
| Old UI / banner missing | Cmd+Shift+R; make sure no `Python`/`uvicorn` process listens on port 8000 (`lsof -nP -iTCP:8000 -sTCP:LISTEN`). An `ssh ... rancher-desktop/lima` listener is normal: it is Docker's port forward |
| `localhost:8000` refuses connections but `docker compose ps` says healthy | Docker's port forward dropped: `docker compose restart malemitra` |
| Banner says "Typical Traffic" | Check `TOMTOM_API_KEY` in `.env`, then `docker compose up -d`. Carry on — it is the fallback, not a failure |
| "Computing..." never ends | OSRM still starting: `docker compose logs osrm`. The app falls back to modelled geometry after a few seconds |
| Red box: "outside the Bengaluru area" | You clicked outside the city; pick a pin near Koramangala / Indiranagar / MG Road |
| Demo data is a mess | `docker compose exec malemitra python -m backend.scripts.reset_demo`, then refresh the browser |

## Reset between runs

```bash
docker compose exec malemitra python -m backend.scripts.reset_demo
```

Clears all incidents, reports, events and rate limits, re-opens every closed road, and re-creates the two sample incidents. It keeps the user accounts and the TomTom request counter, and **refuses to run unless `DEMO_MODE=true`**.

## Keep the TomTom quota safe

Flow polling uses up to about 1,500 requests/day and routing up to 800 (free tier ≈ 2,500). Repeated searches for the same pair within 2 minutes are cached. Do not script hundreds of searches. Check usage any time:

```bash
docker exec malemitra-app python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/api/v1/traffic/live').read().decode())"
```
