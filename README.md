# AMAS-DRM: Autonomous Multi-Agent System for Disaster & Resource Management

B.Tech final year project, Department of Computer Engineering, Mizoram University.

## Setup (Step 1) - VS Code
Open the `amas-drm` folder in VS Code (File > Open Folder), accept the recommended extensions, then use the integrated terminal (Ctrl+`):

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                   # then edit .env with your NEW Gemini key
docker compose up -d db                                # PostgreSQL + PostGIS
python -m scripts.download_map                         # one-time map download
pytest                                                 # schema tests
uvicorn app.main:app --reload                          # open http://localhost:8000/health
```

Then pick the interpreter: Ctrl+Shift+P > "Python: Select Interpreter" > .venv. Press F5 to run the API; use Terminal > Run Task for DB, map and tests; open api.http and click "Send Request".

## How the map pipeline works
1. **Triage** reads the SOS (Gemini if `GEMINI_API_KEY` is set, otherwise a built-in rule parser) and keeps the place name as written, e.g. `Khanapara bus stand`.
2. **Location** is resolved from coordinates in the message, else OpenStreetMap (Nominatim, limited to the Guwahati box, cached in `data/geocode_cache.json`), else the built-in gazetteer (`app/gazetteer.py`). If none is trustworthy the incident is marked *unresolved* and a dispatcher pins it on the map; no default point is ever invented.
3. **Routing** runs on the real OSM road graph: it minimises travel time, follows true road geometry, and removes every road segment that touches a hazard zone (draw zones on the dashboard or `POST /api/hazards`). Points farther than `MAX_SNAP_M` from any road are refused.
4. The dashboard shows depots (blue squares) and incidents (round pins) differently, a dashed circle for location uncertainty, hazards in red, and the detour versus the unrestricted route in grey.

Run `python -m scripts.check_coverage` after downloading the map to confirm key places (including Khanapara) are covered.

## Roadmap
1. Scaffold, config, schemas, map (this step)
2. Triage Agent (Gemini + Pydantic)
3. Routing engine (OSMnx/NetworkX, hazard masking)
4. Allocation (MILP via PuLP)
5. PostGIS (depots, hazards, incidents, inventory)
6. LangGraph orchestration + Human-in-the-Loop
7. FastAPI endpoints + WebSocket
8. React + Leaflet dashboard
9. Benchmarks (triage P/R, routing safety, MILP vs FCFS, latency) and thesis
