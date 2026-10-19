# Data and search

StudySpot has one small data boundary:

```text
NYC Open Data -> data/ingest.py -> data/spots.json -> Postgres -> API
                                                   \-> search index
```

The snapshot holds the public, academic, and institutional libraries and the college and university campuses of the five boroughs — 380 public third places where students might meet or study. These are candidate locations, not guarantees of Wi-Fi, outlets, seating, quietness, or availability.

The directory intentionally stays small:

- `README.md` documents the boundary, including where the records come from and what each field means.
- `ingest.py` downloads, normalizes, and validates.
- `spots.json` is the canonical generated dataset.
- `test_ingest.py` tests the mapping.
- `fixtures/` is a trimmed copy of what the upstream datasets return, so the tests and `ingest.py --fixtures` need no network.

Records come from the city's [Facilities Database](https://data.cityofnewyork.us/City-Government/Facilities-Database/ji82-xba5) (FacDB, Socrata `ji82-xba5`), which is what the `facdb:` identifier prefix refers to, with neighborhood names from the [2020 Neighborhood Tabulation Areas](https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd) (`9nt8-h7nd`). FacDB lists no cafés, so the published `cafe` category has no source yet; the health department's restaurant inspection results are an inspection log rather than a directory of open businesses, and publishing them as study spots would assert more than the data supports. Regenerate the snapshot with `just ingest` and load it with `just load-data`.

Every spot contains `id`, `name`, `category`, `address`, `neighborhood`, `borough`, `latitude`, and `longitude`, plus `university`, which names the closest campus from the curated campus list within 500 metres and is null for every spot with no campus that close. Source-specific fields must be normalized before reaching the API, and the loader rejects a snapshot carrying any field outside that contract rather than dropping it silently. The importer applies the same check to its own output first, because its errors name the offending record while the loader's arrive at deployment time.

Database code belongs to the backend's `spots` app rather than to this source-data directory: the model, the migrations, and the `load_spots` command live there, and nothing in `data/` talks to a database. The serving table and any separate search index remain rebuildable projections of `spots.json` until the product accepts non-reproducible writes — see [Postgres database](database.md).
