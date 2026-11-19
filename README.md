# AMAS-DRM

## Autonomous Multi-Agent System for Disaster and Resource Management

A B.Tech final-year project developed by the Department of Computer Engineering, Mizoram University.

AMAS-DRM is a disaster-response management platform designed to process emergency reports, identify incident locations, avoid hazardous areas during routing, and support resource allocation.

## Key Features

- **SOS Triage:** Uses Google Gemini when configured, with a rule-based fallback when Gemini is unavailable.
- **Location Resolution:** Supports coordinates, OpenStreetMap Nominatim geocoding, and a built-in gazetteer.
- **Hazard-Aware Routing:** Uses an OpenStreetMap road graph to calculate routes while avoiding road segments intersecting hazard zones.
- **Resource Allocation:** Uses Mixed-Integer Linear Programming (MILP) through PuLP.
- **Database:** PostgreSQL with PostGIS support.
- **Backend:** FastAPI.
- **Frontend:** React, Vite, and Leaflet.
- **Human Oversight:** Supports unresolved incident locations that require dispatcher review.

## System Architecture

1. Emergency reports are submitted to the backend.
2. The triage component extracts incident information and estimates severity.
3. The location component resolves the reported location using available geographic sources.
4. The routing engine calculates routes using the road network while avoiding hazard zones.
5. The allocation component supports resource assignment.
6. The dashboard presents incidents, depots, hazards, and routes to the dispatcher.

## Technology Stack

| Component    | Technology                       |
| ------------ | -------------------------------- |
| Backend      | Python, FastAPI                  |
| Frontend     | React 19, Vite                   |
| Map          | Leaflet, OpenStreetMap           |
| Routing      | OSMnx, NetworkX                  |
| Triage       | Google Gemini, rule-based parser |
| Optimization | PuLP, MILP                       |
| Database     | PostgreSQL 16, PostGIS 3.4       |
| Testing      | Pytest                           |

## Prerequisites

Install the following before starting:

- Python 3.11 or a compatible project-supported version
- Node.js and npm
- Docker Desktop
- Git
- VS Code (recommended)

## Installation and Setup (Windows PowerShell)

### 1. Clone the repository

```powershell
git clone https://github.com/sauravjyoti10/AMAS-DRM.git
cd AMAS-DRM
```

To use the latest development branch:

```powershell
git checkout fix/accurate-map-hazard-routing
git pull origin fix/accurate-map-hazard-routing
```

### 2. Create a Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Otherwise install dependencies:

```powershell
python -m pip install -r requirements.txt
```

### 3. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and add your own Gemini API key if you want AI-based triage.

The application can also use its rule-based triage fallback without a Gemini API key.

Never commit `.env` or publish API keys.

### 4. Start PostgreSQL and PostGIS

```powershell
docker compose up -d db
```

Check the database container:

```powershell
docker compose ps
```

### 5. Download the road network

```powershell
python -m scripts.download_map
```

This downloads the configured OpenStreetMap road graph.

### 6. Start the FastAPI backend

```powershell
uvicorn app.main:app --reload
```

Backend health endpoint:

http://localhost:8000/health

Interactive API documentation:

http://localhost:8000/docs

### 7. Start the React frontend

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite, normally:

http://localhost:5173

## Important Configuration

Configuration is managed through `app/config.py` and `.env`.

| Variable                | Default                     |
| ----------------------- | --------------------------- |
| GEMINI_MODEL            | gemini-3.1-flash-lite       |
| GEMINI_TIMEOUT_S        | 10                          |
| GEMINI_BUDGET_S         | 12                          |
| GEOCODE_ONLINE          | true                        |
| GEOCODE_BUDGET_S        | 4                           |
| MAX_SNAP_M              | 1000                        |
| DEFAULT_HAZARD_RADIUS_M | 400                         |
| GRAPH_PATH              | data/guwahati_roads.graphml |

See `.env.example` for the complete configuration template.

## Map and Routing Pipeline

1. **Triage:** Processes emergency messages using Gemini or the rule-based parser.
2. **Location:** Attempts to resolve coordinates or place names using online geocoding and the built-in gazetteer.
3. **Unresolved locations:** Locations that cannot be reliably resolved are left for dispatcher review rather than assigned an invented default point.
4. **Routing:** Uses the downloaded OSM road graph and avoids road segments that intersect hazard zones.
5. **Dashboard:** Displays incidents, depots, hazards, and route information.

Run the coverage check after downloading the map:

```powershell
python -m scripts.check_coverage
```

## Testing

Run the complete test suite:

```powershell
python -m pytest
```

The test modules cover triage, schemas, geocoding, routing, graph handling, hazards, allocation, and evaluation.

## Evaluation

Evaluation artifacts are stored in `evaluation/results/`.

The rules-based triage evaluation currently reports:

- 117 labelled messages
- 0 parse failures
- 98.3% severity accuracy
- 98.4% macro F1 score
- 98.0% recall for CRITICAL incidents

These figures describe the rules-based evaluation dataset and should not be interpreted as Gemini model accuracy or real-world field performance.

Routing, latency, and allocation evaluation results are also maintained in the evaluation results directory. Refer to the corresponding JSON and Markdown reports for methodology and metrics.

## Project Structure

```text
AMAS-DRM/
├── app/                  # Backend application and agents
├── data/                 # Road graph and geographic data
├── evaluation/           # Evaluation scripts and results
├── frontend/             # React dashboard
├── scripts/              # Map download and coverage checks
├── tests/                # Automated tests
├── .env.example          # Environment configuration template
├── docker-compose.yml    # PostgreSQL and PostGIS
├── requirements.txt      # Python dependencies
└── README.md
```

## Important Notes

- Online geocoding requires an internet connection.
- Nominatim usage must follow OpenStreetMap's usage policy.
- Gemini-based triage requires a valid API key.
- The rule-based parser is used as a fallback.
- Routing quality depends on the downloaded road network and the accuracy of incident coordinates.
- This project is an academic prototype and should not replace professional emergency-response systems.

## Academic Project

**Project:** Autonomous Multi-Agent System for Disaster and Resource Management (AMAS-DRM)

**Department:** Computer Engineering

**Institution:** Mizoram University
