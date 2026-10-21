# Data and search

StudySpot has one small data boundary:

```text
NYC Open Data -> data/ingest.py -> data/spots.json -> Postgres -> API
                                                   \-> search index
```

The snapshot holds 2,422 third places across the five boroughs: 2,158 cafés, 227 public library branches, 21 special libraries, 8 academic libraries and 8 NYU campus buildings. The city's 126 campus records are read but not published: an institution's administrative point is not a room, and access to a campus is restricted. They anchor the "near which campus" label instead. These are candidate locations, not guarantees of Wi-Fi, outlets, seating, quietness, or availability.

The directory intentionally stays small:

- `README.md` documents the boundary, including where the records come from and what each field means.
- `ingest.py` downloads, normalizes, and validates.
- `spots.json` is the canonical generated dataset.
- `test_ingest.py` tests the mapping.
- `fixtures/` is a trimmed copy of what the upstream datasets return, so the tests and `ingest.py --fixtures` need no network.

Records come from the city's [Facilities Database](https://data.cityofnewyork.us/City-Government/Facilities-Database/ji82-xba5) (FacDB, Socrata `ji82-xba5`), which is what the `facdb:` identifier prefix refers to, with neighborhood names from the [2020 Neighborhood Tabulation Areas](https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd) (`9nt8-h7nd`). Cafés come from [DOHMH Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j) (`43nn-pn8j`) filtered to `cuisine_description = 'Coffee/Tea'`, which the `dohmh:` prefix refers to. FacDB holds no cafés and never will, because it registers what the city *operates* while a café is something the city *inspects* — and the inspector records what each establishment serves, which is the question the category asks.

That dataset is one row per inspection, so the importer folds its 21,000-odd rows down to the most recent inspection of each `camis` and publishes one record per establishment. An establishment closed at that most recent inspection is dropped; **a place that shut quietly, with no final inspection to record it, is still in here**, and nothing in the data says so. It is still an inspection log rather than a directory of open businesses, and that limit is the price of the category meaning anything at all.

Until this was fixed, cafés came from [Dining Out NYC](https://data.cityofnewyork.us/resource/fpeh-f7ci) (`fpeh-f7ci`), the register of outdoor-dining licences, and every row of it was published as a café on the strength of holding one. A sidewalk licence says a business puts tables on the pavement and nothing whatever about what it sells: of the 1,652 records that reached the snapshot that way, around 270 read as bars, pubs, pizzerias or restaurants — "Good Bar", "P.Mcdaid's Irish Pub", "Koronet Pizza" — against about 210 whose name reads like a coffee shop. It also missed every indoor-only café, because no pavement tables meant no licence and so no row. Dining Out NYC is still read, for the `outdoor_seating` attribute alone.

Neither register publishes a 2020 NTA code for a café — DOHMH's `nta` column is the 2010 vintage, four characters where a 2020 code is six — so a café's neighborhood and borough come from locating its coordinates inside the NTA boundary polygons, while a facility's neighborhood is still a lookup on the code FacDB publishes. One field derived two ways is not ideal; joining 2010 codes to 2010 names would have put two neighborhood vocabularies in one snapshot and made the `neighborhood` filter depend on which source a spot came from. Regenerate the snapshot with `just ingest` and load it with `just load-data`.

Every spot contains `id`, `name`, `category`, `address`, `neighborhood`, `borough`, `latitude`, and `longitude`, plus `university`, which names the closest campus from the curated campus list within 500 metres and is null for every spot with no campus that close. Source-specific fields must be normalized before reaching the API, and the loader rejects a snapshot carrying any field outside that contract rather than dropping it silently. The importer applies the same check to its own output first, because its errors name the offending record while the loader's arrive at deployment time.

Database code belongs to the backend's `spots` app rather than to this source-data directory: the model, the migrations, and the `load_spots` command live there, and nothing in `data/` talks to a database. The serving table and any separate search index remain rebuildable projections of `spots.json` until the product accepts non-reproducible writes — see [Postgres database](database.md).
