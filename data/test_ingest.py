"""Tests for the NYC Open Data importer.

These run against ``fixtures/``, a trimmed copy of what the two Socrata
datasets actually return, so the suite never depends on NYC Open Data being up
and CI needs no network. The fixture keeps the awkward records the backend's own
fixtures warn about -- an accented name, a name carrying SQL ``LIKE`` wildcards,
a branch with no address, an older extract with no 2020 NTA column, a facility
type the importer excludes on purpose -- because those are the records a mapping
quietly gets wrong.

What matters here is that the snapshot the importer writes is one the loader
accepts and the API can serve: nine fields, five boroughs, nulls rather than
blanks, and identifiers that do not move when upstream edits a name.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import ingest
import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: The example record published in docs/source/api.md. The importer has to
#: reproduce it exactly: it is what the frontend, the API and the search index
#: were written against.
PUBLISHED_EXAMPLE = {
    "id": "facdb:eec118768e15a5e03d3354abda7b00da",
    "name": "125th Street Library",
    "category": "library",
    "address": "224 East 125 Street, New York, NY 10035",
    "neighborhood": "East Harlem (North)",
    "borough": "Manhattan",
    "latitude": 40.803027,
    "longitude": -73.934853,
    "university": "Touro University - Harlem",
}

CATEGORIES = {"library", "academic_library", "university", "cafe"}
BOROUGHS = {"Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"}


@pytest.fixture(scope="module")
def facilities() -> list[dict[str, Any]]:
    return ingest.fixture_rows(FIXTURES, "facilities")


@pytest.fixture(scope="module")
def names() -> dict[str, str]:
    return ingest.neighborhood_names(ingest.fixture_rows(FIXTURES, "neighborhoods"))


@pytest.fixture(scope="module")
def spots(facilities: list[dict[str, Any]], names: dict[str, str]) -> list[dict[str, Any]]:
    return ingest.normalize(facilities, names)


def upstream(facilities: list[dict[str, Any]], facname: str) -> dict[str, Any]:
    """One raw record, copied so a test can edit it without affecting others."""
    return dict(next(record for record in facilities if record["facname"] == facname))


def published(spots: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(spot for spot in spots if spot["name"] == name)


class TestPublishedExample:
    def test_is_reproduced_field_for_field(self, spots: list[dict[str, Any]]) -> None:
        spot = next(spot for spot in spots if spot["id"] == PUBLISHED_EXAMPLE["id"])
        assert spot == PUBLISHED_EXAMPLE


class TestIdentifiers:
    def test_carry_the_source_prefix_and_the_upstream_key(
        self, facilities: list[dict[str, Any]], spots: list[dict[str, Any]]
    ) -> None:
        for spot in spots:
            prefix, _, digest = spot["id"].partition(":")
            assert prefix == "facdb"
            assert digest in {record["uid"] for record in facilities}

    def test_survive_an_upstream_edit_to_the_record(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        # The loader replaces the table wholesale, so an identifier derived from
        # a record's contents would delete and recreate every row the city
        # corrected a typo in.
        record = upstream(facilities, "125TH STREET LIBRARY")
        edited = {
            **record,
            "facname": "125TH STREET BRANCH LIBRARY",
            "address": "224 E 125 STREET",
            "latitude": "40.8030269999",
        }
        assert ingest.normalize([edited], names)[0]["id"] == PUBLISHED_EXAMPLE["id"]

    def test_a_repeated_upstream_key_is_an_error(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        record = upstream(facilities, "125TH STREET LIBRARY")
        with pytest.raises(ingest.IngestError, match="Duplicate identifier"):
            ingest.normalize([record, {**record, "facname": "SOMEWHERE ELSE"}], names)

    def test_a_record_without_an_upstream_key_is_an_error(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        record = upstream(facilities, "125TH STREET LIBRARY")
        del record["uid"]
        with pytest.raises(ingest.IngestError, match="no uid"):
            ingest.normalize([record], names)


class TestCategories:
    @pytest.mark.parametrize(
        ("facname", "expected"),
        [
            ("125TH STREET LIBRARY", "library"),
            ("THE GROLIER CLUB OF NEW YORK", "library"),
            ("COLUMBIA UNIVERSITY BUTLER LIBRARY", "academic_library"),
            ("COLUMBIA UNIVERSITY", "university"),
        ],
    )
    def test_upstream_types_map_onto_the_published_vocabulary(
        self, facilities: list[dict[str, Any]], facname: str, expected: str
    ) -> None:
        assert ingest.category(upstream(facilities, facname)) == expected

    def test_every_published_category_is_in_the_vocabulary(
        self, spots: list[dict[str, Any]]
    ) -> None:
        assert {spot["category"] for spot in spots} <= CATEGORIES

    def test_a_residence_is_excluded_rather_than_published(
        self, spots: list[dict[str, Any]]
    ) -> None:
        # People live there. The fixture carries CUNY's chancellor's residence
        # because FacDB files it under higher education.
        assert ingest.category({"uid": "x", "factype": "UNIVERSITY RESIDENTIAL STRUCTURE"}) is None
        assert not [spot for spot in spots if "Residence" in spot["name"]]

    def test_an_unmapped_type_fails_loudly(self, facilities: list[dict[str, Any]]) -> None:
        # Mapping it to the nearest existing category would publish a guess and
        # hide the fact that FacDB changed.
        record = {**upstream(facilities, "125TH STREET LIBRARY"), "factype": "COWORKING SPACE"}
        with pytest.raises(ingest.IngestError, match="COWORKING SPACE"):
            ingest.category(record)


class TestBoroughs:
    def test_are_the_five_exact_names(self, spots: list[dict[str, Any]]) -> None:
        assert {spot["borough"] for spot in spots} == BOROUGHS

    def test_a_sixth_borough_is_an_error(self, facilities: list[dict[str, Any]]) -> None:
        record = {**upstream(facilities, "125TH STREET LIBRARY"), "boro": "YONKERS"}
        with pytest.raises(ingest.IngestError, match="not one of the five boroughs"):
            ingest.borough(record)


class TestAbsentValues:
    def test_a_branch_without_an_address_publishes_null(self, spots: list[dict[str, Any]]) -> None:
        # FacDB has no street address for this branch. A city and a zip code are
        # not an address, so the field is null rather than ", Brooklyn, NY".
        assert published(spots, "Cypress Hills Library")["address"] is None

    def test_an_older_extract_without_the_nta_column_publishes_null(
        self, spots: list[dict[str, Any]]
    ) -> None:
        assert published(spots, "Great Kills Library")["neighborhood"] is None

    def test_nothing_is_published_as_a_blank_string(self, spots: list[dict[str, Any]]) -> None:
        # The contract distinguishes null from blank and the API returns null,
        # so an empty string would assert that the source supplied one.
        for spot in spots:
            for field in ("address", "neighborhood", "university"):
                assert spot[field] is None or spot[field].strip() == spot[field] != ""

    def test_a_record_without_coordinates_is_skipped(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        record = {**upstream(facilities, "125TH STREET LIBRARY"), "latitude": "", "longitude": ""}
        assert ingest.normalize([record], names) == []

    def test_a_non_numeric_coordinate_is_an_error(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        record = {**upstream(facilities, "125TH STREET LIBRARY"), "latitude": "uptown"}
        with pytest.raises(ingest.IngestError, match="non-numeric latitude"):
            ingest.normalize([record], names)


class TestNeighborhoods:
    def test_are_2020_nta_names(self, spots: list[dict[str, Any]]) -> None:
        assert published(spots, "125th Street Library")["neighborhood"] == "East Harlem (North)"
        assert published(spots, "Columbia University")["neighborhood"] == "Morningside Heights"

    def test_a_code_the_boundary_file_does_not_know_publishes_null(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        # The two datasets are revised separately. Publishing "MN9999" would put
        # a code where the contract promises a name.
        record = {**upstream(facilities, "125TH STREET LIBRARY"), "nta2020": "MN9999"}
        assert ingest.normalize([record], names)[0]["neighborhood"] is None


class TestUniversityIsProximity:
    def test_a_campus_record_names_itself(self, spots: list[dict[str, Any]]) -> None:
        assert published(spots, "Columbia University")["university"] == "Columbia University"

    def test_a_spot_inside_the_radius_names_the_closest_campus(
        self, spots: list[dict[str, Any]]
    ) -> None:
        assert published(spots, "Columbia University Butler Library")["university"] == (
            "Columbia University"
        )

    def test_a_spot_with_no_campus_nearby_publishes_null(self, spots: list[dict[str, Any]]) -> None:
        assert published(spots, "The Grolier Club of New York")["university"] is None

    def test_a_name_that_mentions_a_university_is_not_enough(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        # Affiliation is never inferred from a name, an operator, or anything
        # else: only the curated campus list and a distance.
        far = {
            **upstream(facilities, "GREAT KILLS LIBRARY"),
            "facname": "COLUMBIA UNIVERSITY READING ROOM",
        }
        campus = upstream(facilities, "COLUMBIA UNIVERSITY")
        published_spots = ingest.normalize([far, campus], names)
        assert published(published_spots, "Columbia University Reading Room")["university"] is None

    def test_the_radius_is_500_metres(self) -> None:
        campus = ingest.Campus("Somewhere College", 40.8, -73.95)
        # Roughly 330 m and 670 m north of the campus.
        assert ingest.nearest_campus(40.803, -73.95, [campus]) == "Somewhere College"
        assert ingest.nearest_campus(40.806, -73.95, [campus]) is None

    def test_the_closest_of_several_campuses_wins(self) -> None:
        near = ingest.Campus("Near College", 40.8005, -73.95)
        far = ingest.Campus("Far College", 40.803, -73.95)
        assert ingest.nearest_campus(40.8, -73.95, [far, near]) == "Near College"

    def test_the_documented_distance_holds(self, facilities: list[dict[str, Any]]) -> None:
        library = upstream(facilities, "125TH STREET LIBRARY")
        campus = upstream(facilities, "TOURO UNIVERSITY - HARLEM")
        metres = ingest.haversine_metres(
            float(library["latitude"]),
            float(library["longitude"]),
            float(campus["latitude"]),
            float(campus["longitude"]),
        )
        assert 160 < metres < 180


class TestNames:
    @pytest.mark.parametrize(
        ("shouted", "expected"),
        [
            ("125TH STREET LIBRARY", "125th Street Library"),
            ("ST JOHN'S UNIVERSITY LIBRARY", "St John's University Library"),
            ("CUNY HUNTER COLLEGE", "CUNY Hunter College"),
            ("CUNY'S CHANCELLORS RESIDENCE", "CUNY's Chancellors Residence"),
            ("LIBRARY FOR ARTS & CULTURE", "Library for Arts & Culture"),
            ("JUILLIARD SCHOOL (THE)", "Juilliard School (The)"),
            ("AMERICAN ACAD MCALLISTER INST", "American Acad McAllister Inst"),
            ("FORDHAM UNIV (ROSE HILL-LINCOLN CTR)", "Fordham Univ (Rose Hill-Lincoln Ctr)"),
            ("NY COL OF PODIATRIC MEDICINE", "NY Col of Podiatric Medicine"),
            # FacDB truncates long names mid-word and writes middle initials
            # without one, so neither trailing "A" is an article.
            ("NEW YORK CONSERVATORY FOR DRAMATIC A", "New York Conservatory for Dramatic A"),
            ("STEPHEN A. SCHWARZMAN BUILDING", "Stephen A. Schwarzman Building"),
        ],
    )
    def test_shouted_upstream_names_become_readable(self, shouted: str, expected: str) -> None:
        assert ingest.title_case(shouted) == expected

    def test_accents_survive(self, spots: list[dict[str, Any]]) -> None:
        # The API folds case across the whole of Unicode, so "garcía" has to
        # match what is stored. Mangling the accent here would break that.
        assert published(spots, "Biblioteca Yolanda García")
        assert ingest.title_case("YOLANDA GARCÍA PARK") == "Yolanda García Park"

    def test_sql_wildcards_are_left_alone(self, spots: list[dict[str, Any]]) -> None:
        # `?name=` matches `%` and `_` literally, so the importer must not
        # rewrite or escape them -- the API's filter is what handles them.
        spot = published(spots, "100% Coffee Reading Room")
        assert "%" in spot["name"]
        assert ingest.title_case("100% COFFEE_HOUSE") == "100% Coffee_house"

    def test_punctuation_between_words_is_kept(self, spots: list[dict[str, Any]]) -> None:
        assert published(spots, "Inwood Library–Joseph and Sheila Rosenblatt Building")


class TestSnapshot:
    def test_every_record_is_exactly_the_contract(self, spots: list[dict[str, Any]]) -> None:
        for spot in spots:
            assert tuple(spot) == ingest.CONTRACT_FIELDS

    def test_coordinates_are_rounded_to_six_places(self, spots: list[dict[str, Any]]) -> None:
        for spot in spots:
            assert spot["latitude"] == round(spot["latitude"], 6)
            assert spot["longitude"] == round(spot["longitude"], 6)
            assert -90 <= spot["latitude"] <= 90
            assert -180 <= spot["longitude"] <= 180

    def test_the_order_does_not_depend_on_the_upstream_order(
        self, facilities: list[dict[str, Any]], names: dict[str, str]
    ) -> None:
        # Socrata pages in whatever order it likes, and a reordered snapshot is
        # a diff of every line.
        assert ingest.normalize(list(reversed(facilities)), names) == ingest.normalize(
            facilities, names
        )

    def test_rerunning_writes_the_same_bytes(
        self, facilities: list[dict[str, Any]], names: dict[str, str], tmp_path: Path
    ) -> None:
        first, second = tmp_path / "first.json", tmp_path / "second.json"
        for path in (first, second):
            ingest.write_snapshot(path, ingest.normalize(facilities, names))
        assert first.read_bytes() == second.read_bytes()

    def test_a_record_outside_the_contract_is_an_error(self) -> None:
        with pytest.raises(ingest.IngestError, match="does not match the shared contract"):
            ingest.validate([{**PUBLISHED_EXAMPLE, "wifi": True}])


class TestCommandLine:
    def test_the_fixture_run_needs_no_network(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("the fixture run reached the network")

        monkeypatch.setattr(ingest.urllib.request, "urlopen", refuse)
        output = tmp_path / "spots.json"
        assert ingest.main(["--fixtures", str(FIXTURES), "--output", str(output)]) == 0
        assert len(json.loads(output.read_text("utf-8"))) == 11

    def test_a_missing_fixture_directory_is_reported_not_raised(self, tmp_path: Path) -> None:
        assert ingest.main(["--fixtures", str(tmp_path / "absent")]) == 1


@pytest.fixture(scope="module")
def snapshot() -> list[dict[str, Any]]:
    return json.loads((Path(__file__).resolve().parent / "spots.json").read_text("utf-8"))


class TestCommittedSnapshot:
    """The snapshot in version control, which is what deployments load."""

    def test_holds_real_records(self, snapshot: list[dict[str, Any]]) -> None:
        assert len(snapshot) > 100

    def test_matches_the_contract_the_loader_enforces(self, snapshot: list[dict[str, Any]]) -> None:
        ingest.validate(snapshot)
        assert {spot["borough"] for spot in snapshot} <= BOROUGHS
        assert {spot["category"] for spot in snapshot} <= CATEGORIES

    def test_is_sorted_and_unique_by_identifier(self, snapshot: list[dict[str, Any]]) -> None:
        identifiers = [spot["id"] for spot in snapshot]
        assert identifiers == sorted(identifiers)
        assert len(set(identifiers)) == len(identifiers)
