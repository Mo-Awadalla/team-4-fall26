# Study-spot data

This directory is the small boundary between NYC Open Data and StudySpot:

```text
NYC Open Data -> ingest.py -> spots.json
```

- `ingest.py` downloads NYC Open Data and normalizes it into the shared contract.
- `spots.json` is the canonical generated dataset consumed by the application.
- `test_ingest.py` tests the mapping.
- `fixtures/` is a trimmed copy of what the upstream datasets return, so the tests and
  `--fixtures` need no network.

Regenerating the snapshot is how the data changes:

```shell
just ingest
just load-data
```

`spots.json` stays in version control, so a checkout can load the serving table and run the API
without reaching NYC Open Data. Nothing writes to it at runtime. Database migrations, local
database files, and search indexes do not belong here; the backend's `load_spots` management
command copies this snapshot into the Postgres serving table, replacing its contents in one
transaction.

A spot contains `id`, `name`, `category`, `address`, `neighborhood`, `borough`, `latitude`, and
`longitude`, plus `university`. A field outside that set makes the loader fail rather than
disappear silently, and the importer checks its own output against the same set first, because
its errors name the record and the loader's arrive at deployment time.

## Where the records come from

One dataset: the city's [Facilities Database][facdb] (FacDB, Socrata `ji82-xba5`), which is what
the `facdb:` identifier prefix refers to. Two subsets of it are places a student might read in —
the `LIBRARIES` facility group and the `COLLEGES OR UNIVERSITIES` subgroup — which is 380 public,
academic, and institutional libraries and campuses across the five boroughs. Neighborhood names
come from a second dataset, the [2020 Neighborhood Tabulation Areas][nta] (`9nt8-h7nd`), because
FacDB publishes the NTA code and not its name.

Requests identify themselves and page politely. `NYC_OPEN_DATA_APP_TOKEN` raises the rate limit
from the shared anonymous pool to a personal one; the importer runs without it, and the token is
read from the environment so it never reaches version control.

FacDB lists no cafés, so no record maps to the published `cafe` category yet. The obvious
candidate, the health department's restaurant inspection results, is an inspection log rather
than a directory of open businesses: it keeps establishments that closed years ago and carries no
2020 NTA, so publishing it as study spots would assert more than the data supports. A café source
is an open question, not a missing line of code.

## Identifiers

An identifier is the source prefix and FacDB's own `uid`, as in
`facdb:eec118768e15a5e03d3354abda7b00da`. The digest is upstream's, derived from the source
record, and the importer treats it as the record's identity rather than computing one of its own.

That choice is about churn. `load_spots` replaces the whole table rather than upserting, so an
identifier derived from a record's *contents* — its name, address, or coordinates — would change
every time the city fixed a typo or re-geocoded a building, and every row would silently come
back as a different spot with the old one deleted. Deriving it from identity alone means
re-running the importer against unchanged upstream data writes a byte-identical snapshot, and a
renamed facility is an update to one row. The prefix keeps a second source from colliding with
FacDB if its keys ever look the same.

## Categories

`library`, `academic_library`, `university`, and `cafe` are the published vocabulary. The model
leaves `category` a free string on purpose, so the vocabulary lives in `ingest.py`, keyed on
FacDB's most specific facility type. A type nobody has mapped fails the import rather than
landing in a near-enough bucket: inventing a category would publish a guess as data, and mapping
it to the closest existing one would bury the fact that FacDB changed.

FacDB's special libraries — a club's, a society's, a hospital's — are categorized `library`,
because that is the kind of place they are. Many are open by appointment or to members only. The
contract has no field for access and the application promises none: these are candidate
locations, not guarantees of Wi-Fi, outlets, seating, quietness, or entry.

## Absent values

`address`, `neighborhood`, and `university` are genuinely absent for some records: FacDB has no
street address for three dozen library branches, and an older extract predates the 2020 NTA
column. They are written as `null`, never as an empty string — the contract distinguishes the two
and the API returns `null`.

## `university` is proximity

It names the closest campus within 500 metres, or the campus itself for a campus record, and is
`null` when no campus is that close. The campus list is curated — it is the higher-education
subset of FacDB named above, the same records the importer publishes as `university` spots — and
the field is never guessed from a facility's name, its operator, or anything else.

A named campus is not an affiliation, an endorsement, or a claim that anyone may walk in. One
hundred and sixty-nine metres is what the data says about "125th Street Library" and "Touro
University - Harlem", and it says nothing more than that.

[facdb]: https://data.cityofnewyork.us/City-Government/Facilities-Database/ji82-xba5
[nta]: https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd
