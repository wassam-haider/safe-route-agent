"""One-time: geocode every Area in the crime CSV and save lat/lng centroids to data/area_centroids.json."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd  # noqa: E402

from app.config import settings, validate_settings  # noqa: E402
from app.services.geocoding import geocode  # noqa: E402

LAT_MIN, LAT_MAX, LNG_MIN, LNG_MAX = 24.70, 25.30, 66.70, 67.50  # rough Karachi box


def main() -> None:
    validate_settings()
    df = pd.read_csv(settings.crime_csv_path)
    df.columns = [str(c).strip() for c in df.columns]
    areas = sorted(df["Area"].astype(str).str.strip().unique())
    print(f"{len(areas)} unique areas")

    out, skipped = {}, []
    for area in areas:
        res = geocode(f"{area}, Karachi, Pakistan")
        if res and LAT_MIN <= res["lat"] <= LAT_MAX and LNG_MIN <= res["lng"] <= LNG_MAX:
            out[area] = [res["lat"], res["lng"]]
            print(f"ok      {area} -> {res['lat']:.4f}, {res['lng']:.4f}")
        else:
            skipped.append(area)
            print(f"SKIPPED {area}")
        time.sleep(0.05)

    settings.centroids_path.parent.mkdir(parents=True, exist_ok=True)
    settings.centroids_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nSaved {len(out)} areas to {settings.centroids_path}")
    if skipped:
        print("Skipped (add manually to the JSON if needed):", skipped)


if __name__ == "__main__":
    main()