"""Fetch the subway station list that the detail pages measure against.

.. code-block:: text

    MTA Subway Stations -> subway.py -> subway_stations.json

Run it through just::

    just ingest-subway

Separate from ``ingest.py`` for two reasons. The stations come from the *state*
portal, ``data.ny.gov``, rather than the city's -- the MTA publishes there --
and they are not study spots: nothing here reaches the ``spots`` table or the
API. This is a reference list the frontend build measures distances against,
the same way it measures them between spots.

Like ``spots.json``, the output is committed. A checkout can build every detail
page without the network, and a change to the subway system is a reviewable diff
rather than something that silently moves under a deployment.

Why a station and not an entrance
---------------------------------

The MTA also publishes entrances, which would be more accurate: a station can
span two avenues and its entrances with it. Stations are used because the
published distance is then "to the station", which is what a person reads it
as, and because an entrance list invites a precision the rest of this snapshot
does not have -- the spot coordinates are themselves building centroids.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DEFAULT_OUTPUT = HERE / "subway_stations.json"

#: MTA Subway Stations, on the state portal.
STATIONS_URL = "https://data.ny.gov/resource/39hk-dx4f.json"

#: 496 stations today. The ceiling is a guard against a silent truncation, not
#: a page size: one request is enough and the importer would rather fail than
#: publish a partial list.
REQUEST_LIMIT = 1000

HTTP_TIMEOUT_SECONDS = 60

USER_AGENT = "StudySpot-ingest/1.0 (+https://github.com/gcivil-nyu-org/team-4-fall26)"

#: What the MTA's `ada` column means. 2 is one direction only -- a platform you
#: can reach going one way and not the other -- which is worth distinguishing
#: from both of the others rather than rounding to "yes" or "no".
STEP_FREE = {"0": "none", "1": "full", "2": "partial"}

#: Best first, for picking one value across a merged complex.
STEP_FREE_RANK = ("full", "partial", "none")


class SubwayError(RuntimeError):
    """Raised when the upstream data cannot be turned into a station list."""


def fetch(url: str = STATIONS_URL) -> list[Any]:
    """Every station, in one request."""
    request = urllib.request.Request(
        f"{url}?$limit={REQUEST_LIMIT}",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except urllib.error.URLError as error:
        raise SubwayError(f"Could not reach {url}: {error}") from error

    if not isinstance(payload, list):
        raise SubwayError(f"{url} did not return an array of stations.")
    if len(payload) >= REQUEST_LIMIT:
        raise SubwayError(f"{url} returned {len(payload)} rows, which may be truncated.")
    return payload


def route_key(route: str) -> tuple[int, str]:
    """Numbered lines before lettered ones, which is how a sign reads."""
    return (0, route) if route.isdigit() else (1, route)


def normalize(rows: list[Any]) -> list[dict[str, Any]]:
    """Map the upstream rows onto the few fields a distance needs.

    Rows are merged on ``complex_id``, which is the MTA's own grouping and
    turns 496 rows into 445 stations. Without it a station appears once per
    line and a page shows half its trains: W 4 St-Wash Sq is published twice,
    as "A C E" and as "B D F M", at identical coordinates.
    """
    complexes: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise SubwayError("An upstream station is not a JSON object.")

        name = (row.get("stop_name") or "").strip()
        routes = (row.get("daytime_routes") or "").split()
        latitude = row.get("gtfs_latitude")
        longitude = row.get("gtfs_longitude")

        if not name or not routes or latitude is None or longitude is None:
            raise SubwayError(f"Station {name or row.get('station_id')!r} is missing a field.")

        complexes.setdefault(str(row.get("complex_id") or row.get("station_id")), []).append(
            {
                "name": name,
                "routes": routes,
                "latitude": float(latitude),
                "longitude": float(longitude),
                "step_free": STEP_FREE.get(str(row.get("ada")), "none"),
            }
        )

    stations: list[dict[str, Any]] = []
    for group in complexes.values():
        # A complex can carry more than one name -- Times Sq-42 St and 42 St-
        # Port Authority Bus Terminal are one place. The name on the most lines
        # wins, then the shorter, then alphabetical, so the result does not
        # depend on the order upstream returned rows in.
        named = sorted(group, key=lambda row: (-len(row["routes"]), len(row["name"]), row["name"]))
        routes = sorted({route for row in group for route in row["routes"]}, key=route_key)

        # The best access across the complex: one step-free platform is what a
        # person needs to know, and which line they want is not ours to guess.
        step_free = min(
            (row["step_free"] for row in group), key=lambda value: STEP_FREE_RANK.index(value)
        )

        stations.append(
            {
                "name": named[0]["name"],
                "routes": routes,
                # The centre of the complex, which can span a block.
                "latitude": round(sum(r["latitude"] for r in group) / len(group), 6),
                "longitude": round(sum(r["longitude"] for r in group) / len(group), 6),
                "step_free": step_free,
            }
        )

    if not stations:
        raise SubwayError("The station list is empty.")

    # Sorted so that an unchanged upstream produces a byte-identical file and
    # the diff shows what actually moved.
    return sorted(stations, key=lambda station: (station["name"], station["routes"]))


def main(argv: list[str] | None = None) -> int:
    output = Path(argv[0]) if argv else DEFAULT_OUTPUT
    try:
        stations = normalize(fetch())
    except SubwayError as error:
        print(f"subway: {error}", file=sys.stderr)
        return 1

    output.write_text(json.dumps(stations, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    step_free = sum(1 for station in stations if station["step_free"] == "full")
    print(f"wrote {len(stations)} stations ({step_free} step-free) to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
