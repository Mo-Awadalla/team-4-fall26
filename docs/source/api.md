# HTTP API

The API is available directly at `http://localhost:7501` and through the frontend proxy under `http://localhost:7500/api`. Deployments publish it under `/api`, and both edges strip that prefix before the request reaches the application, so the routes below are the same everywhere.

No route has a trailing slash, and the application does not redirect one onto the other: `/spots/` is a 404 rather than a 301 to `/spots`.

## Implemented routes

| Route | Purpose |
|---|---|
| `GET /health/live` | Reports whether the API process can serve requests. It intentionally does not contact Postgres or Meilisearch. |
| `GET /spots` | Returns a filtered, paginated page of study spots. |
| `GET /spots/{id}` | Returns one study spot. |

`GET /health/live` returns:

```json
{
  "status": "ok"
}
```

## Study-spot summary

```json
{
  "id": "facdb:eec118768e15a5e03d3354abda7b00da",
  "name": "125th Street Library",
  "category": "library",
  "address": "224 East 125 Street, New York, NY 10035",
  "neighborhood": "East Harlem (North)",
  "borough": "Manhattan",
  "latitude": 40.803027,
  "longitude": -73.934853,
  "university": "Touro University - Harlem"
}
```

The records represent public third places from NYC Open Data — today the libraries and campuses of the city's facilities database. They are candidate gathering and study locations; the API must not imply that unverified amenities are available. This response shape belongs to the shared contract. Changes require review from frontend, API, data, and search owners.

`category` currently takes one of `library`, `academic_library`, `university`, or `university_building`. `university_building` is a campus building a student can work in; the city's facilities database registers institutions and administrative points rather than buildings, so these come from the curated list in `data/nyu_buildings.json` and all carry the `nyu:` identifier prefix. `cafe` is part of the published vocabulary and has no source yet: see [Data and search](data-and-search.md). The API does not constrain the value: the vocabulary belongs to the importer, and pinning it in the serving schema would put every category change through a migration. `borough` is one of the five borough names and the database refuses any other. `neighborhood` is the 2020 Neighborhood Tabulation Area name and is `null` when NYC Open Data does not place the record in one.

```{important}
`university` is an addition to the previously agreed contract and still needs owner sign-off. It is proximity and nothing else: it names the closest campus within 500 metres, or the campus itself for a campus record, and is `null` when no campus is that close. The campus list is curated — the college and university records of the city's facilities database — and the field is never guessed from a spot's name, its operator, or anything else. It is not an affiliation, an endorsement, or an access claim: a named campus does not mean the institution is connected to the spot or that the public may use the room. In the example above, 169 metres separate a public library branch from a campus with no relationship to it.
```

## Listing study spots

`GET /spots` returns one page of spots inside a stable envelope:

```json
{
  "items": [],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "count": 0,
    "total": 1900,
    "has_more": false
  }
}
```

`total` counts every spot matching the filters, ignoring the page window. `count` is the number of items on this page, and `has_more` is true when `offset + count < total`.

Results are ordered by name, then by identifier. Because the identifier is unique, that sort key is total, so paging over an unchanged dataset never repeats or skips a spot. What the contract promises is that the order does not move between requests, not the exact sequence: where in the alphabet punctuation and digits fall is the database collation's business.

### Query parameters

| Parameter | Type | Default | Behavior |
|---|---|---|---|
| `name` | string | — | Case-insensitive substring match. `%` and `_` are matched literally. |
| `neighborhood` | string | — | Case-insensitive exact match. |
| `borough` | string | — | Case-insensitive exact match on one of the five borough names. |
| `university` | string | — | Case-insensitive exact match. Spots with no curated campus affiliation are excluded. |
| `limit` | integer | `20` | Page size, between 1 and 100. |
| `offset` | integer | `0` | Rows to skip before the page starts. |

Filters combine with AND. Text filters are trimmed, must not be blank, and are limited to 120 characters. A `borough` value is also normalized for internal spacing, so `?borough=brooklyn` and `?borough=  Staten   Island ` both resolve.

Case-insensitivity covers the whole of Unicode, not only ASCII, so `?name=café` and `?name=CAFÉ` return the same spots. Folding is the database's, applied identically to the stored value and the filter value, and every environment runs a UTF-8 cluster; the one place it is less aggressive than the previous implementation is `ß`, which Postgres does not fold to `ss`, so "strasse" does not match "Straße". See [Why no column declares a collation](database.md#why-no-column-declares-a-collation).

Unknown query parameters are rejected rather than ignored, so a misspelled filter fails loudly instead of silently returning unfiltered results:

```shell
curl --fail 'http://localhost:7501/spots?borough=Brooklyn&name=library&limit=5'
```

## Errors

Every non-2xx response uses one envelope:

```json
{
  "error": {
    "code": "validation_error",
    "message": "The request could not be validated.",
    "details": [
      {
        "field": "query.limit",
        "message": "Ensure this value is less than or equal to 100.",
        "type": "max_value"
      }
    ]
  }
}
```

`code` is stable and machine-readable; `message` is for people. `details` lists one entry per offending input and is empty when no single input is at fault.

| Status | `code` | Raised when |
|---|---|---|
| 404 | `not_found` | No spot has the requested identifier. |
| 405 | `method_not_allowed` | The route exists but the method does not. |
| 422 | `validation_error` | A parameter is missing, malformed, out of range, or unrecognized. |
| 500 | `internal_error` | An unhandled failure. The cause is logged, never returned. |
| 503 | `database_unavailable` | Postgres could not answer the query, or has never been migrated. |

## Searching

`GET /spots/search?q=` ranks spots instead of filtering them, in the same
envelope `GET /spots` returns. It takes `q`, `limit` and `offset`, rejects any
other parameter, and orders results by relevance rather than by name.

The difference matters at the search box. `GET /spots` answers "does this
match": `?name=libary` returns nothing, and so does `?name=NYPL`. `search`
answers "which of these is closest", so both find what the person meant.

Scoring is a few rules rather than one opaque number. An exact name scores
highest, then a prefix, then a substring, then an exact neighborhood. Below
those, Postgres trigram similarity compares the query against the best-matching
run of words in the name, which is what tolerates a misspelling and what lets a
fragment of a long title match -- `bobst` finds *Elmer Holmes Bobst Library*. A
neighborhood match scores lower than a name match, so a place *called*
Greenpoint outranks a place *in* Greenpoint.

Results below a relevance of 0.45 are dropped, so an unrelated query returns
nothing rather than everything in an arbitrary order. That figure was measured
rather than chosen: a one-character typo in a seven-letter word scores 0.5, and
unrelated words sit near 0.33.

An initialism is expanded before the query reaches Postgres, because no fuzzy
algorithm connects `NYPL` to `New York Public Library` -- they share almost no
trigrams. The list is in `spots/search.py` and expands only when the whole query
is an initialism.

The relevance score is not in the response. It exists to order results, and
publishing it would be a number the contract has to keep stable for no one's
benefit.

## Planned routes

- `GET /health/ready`

The readiness route will report required dependency failures.
