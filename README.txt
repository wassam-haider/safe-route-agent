SafeRoute Agent
===============

SafeRoute Agent is a web and command-line chat application. The web app runs locally at http://127.0.0.1:8000.

Requirements
------------
- Python 3.12
- uv
- Kaggle crime data CSV saved as data/karachi_crime.csv
- Required API credentials configured in a .env file

Setup
-----
Run these commands from the project directory (saferoute-agent):

    uv venv --python 3.12

Windows PowerShell:

    .\.venv\Scripts\Activate.ps1

Linux or macOS:

    source .venv/bin/activate

Then install dependencies:

    uv pip install -r requirements.txt

Copy or create a .env file and add the required API credentials. Place the Kaggle crime CSV at data/karachi_crime.csv.

Run the following once to build area centroids from the crime data:

    python scripts/build_area_centroids.py

Run the web application:

    uvicorn app.main:app --reload --port 8000

Open http://127.0.0.1:8000 in a browser.

Run the terminal chat instead:

    python run_cli.py

Type exit or quit to leave the terminal chat.
