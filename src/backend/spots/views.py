"""Public study-spot routes."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, QuerySet
from rest_framework.exceptions import NotFound
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import StudySpot
from .search import search
from .serializers import (
    SpotQuerySerializer,
    SpotSearchQuerySerializer,
    StudySpotSerializer,
)

#: Maps a validated query parameter to the lookup it filters with. Substring for
#: the name, exact for the rest, all case-insensitive. A `university` or
#: `neighborhood` filter therefore excludes rows where the column is NULL, which
#: is the documented behaviour.
LOOKUPS = {
    "name": "name__icontains",
    "category": "category__iexact",
    "neighborhood": "neighborhood__iexact",
    "borough": "borough__iexact",
    "university": "university__iexact",
    "free_public_wifi": "free_public_wifi",
}


def apply_filters(queryset: QuerySet[StudySpot], parameters: dict[str, Any]) -> QuerySet[StudySpot]:
    """Narrow ``queryset`` by every filter the caller supplied.

    Django escapes the LIKE wildcards in an ``icontains`` value, so a search for
    ``100%`` is a search for a literal percent sign.
    """
    lookups = {
        lookup: parameters[parameter]
        for parameter, lookup in LOOKUPS.items()
        if parameters.get(parameter) is not None
    }
    return queryset.filter(**lookups) if lookups else queryset


class SpotListView(APIView):
    """``GET /spots`` -- a filtered, paginated page of study spots."""

    def get(self, request: Request) -> Response:
        query = SpotQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        parameters = query.validated_data

        limit: int = parameters["limit"]
        offset: int = parameters["offset"]

        matching = apply_filters(StudySpot.objects.all(), parameters)

        # Counted before slicing, because the envelope reports the size of the
        # whole result set rather than of this page.
        total = matching.count()
        items = StudySpotSerializer(matching[offset : offset + limit], many=True).data

        return Response(
            {
                "items": items,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(items),
                    "total": total,
                    "has_more": offset + len(items) < total,
                },
            }
        )


class SpotDetailView(APIView):
    """``GET /spots/{id}`` -- one study spot."""

    def get(self, request: Request, spot_id: str) -> Response:
        try:
            spot = StudySpot.objects.get(pk=spot_id)
        except StudySpot.DoesNotExist:
            raise NotFound(f"No study spot has the identifier {spot_id!r}.") from None
        return Response(StudySpotSerializer(spot).data)


class SpotSearchView(APIView):
    """``GET /spots/search`` -- study spots ranked by how well they match ``q``.

    The envelope is the one ``GET /spots`` uses, so a caller can swap between
    filtering and searching without handling two response shapes. The relevance
    score is not part of it: it exists to order the results and would be a
    number the contract has to keep stable for no one's benefit.
    """

    def get(self, request: Request) -> Response:
        query = SpotSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        parameters = query.validated_data

        limit: int = parameters["limit"]
        offset: int = parameters["offset"]

        # Filter first, then rank. The other order would drop the best
        # matches out of a page rather than out of the result set.
        matching = search(parameters["q"], apply_filters(StudySpot.objects.all(), parameters))

        total = matching.count()
        items = StudySpotSerializer(matching[offset : offset + limit], many=True).data

        return Response(
            {
                "items": items,
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "count": len(items),
                    "total": total,
                    "has_more": offset + len(items) < total,
                },
            }
        )


class SpotFacetsView(APIView):
    """``GET /spots/facets`` -- the values the filters can take, with counts.

    A filter control cannot be built from the contract alone: `borough` is five
    fixed names, but `category` belongs to the importer and the campuses are
    whatever the data happens to contain. Hard-coding either in the browser
    would mean a filter that silently stops matching when the snapshot changes.

    Counts come along because a filter offering a value that matches nothing is
    worse than not offering it.
    """

    def get(self, request: Request) -> Response:
        def facet(field: str) -> list[dict[str, Any]]:
            rows = (
                StudySpot.objects.exclude(**{f"{field}__isnull": True})
                .values(field)
                .annotate(count=Count("id"))
                .order_by("-count", field)
            )
            return [{"value": row[field], "count": row["count"]} for row in rows]

        return Response(
            {
                "boroughs": facet("borough"),
                "categories": facet("category"),
                "universities": facet("university"),
            }
        )
