"""Tests for the subway station list.

The list exists so a detail page can say which trains are near a spot. What
matters is that a station appears once with all of its lines, that the
accessibility value is the MTA's own rather than a rounding of it, and that the
file is stable enough for a diff to mean something.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import subway

#: Two rows of one complex, as the MTA publishes them: W 4 St-Wash Sq arrives
#: once per line, at identical coordinates.
W4_ROWS: list[dict[str, Any]] = [
    {
        "complex_id": "167",
        "stop_name": "W 4 St-Wash Sq",
        "daytime_routes": "A C E",
        "gtfs_latitude": "40.732338",
        "gtfs_longitude": "-74.000495",
        "ada": "1",
    },
    {
        "complex_id": "167",
        "stop_name": "W 4 St-Wash Sq",
        "daytime_routes": "B D F M",
        "gtfs_latitude": "40.732338",
        "gtfs_longitude": "-74.000495",
        "ada": "1",
    },
]


@pytest.fixture(scope="module")
def stations() -> list[dict[str, Any]]:
    """The committed list, as the frontend build reads it."""
    path = Path(__file__).resolve().parent / "subway_stations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def station(rows: list[dict[str, Any]], name: str) -> dict[str, Any]:
    return next(s for s in subway.normalize(rows) if s["name"] == name)


class TestMergingAComplex:
    def test_one_station_rather_than_one_per_line(self) -> None:
        assert len(subway.normalize(W4_ROWS)) == 1

    def test_it_carries_every_line(self) -> None:
        # Unmerged, a page would show half the trains at the station.
        assert station(W4_ROWS, "W 4 St-Wash Sq")["routes"] == [
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "M",
        ]

    def test_numbered_lines_come_before_lettered_ones(self) -> None:
        rows = [{**W4_ROWS[0], "daytime_routes": "Q 7 A 2"}]
        assert station(rows, "W 4 St-Wash Sq")["routes"] == ["2", "7", "A", "Q"]

    def test_the_name_on_the_most_lines_wins(self) -> None:
        # Times Sq-42 St and 42 St-Port Authority Bus Terminal are one complex.
        rows = [
            {**W4_ROWS[0], "stop_name": "42 St-Port Authority Bus Terminal", "daytime_routes": "A"},
            {**W4_ROWS[1], "stop_name": "Times Sq-42 St", "daytime_routes": "1 2 3 7"},
        ]
        assert station(rows, "Times Sq-42 St")["routes"] == ["1", "2", "3", "7", "A"]

    def test_the_result_does_not_depend_on_upstream_order(self) -> None:
        assert subway.normalize(W4_ROWS) == subway.normalize(list(reversed(W4_ROWS)))


class TestAccessibility:
    @pytest.mark.parametrize(
        ("ada", "expected"),
        [("0", "none"), ("1", "full"), ("2", "partial")],
    )
    def test_the_three_states_are_kept_apart(self, ada: str, expected: str) -> None:
        # 2 is one direction only, which is worth saying rather than rounding
        # to either of the others.
        rows = [{**W4_ROWS[0], "ada": ada}]
        assert station(rows, "W 4 St-Wash Sq")["step_free"] == expected

    def test_a_complex_reports_its_best_platform(self) -> None:
        # One step-free platform is what a person needs to know, and which line
        # they want is not ours to guess.
        rows = [{**W4_ROWS[0], "ada": "0"}, {**W4_ROWS[1], "ada": "1"}]
        assert station(rows, "W 4 St-Wash Sq")["step_free"] == "full"

    def test_an_unknown_value_is_not_claimed_as_access(self) -> None:
        rows = [{**W4_ROWS[0], "ada": "NaN"}]
        assert station(rows, "W 4 St-Wash Sq")["step_free"] == "none"


class TestRefusingBadInput:
    @pytest.mark.parametrize("field", ["stop_name", "daytime_routes", "gtfs_latitude"])
    def test_a_missing_field_fails_rather_than_publishes(self, field: str) -> None:
        rows = [{**W4_ROWS[0], field: None}]
        with pytest.raises(subway.SubwayError):
            subway.normalize(rows)

    def test_an_empty_list_fails(self) -> None:
        with pytest.raises(subway.SubwayError):
            subway.normalize([])

    def test_a_row_that_is_not_an_object_fails(self) -> None:
        with pytest.raises(subway.SubwayError):
            subway.normalize(["not a station"])


class TestCommittedList:
    def test_covers_the_system(self, stations: list[dict[str, Any]]) -> None:
        assert len(stations) > 400

    def test_every_station_is_in_the_city(self, stations: list[dict[str, Any]]) -> None:
        south, north, west, east = 40.47, 40.93, -74.30, -73.68
        for s in stations:
            assert south <= s["latitude"] <= north, s["name"]
            assert west <= s["longitude"] <= east, s["name"]

    def test_every_station_has_at_least_one_line(self, stations: list[dict[str, Any]]) -> None:
        assert all(s["routes"] for s in stations)

    def test_no_station_is_listed_twice(self, stations: list[dict[str, Any]]) -> None:
        keyed = [(s["name"], tuple(s["routes"])) for s in stations]
        assert len(set(keyed)) == len(keyed)
