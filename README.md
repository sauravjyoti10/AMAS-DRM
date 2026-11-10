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
