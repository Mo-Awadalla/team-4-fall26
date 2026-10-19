"""Ranked study-spot search.

``GET /spots`` filters: a value either matches or it does not, and the order is
alphabetical. That is the right behaviour for a filter and the wrong one for a
search box, where "libary" and "kimel" are what people actually type and
returning nothing is indistinguishable from having no data.

This module ranks instead. Every candidate gets a score between 0 and 1, the
best are returned first, and anything below :data:`THRESHOLD` is dropped so a
query matches nothing rather than everything.

The scoring is deliberately a few understandable rules rather than one opaque
number:

- an exact name, a prefix, and a substring score highest, in that order,
  because someone who typed enough of the name to match it exactly meant it;
- trigram word similarity catches the misspellings, comparing the query against
  the best-matching run of words in the name rather than the whole string, so a
  short query is not penalised for a long title; and
- the same, lower, for neighborhood, so "Greenpoint" finds places in Greenpoint
  without outranking a place actually called Greenpoint.

Postgres does the work through ``pg_trgm``. A GIN index on the name makes the
similarity search an index scan; see the migration that creates it.
"""

from __future__ import annotations

from django.contrib.postgres.search import TrigramWordSimilarity
from django.db.models import Case, F, FloatField, QuerySet, Value, When
from django.db.models.functions import Coalesce, Greatest

from .models import StudySpot

#: Below this, a result is noise.
#:
#: Measured against the real snapshot rather than guessed. A one-character typo
#: in a seven-letter word scores 0.5 -- "libary" against "Library" -- and
#: unrelated words sit around 0.33, so the useful range is narrow. Anything from
#: 0.45 to 0.5 returns identical results on the queries that matter; 0.45 is the
#: low end of that band, so the common typo clears it with margin instead of
#: landing exactly on it. At 0.6 "libary" matches nothing at all, which is the
#: failure this whole module exists to prevent.
THRESHOLD = 0.45

#: Scores for the non-fuzzy rules, above anything trigram similarity returns so
#: that a literal match always outranks an approximate one.
EXACT = 1.0
PREFIX = 0.95
SUBSTRING = 0.9
NEIGHBORHOOD_EXACT = 0.85

#: Weight applied to fuzzy matches on the neighborhood, so that a place *called*
#: Greenpoint outranks a place *in* Greenpoint.
NEIGHBORHOOD_WEIGHT = 0.7

#: Initialisms nobody spells out, expanded before the query reaches Postgres.
#:
#: No fuzzy algorithm connects "NYPL" to "New York Public Library" -- they share
#: almost no trigrams -- so this is a lookup rather than something cleverer. It
#: expands only when the whole query is an initialism, because expanding one
#: word of several changes what the rest is compared against in ways that are
#: hard to predict.
INITIALISMS = {
    "nypl": "New York Public Library",
    "bpl": "Brooklyn Public Library",
    "qpl": "Queens Public Library",
    "nyu": "New York University",
    "cuny": "City University of New York",
    "suny": "State University of New York",
    "snfl": "Stavros Niarchos Foundation Library",
}


def expand(query: str) -> str:
    """Expand a query that is entirely a known initialism."""
    return INITIALISMS.get(query.strip().casefold(), query)


def score(query: str) -> Greatest:
    """Build the ranking expression for ``query``."""
    return Greatest(
        # Literal matches, strongest first. Case() stops at the first match, so
        # an exact name never also scores as a substring.
        Case(
            When(name__iexact=query, then=Value(EXACT)),
            When(name__istartswith=query, then=Value(PREFIX)),
            When(name__icontains=query, then=Value(SUBSTRING)),
            When(neighborhood__iexact=query, then=Value(NEIGHBORHOOD_EXACT)),
            default=Value(0.0),
            output_field=FloatField(),
        ),
        TrigramWordSimilarity(query, "name"),
        # Coalesce because neighborhood is null for some records and a null
        # here would otherwise propagate through the comparison.
        Coalesce(
            TrigramWordSimilarity(query, "neighborhood") * Value(NEIGHBORHOOD_WEIGHT),
            Value(0.0),
            output_field=FloatField(),
        ),
        output_field=FloatField(),
    )


def search(query: str, queryset: QuerySet[StudySpot] | None = None) -> QuerySet[StudySpot]:
    """Return spots matching ``query``, best first.

    ``queryset`` narrows the candidates before they are ranked, which is the
    order filtering and searching have to happen in: ranking first and filtering
    after would drop the best matches out of a page rather than out of the
    result set, and the count would describe something the caller never sees.

    Ties break on name then id, the same total ordering ``GET /spots`` uses, so
    that paging through results is stable when many share a score.
    """
    expanded = expand(query)
    base = StudySpot.objects.all() if queryset is None else queryset

    return (
        base.annotate(relevance=score(expanded))
        .filter(relevance__gte=THRESHOLD)
        .order_by(F("relevance").desc(), "name", "id")
    )


__all__ = ["INITIALISMS", "THRESHOLD", "expand", "score", "search"]
