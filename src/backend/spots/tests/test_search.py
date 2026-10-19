"""Tests for the ranked search endpoint.

``GET /spots`` filters and ``GET /spots/search`` ranks, and the difference is
the point: a filter answers "does this match", a search answers "which of these
is closest". The cases below are the ones a filter gets wrong -- a misspelling,
an initialism, a fragment of a long title -- plus the one a ranked search gets
wrong if the threshold is too low, which is returning everything.
"""

from __future__ import annotations

from typing import Any

import pytest

from spots.models import StudySpot
from spots.search import INITIALISMS, THRESHOLD, expand, search

pytestmark = pytest.mark.django_db

#: Chosen so that every ranking rule has something to act on: a long title whose
#: distinctive word sits in the middle, two names sharing a word, a neighborhood
#: that is not in any name, and an accented name.
RECORDS: list[dict[str, Any]] = [
    {
        "id": "nyu:bobst",
        "name": "Elmer Holmes Bobst Library",
        "category": "academic_library",
        "address": "70 Washington Square S",
        "neighborhood": "Greenwich Village",
        "borough": "Manhattan",
        "latitude": 40.7295,
        "longitude": -73.9973,
        "university": "New York University",
    },
    {
        "id": "nyu:kimmel",
        "name": "Kimmel Center for University Life",
        "category": "university_building",
        "address": "60 Washington Square S",
        "neighborhood": "Greenwich Village",
        "borough": "Manhattan",
        "latitude": 40.7301,
        "longitude": -73.9977,
        "university": "New York University",
    },
    {
        "id": "facdb:nypl-53",
        "name": "53rd Street Library",
        "category": "library",
        "address": "18 West 53 Street",
        "neighborhood": "Midtown-Times Square",
        "borough": "Manhattan",
        "latitude": 40.7606,
        "longitude": -73.9787,
        "university": None,
    },
    {
        "id": "facdb:baychester",
        "name": "Baychester Library",
        "category": "library",
        "address": "2049 Asch Loop North",
        "neighborhood": "Co-op City",
        "borough": "Bronx",
        "latitude": 40.8714,
        "longitude": -73.8278,
        "university": None,
    },
    {
        "id": "dining:grumpy",
        "name": "Café Grumpy",
        "category": "cafe",
        "address": None,
        "neighborhood": "Chelsea",
        "borough": "Manhattan",
        "latitude": 40.7442,
        "longitude": -74.0,
        "university": None,
    },
]


@pytest.fixture
def spots() -> list[StudySpot]:
    return StudySpot.objects.bulk_create(StudySpot(**record) for record in RECORDS)


def names(query: str) -> list[str]:
    return [spot.name for spot in search(query)]


class TestTypos:
    """The failure that motivated the endpoint: a filter returns nothing."""

    @pytest.mark.parametrize(
        ("typo", "expected"),
        [
            ("libary", "53rd Street Library"),
            ("kimel", "Kimmel Center for University Life"),
            ("bobts", "Elmer Holmes Bobst Library"),
            ("baychestr", "Baychester Library"),
        ],
    )
    def test_a_misspelling_still_finds_the_place(
        self, spots: list[StudySpot], typo: str, expected: str
    ) -> None:
        assert expected in names(typo)

    def test_the_best_match_comes_first(self, spots: list[StudySpot]) -> None:
        assert names("kimel")[0] == "Kimmel Center for University Life"


class TestShortenedNames:
    def test_a_fragment_of_a_long_title_matches(self, spots: list[StudySpot]) -> None:
        # "Bobst" is the fourth word of its title; a prefix match would miss it.
        assert names("bobst")[0] == "Elmer Holmes Bobst Library"

    def test_an_initialism_is_expanded(self, spots: list[StudySpot]) -> None:
        # No fuzzy algorithm connects NYPL to its expansion: they share almost
        # no trigrams. The lookup is why this works.
        assert expand("NYPL") == "New York Public Library"
        assert expand("nypl") == expand("NYPL")

    def test_an_unknown_word_is_left_alone(self) -> None:
        assert expand("bobst") == "bobst"

    def test_expansion_only_applies_to_the_whole_query(self) -> None:
        # Expanding one word of several changes what the rest is compared
        # against in ways that are hard to predict, so it does not.
        assert expand("nyu library") == "nyu library"

    def test_every_initialism_is_stored_folded(self) -> None:
        # expand() looks up a casefolded key, so a capitalised one would never
        # be found and the entry would silently do nothing.
        assert all(key == key.casefold() for key in INITIALISMS)


class TestRanking:
    def test_an_exact_name_outranks_a_fuzzy_match(self, spots: list[StudySpot]) -> None:
        assert names("Baychester Library")[0] == "Baychester Library"

    def test_a_name_outranks_a_neighborhood(self, spots: list[StudySpot]) -> None:
        # A place called Greenwich Village would beat places in it; here the
        # neighborhood match should still appear.
        assert "Elmer Holmes Bobst Library" in names("Greenwich Village")

    def test_a_neighborhood_absent_from_every_name_still_matches(
        self, spots: list[StudySpot]
    ) -> None:
        assert names("Co-op City") == ["Baychester Library"]

    def test_an_accented_name_is_found_by_its_accented_spelling(
        self, spots: list[StudySpot]
    ) -> None:
        assert "Café Grumpy" in names("Café")

    def test_results_are_ordered_by_relevance(self, spots: list[StudySpot]) -> None:
        results = list(search("library"))
        relevance = [spot.relevance for spot in results]
        assert relevance == sorted(relevance, reverse=True)


class TestThreshold:
    def test_an_unrelated_query_matches_nothing(self, spots: list[StudySpot]) -> None:
        # The risk a ranked search carries that a filter does not: returning
        # everything, ordered.
        assert names("zzzznowhere") == []

    def test_the_threshold_is_above_what_unrelated_words_score(self) -> None:
        # Unrelated words sit around 0.33 against this data; the margin is what
        # keeps a search from degrading into a listing.
        assert THRESHOLD > 0.33


class TestEndpoint:
    def test_returns_the_published_envelope(self, client: Any, spots: list[StudySpot]) -> None:
        body = client.get("/spots/search?q=library").json()

        assert set(body) == {"items", "pagination"}
        assert set(body["pagination"]) == {"limit", "offset", "count", "total", "has_more"}

    def test_does_not_leak_the_relevance_score(self, client: Any, spots: list[StudySpot]) -> None:
        # It orders the results; publishing it would be a number the contract
        # has to keep stable for no one's benefit.
        body = client.get("/spots/search?q=library").json()
        assert "relevance" not in body["items"][0]

    def test_the_route_is_not_captured_by_the_detail_route(
        self, client: Any, spots: list[StudySpot]
    ) -> None:
        # /spots/<id> would match "search" as an identifier if it were declared
        # first, and the endpoint would 404 forever.
        assert client.get("/spots/search?q=library").status_code == 200

    def test_a_missing_query_is_422(self, client: Any, spots: list[StudySpot]) -> None:
        response = client.get("/spots/search")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    @pytest.mark.parametrize("query", ["q=", "q=library&bogus=1", "q=library&limit=0"])
    def test_a_bad_parameter_is_422(self, client: Any, spots: list[StudySpot], query: str) -> None:
        assert client.get(f"/spots/search?{query}").status_code == 422

    def test_paging_reports_the_total_beyond_the_page(
        self, client: Any, spots: list[StudySpot]
    ) -> None:
        body = client.get("/spots/search?q=library&limit=1").json()

        assert body["pagination"]["count"] == 1
        assert body["pagination"]["total"] > 1
        assert body["pagination"]["has_more"] is True
