"""Turn NYC Open Data into the normalized study-spot snapshot.

.. code-block:: text

    NYC Open Data -> ingest.py -> spots.json

Run it through just, which writes ``data/spots.json`` in place::

    just ingest

The snapshot stays in version control, so a checkout can load the serving table
and run the API without reaching the network. Regenerating it is how the data
changes; nothing writes to ``spots.json`` at runtime.

Where the records come from
---------------------------

One dataset: the city's Facilities Database (FacDB, Socrata ``ji82-xba5``),
which is what the ``facdb:`` identifier prefix refers to. Two subsets of it are
places a student might read in -- the ``LIBRARIES`` facility group and the
``COLLEGES OR UNIVERSITIES`` subgroup. Neighborhood names come from a second
dataset, the 2020 Neighborhood Tabulation Areas (``9nt8-h7nd``), because FacDB
publishes the NTA code and not its name.

FacDB does not list cafés, so no record maps to the published ``cafe`` category
yet. The obvious candidate, the health department's restaurant inspection
results, is an inspection log rather than a directory of open businesses: it
keeps establishments that closed years ago and carries no 2020 NTA, so
publishing it as study spots would assert more than the data supports.

Why the identifiers look like that
----------------------------------

An identifier is the source prefix and FacDB's own ``uid``, as in
``facdb:eec118768e15a5e03d3354abda7b00da``. The digest is upstream's, derived
from the source record, and this importer treats it as the record's identity
rather than computing one of its own.

That choice is about churn. ``load_spots`` replaces the whole table rather than
upserting, so an identifier derived from a record's *contents* -- its name,
address or coordinates -- would change every time the city fixed a typo or
re-geocoded a building, and every row of the snapshot would silently come back
as a different spot with the old one deleted. Anything holding an identifier,
including a bookmarked ``GET /spots/{id}``, would break for a cosmetic edit
upstream. Deriving the identifier from identity alone means re-running this
importer against unchanged upstream data produces a byte-identical snapshot,
and a changed name is an update to one row.

The prefix is not decoration: it keeps a second source from colliding with
FacDB if its keys happen to look the same, and it says where a record came
from.

What normalization does
-----------------------

Presentation is part of it. FacDB writes names and addresses in capitals, and
the published contract shows "125th Street Library" rather than "125TH STREET
LIBRARY", so this module title-cases both. Coordinates are rounded to six
decimal places, about a tenth of a metre, which is finer than a building and
keeps the snapshot small.

``address``, ``neighborhood`` and ``university`` are absent for some records.
They are written as ``null``, never as an empty string: the contract
distinguishes the two and the API returns ``null``.

``university`` is proximity and nothing else
--------------------------------------------

It names the closest campus within 500 metres, or the campus itself for a
campus record, and is ``null`` when no campus is that close. The campus list is
curated -- it is the higher-education subset of FacDB named above, the same
records this importer publishes as ``university`` spots -- and the field is
never guessed from a facility's name, its operator, or anything else.

A named campus is not an affiliation, an endorsement, or a claim that anyone
may walk in: 169 metres is what the data says about "125th Street Library" and
"Touro University - Harlem", and it says nothing more than that.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: ``data/ingest.py`` -> ``data/``.
HERE = Path(__file__).resolve().parent

DEFAULT_OUTPUT = HERE / "spots.json"

#: Trimmed upstream responses, so the tests and `--fixtures` need no network.
DEFAULT_FIXTURES = HERE / "fixtures"

SOCRATA_DOMAIN = "data.cityofnewyork.us"

#: Facilities Database. The ``facdb:`` identifier prefix names this dataset.
FACILITIES_DATASET = "ji82-xba5"
FACILITIES_WHERE = "facgroup = 'LIBRARIES' OR facsubgrp = 'COLLEGES OR UNIVERSITIES'"

#: 2020 Neighborhood Tabulation Areas, for the names FacDB only codes.
NEIGHBORHOODS_DATASET = "9nt8-h7nd"

SOURCE_PREFIX = "facdb"

#: Socrata serves at most 1,000 rows per request.
PAGE_SIZE = 1000

#: Anonymous requests share one throttled pool. A token raises the limit and is
#: free; it is read from the environment so it never reaches version control.
APP_TOKEN_VARIABLE = "NYC_OPEN_DATA_APP_TOKEN"

HTTP_TIMEOUT_SECONDS = 60

#: NYC Open Data asks for identifiable traffic and sheds load under pressure.
#: Two requests do not need a budget, but paging politely costs nothing.
PAGE_DELAY_SECONDS = 0.25
USER_AGENT = "StudySpot-ingest/1.0 (+https://github.com/2SpaceMasterRace/studyspot)"

#: The fields ``load_spots`` accepts. A tenth field fails the load rather than
#: being dropped, so the importer checks its own output against this.
CONTRACT_FIELDS = (
    "id",
    "name",
    "category",
    "address",
    "neighborhood",
    "borough",
    "latitude",
    "longitude",
    "university",
)

#: The published category vocabulary, keyed on FacDB's most specific type so
#: that a new upstream type fails loudly instead of landing in a near-enough
#: bucket. ``None`` is a deliberate exclusion rather than a missing mapping.
#:
#: ``SPECIAL LIBRARIES`` are institutional collections -- a club's, a society's,
#: a hospital's -- and many are open by appointment or to members only. They map
#: to ``library`` because that is the kind of place they are; the contract has
#: no field for access, and the application promises none.
CATEGORY_BY_FACILITY_TYPE: dict[str, str | None] = {
    "PUBLIC LIBRARY": "library",
    "NYCHA COMMUNITY CENTER - LIBRARY": "library",
    "SPECIAL LIBRARIES": "library",
    "ACADEMIC LIBRARIES": "academic_library",
    "2 YEAR INDEPENDENT": "university",
    "2 YEAR PROPRIETARY": "university",
    "4 YEAR PROPRIETARY": "university",
    "4-YEAR INDEPENDENT": "university",
    "CUNY - 4 YEAR COLLEGE": "university",
    "CUNY - COMMUNITY COLLEGE": "university",
    "CUNY - GRADUATE CENTER": "university",
    "GRADUATE PROGRAMS ONLY": "university",
    "SUNY - COMMUNITY COLLEGES": "university",
    "SUNY - HEALTH SCIENCE CENTERS": "university",
    "SUNY - SPECIALIZED COLLEGES": "university",
    # Someone's home. Listing it as a place to study would invite people to a
    # residence.
    "UNIVERSITY RESIDENTIAL STRUCTURE": None,
}

CAMPUS_CATEGORY = "university"

#: Close enough to walk out of one and into the other.
CAMPUS_RADIUS_METRES = 500.0

BOROUGH_BY_FACILITY_BOROUGH = {
    "MANHATTAN": "Manhattan",
    "BROOKLYN": "Brooklyn",
    "QUEENS": "Queens",
    "BRONX": "Bronx",
    "STATEN ISLAND": "Staten Island",
}

#: About a tenth of a metre, and what the published example record shows.
COORDINATE_DIGITS = 6

EARTH_RADIUS_METRES = 6_371_000.0

#: Initialisms FacDB shouts for a reason, and which title case would mangle.
#: Every one of these appears in the facilities the importer publishes; a type
#: this list has not caught yet shows up as "Cuny" in the snapshot.
INITIALISMS = frozenset(
    {
        "AMG",
        "CUNY",
        "IE",
        "LIU",
        "MCNY",
        "NY",
        "NYADI",
        "NYC",
        "NYFA",
        "NYU",
        "SI",
        "SNFL",
        "SUNY",
    }
)

MINOR_WORDS = frozenset(
    {"a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to"}
)

#: "125TH STREET" is a street number, not emphasis.
ORDINAL = re.compile(r"^(\d+)(ST|ND|RD|TH)$", re.IGNORECASE)

#: Keeps an apostrophe inside its word, so "ST JOHN'S" does not become
#: "St John'S", and keeps every other run of punctuation as a separator, so
#: "100% COFFEE" keeps its per cent sign.
WORD_BOUNDARY = re.compile(r"([^\w']+)")


class IngestError(Exception):
    """The importer cannot produce a snapshot the loader would accept."""


@dataclass(frozen=True)
class Campus:
    """One entry of the curated campus list."""

    name: str
    latitude: float
    longitude: float


def warn(message: str) -> None:
    print(f"ingest: {message}", file=sys.stderr)


# -- Upstream ----------------------------------------------------------------


def socrata_page(dataset: str, params: dict[str, Any], token: str | None) -> list[Any]:
    url = f"https://{SOCRATA_DOMAIN}/resource/{dataset}.json?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    if token:
        request.add_header("X-App-Token", token)

    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 429:
            raise IngestError(
                "NYC Open Data is throttling this client. Request a free app token at "
                f"https://{SOCRATA_DOMAIN}/profile/edit/developer_settings and export it as "
                f"{APP_TOKEN_VARIABLE}."
            ) from error
        detail = error.read(100).decode("utf-8", "replace").strip()
        raise IngestError(
            f"NYC Open Data answered HTTP {error.code} for dataset {dataset}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise IngestError(
            f"Could not reach {SOCRATA_DOMAIN} ({error.reason}). "
            "Pass --fixtures to run against the committed sample instead."
        ) from error

    if not isinstance(payload, list):
        raise IngestError(
            f"Dataset {dataset} answered with {type(payload).__name__}, not an array."
        )
    return payload


def socrata_rows(dataset: str, params: dict[str, Any], token: str | None, order: str) -> list[Any]:
    """Every row matching ``params``, one page at a time.

    ``order`` is a column of this dataset: ``$offset`` paging over an unordered
    query can repeat and skip rows.
    """
    rows: list[Any] = []
    offset = 0
    while True:
        page = socrata_page(
            dataset,
            {**params, "$order": order, "$limit": PAGE_SIZE, "$offset": offset},
            token,
        )
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE
        time.sleep(PAGE_DELAY_SECONDS)


def fixture_rows(directory: Path, name: str) -> list[Any]:
    path = directory / f"{name}.json"
    if not path.exists():
        raise IngestError(f"No fixture at {path}.")
    rows = json.loads(path.read_text("utf-8"))
    if not isinstance(rows, list):
        raise IngestError(f"{path} must contain an array of upstream records.")
    return rows


def read_sources(fixtures: Path | None) -> tuple[list[Any], list[Any]]:
    """The raw upstream records, from the network or from a fixture directory."""
    if fixtures is not None:
        return fixture_rows(fixtures, "facilities"), fixture_rows(fixtures, "neighborhoods")

    token = os.environ.get(APP_TOKEN_VARIABLE) or None
    if not token:
        warn(f"no {APP_TOKEN_VARIABLE} set; using the shared anonymous rate limit")

    facilities = socrata_rows(FACILITIES_DATASET, {"$where": FACILITIES_WHERE}, token, order="uid")
    neighborhoods = socrata_rows(
        NEIGHBORHOODS_DATASET,
        # The boundaries themselves are megabytes of geometry, and the code and
        # its name are all this needs.
        {"$select": "nta2020,ntaname"},
        token,
        order="nta2020",
    )
    return facilities, neighborhoods


# -- Normalization -----------------------------------------------------------


def text(value: Any) -> str | None:
    """A trimmed string, or ``None`` for anything upstream left blank."""
    if not isinstance(value, str):
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def title_word(word: str, *, minor_allowed: bool) -> str:
    stem, apostrophe, suffix = word.partition("'")
    if apostrophe and suffix.upper() == "S" and stem.upper() in INITIALISMS:
        return f"{stem.upper()}'s"

    shouted = word.upper()
    if shouted in INITIALISMS:
        return shouted

    ordinal = ORDINAL.match(word)
    if ordinal:
        return f"{ordinal.group(1)}{ordinal.group(2).lower()}"

    # A one-letter word is a middle initial far more often than it is an
    # article: "STEPHEN A. SCHWARZMAN BUILDING".
    if minor_allowed and len(word) > 1 and word.lower() in MINOR_WORDS:
        return word.lower()

    if shouted.startswith("MC") and len(word) > 3 and word.isalpha():
        return f"Mc{word[2:].capitalize()}"

    return word.capitalize()


def title_case(value: str) -> str:
    """Make a shouted FacDB string readable.

    Best effort, and deliberately so: the alternative to a short rule set is
    showing people "125TH STREET LIBRARY", which the published contract does
    not. Mixed-case input is normalized the same way, because FacDB is not
    consistent about which rows shout.
    """
    parts = WORD_BOUNDARY.split(" ".join(value.split()))
    words = [index for index, part in enumerate(parts) if index % 2 == 0 and part]
    rebuilt: list[str] = []
    separator = ""
    for index, part in enumerate(parts):
        if index % 2:
            separator = part
            rebuilt.append(part)
            continue
        if not part:
            continue
        # A minor word only stays lowercase in the middle of a phrase. After a
        # bracket or a dash it begins one -- "Juilliard School (The)", "Rose
        # Hill-Lincoln" -- and FacDB truncates long names mid-word, which leaves
        # a trailing "A" that is not an article.
        inside = index not in (words[0], words[-1]) and separator.isspace()
        rebuilt.append(title_word(part, minor_allowed=inside))
    return "".join(rebuilt)


def spot_id(record: dict[str, Any]) -> str:
    uid = text(record.get("uid"))
    if not uid:
        raise IngestError(f"An upstream record has no uid: {record.get('facname')!r}.")
    return f"{SOURCE_PREFIX}:{uid}"


def category(record: dict[str, Any]) -> str | None:
    """The published category, or ``None`` for a deliberately excluded type."""
    facility_type = text(record.get("factype"))
    if facility_type is None:
        raise IngestError(f"Record {spot_id(record)} has no facility type.")
    try:
        return CATEGORY_BY_FACILITY_TYPE[facility_type.upper()]
    except KeyError:
        # Inventing a category here would publish a guess as data, and mapping
        # it to the nearest existing one would bury the change. FacDB added a
        # type; someone has to decide what it is.
        raise IngestError(
            f"Record {spot_id(record)} has the unmapped facility type {facility_type!r}. "
            "Add it to CATEGORY_BY_FACILITY_TYPE, or map it to None to exclude it."
        ) from None


def borough(record: dict[str, Any]) -> str:
    name = text(record.get("boro"))
    if name is None:
        raise IngestError(f"Record {spot_id(record)} has no borough.")
    try:
        return BOROUGH_BY_FACILITY_BOROUGH[name.upper()]
    except KeyError:
        raise IngestError(
            f"Record {spot_id(record)} is in {name!r}, which is not one of the five boroughs."
        ) from None


def street_address(record: dict[str, Any]) -> str | None:
    """The address as the contract publishes it, or ``None``.

    FacDB leaves the street address off a few dozen library branches. The
    remaining pieces -- a city and a zip code -- are not an address, so the
    field stays null rather than becoming ", New York, NY 11208".
    """
    street = text(record.get("address"))
    if street is None:
        return None

    parts = [title_case(street)]
    city = text(record.get("city"))
    if city:
        parts.append(title_case(city))
    zipcode = text(record.get("zipcode"))
    parts.append(f"NY {zipcode}" if zipcode else "NY")
    return ", ".join(parts)


def neighborhood_names(rows: list[Any]) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = text(row.get("nta2020"))
        name = text(row.get("ntaname"))
        if code and name:
            names[code] = name
    if not names:
        raise IngestError("The neighborhood dataset supplied no 2020 NTA names.")
    return names


def neighborhood(record: dict[str, Any], names: dict[str, str]) -> str | None:
    """The 2020 NTA name, or ``None`` when the source does not place the record."""
    code = text(record.get("nta2020"))
    if code is None:
        return None
    name = names.get(code)
    if name is None:
        # The two datasets are revised on their own schedules, so a code can
        # outrun the boundary file. Publishing the code instead would put a
        # string like "MN1102" where the contract promises a name.
        warn(f"no 2020 NTA name for {code!r}; leaving {spot_id(record)} without a neighborhood")
    return name


def coordinate(record: dict[str, Any], field: str, limit: float) -> float | None:
    raw = record.get(field)
    if raw is None or raw == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise IngestError(f"Record {spot_id(record)} has a non-numeric {field}: {raw!r}.") from None
    if not math.isfinite(value) or abs(value) > limit:
        raise IngestError(f"Record {spot_id(record)} has an out-of-range {field}: {value!r}.")
    return round(value, COORDINATE_DIGITS)


def haversine_metres(
    latitude: float, longitude: float, other_latitude: float, other_longitude: float
) -> float:
    first, second = math.radians(latitude), math.radians(other_latitude)
    delta_latitude = second - first
    delta_longitude = math.radians(other_longitude - longitude)
    arc = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(first) * math.cos(second) * math.sin(delta_longitude / 2) ** 2
    )
    return 2 * EARTH_RADIUS_METRES * math.asin(math.sqrt(arc))


def nearest_campus(latitude: float, longitude: float, campuses: list[Campus]) -> str | None:
    """The closest curated campus within ``CAMPUS_RADIUS_METRES``, if any.

    Proximity, not affiliation: see this module's docstring.
    """
    nearby = [
        (haversine_metres(latitude, longitude, campus.latitude, campus.longitude), campus.name)
        for campus in campuses
    ]
    # Sorting on the name too keeps two equidistant campuses from making the
    # snapshot depend on the order upstream happened to return rows in.
    within = sorted(pair for pair in nearby if pair[0] <= CAMPUS_RADIUS_METRES)
    return within[0][1] if within else None


def normalize(facilities: list[Any], names: dict[str, str]) -> list[dict[str, Any]]:
    """The whole mapping, from raw upstream records to contract records."""
    spots: list[dict[str, Any]] = []
    skipped = 0

    for record in facilities:
        if not isinstance(record, dict):
            raise IngestError("An upstream record is not a JSON object.")

        published_category = category(record)
        if published_category is None:
            continue

        name = text(record.get("facname"))
        if name is None:
            raise IngestError(f"Record {spot_id(record)} has no name.")

        latitude = coordinate(record, "latitude", 90.0)
        longitude = coordinate(record, "longitude", 180.0)
        if latitude is None or longitude is None:
            # Nothing can place these on a map, and the model requires both.
            # Upstream ungeocoded rows should not fail a whole import.
            skipped += 1
            continue

        spots.append(
            {
                "id": spot_id(record),
                "name": title_case(name),
                "category": published_category,
                "address": street_address(record),
                "neighborhood": neighborhood(record, names),
                "borough": borough(record),
                "latitude": latitude,
                "longitude": longitude,
                # Filled in below: it depends on the rest of the snapshot.
                "university": None,
            }
        )

    if skipped:
        warn(f"skipped {skipped} record(s) without coordinates")

    campuses = [
        Campus(spot["name"], spot["latitude"], spot["longitude"])
        for spot in spots
        if spot["category"] == CAMPUS_CATEGORY
    ]
    for spot in spots:
        if spot["category"] == CAMPUS_CATEGORY:
            spot["university"] = spot["name"]
        else:
            spot["university"] = nearest_campus(spot["latitude"], spot["longitude"], campuses)

    validate(spots)
    # Identifiers rather than names: a renamed facility then moves one line of
    # the snapshot instead of shifting every record after it.
    return sorted(spots, key=lambda spot: spot["id"])


def validate(spots: list[dict[str, Any]]) -> None:
    """Refuse a snapshot ``load_spots`` would reject.

    The loader validates every record too, but it runs at deployment time and
    inside a Lambda function. Failing here points at the importer instead.
    """
    seen: set[str] = set()
    for spot in spots:
        if tuple(spot) != CONTRACT_FIELDS:
            raise IngestError(
                f"Record {spot['id']} does not match the shared contract: {list(spot)}."
            )
        if spot["id"] in seen:
            # Two records with one identifier means uid is not the identity it
            # is being used as, and the load would quietly keep one of them.
            raise IngestError(f"Duplicate identifier {spot['id']!r}.")
        seen.add(spot["id"])
        for field in ("name", "category", "borough"):
            if not isinstance(spot[field], str) or not spot[field]:
                raise IngestError(f"Record {spot['id']} has an empty {field}.")
        for field in ("address", "neighborhood", "university"):
            if spot[field] is not None and not str(spot[field]).strip():
                raise IngestError(f"Record {spot['id']} has a blank {field}; it should be null.")


def write_snapshot(path: Path, spots: list[dict[str, Any]]) -> None:
    # ensure_ascii=False keeps "García" readable in the diff; the loader and the
    # API are UTF-8 throughout.
    path.write_text(json.dumps(spots, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize NYC Open Data into the study-spot snapshot."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Where to write the snapshot (default: %(default)s).",
    )
    parser.add_argument(
        "--fixtures",
        type=Path,
        nargs="?",
        const=DEFAULT_FIXTURES,
        default=None,
        help=(
            "Read the committed upstream sample from this directory instead of the network "
            f"(default when the flag is given: {DEFAULT_FIXTURES})."
        ),
    )
    options = parser.parse_args(argv)

    try:
        facilities, neighborhoods = read_sources(options.fixtures)
        spots = normalize(facilities, neighborhood_names(neighborhoods))
    except IngestError as error:
        warn(str(error))
        return 1

    write_snapshot(options.output, spots)
    counts = Counter(spot["category"] for spot in spots)
    summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    print(f"wrote {len(spots)} spots ({summary}) to {options.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
