# SafeRoute Agent

A LangChain-based AI agent that recommends the *safest* route between two
points in Karachi, Pakistan — not just the fastest one. It cross-references
routing, historical crime data, live news/web search, and weather to score
multiple candidate routes and explain its pick.

## What it does

Tell it where you're starting, where you're going, and how you're
travelling (car, motorcycle, bicycle, walking, public transport). The agent:

1. Fetches several candidate routes (OpenStreetMap/OSRM).
2. Scores each route's **crime risk** using a historical Karachi crime
   dataset, weighted by area, time of day, and transport mode.
3. Runs a handful of targeted web searches for *today's* incidents
   (firing, robbery, accidents, traffic) and *this week's* announced
   protests/rallies/road closures along each route's areas and roads.
4. Checks the weather for the trip's departure time.
5. Combines all of this into a weighted safety/traffic/time score per
   route and returns a structured recommendation — best route, why, the
   alternatives, and any caveats about thin evidence.

If something essential is missing (start, destination, or transport mode)
it asks a single clarifying question instead of guessing.

## Architecture

Built with LangChain's `create_agent` (tool-calling agent loop) and a
Pydantic `ToolStrategy` structured output (`AskUser` | `RouteRecommendation`),
served through FastAPI with a small browser chat UI, plus a terminal CLI.

```
app/
├── agent.py          # agent setup, session history, turn loop
├── prompts.py        # system prompt: the agent's step-by-step safety workflow
├── schemas.py        # AskUser / RouteRecommendation structured outputs
├── middleware.py      # agent middleware
├── results.py        # response finalization / rendering
├── tools/
│   ├── route_tools.py        # get_routes, score_routes
│   ├── scoring_tools.py       # risk/score aggregation helpers
│   ├── location_tools.py      # geocode_location
│   └── intelligence_tools.py  # get_crime_risk, get_weather, web_search
├── services/
│   ├── routing.py    # OSRM route fetching + traffic-factor estimation
│   ├── crime.py      # historical Karachi crime dataset -> area risk scores
│   ├── scoring.py    # weighted route scoring (priority: balanced/fastest/safest)
│   ├── search.py     # Tavily web search (news/recency-aware)
│   ├── weather.py    # weather-based risk per mode
│   └── geocoding.py  # Nominatim/OpenRouteService geocoding
└── main.py           # FastAPI app: /api/chat, /api/reset
```

## Running it

```bash
uv venv --python 3.12
# Windows: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate

uv pip install -r requirements.txt

# add API credentials to a .env file (OpenRouter, Tavily, routing/geocoding)
# place the Kaggle Karachi crime dataset at data/karachi_crime.csv

python scripts/build_area_centroids.py   # build area centroids from the crime data

uvicorn app.main:app --reload --port 8000
# open http://127.0.0.1:8000

# or chat from the terminal instead:
python run_cli.py
```

## Tech stack

Python, LangChain (`create_agent`), FastAPI, Pydantic, OpenRouter, Tavily
web search, OSRM/OpenStreetMap routing, pandas
