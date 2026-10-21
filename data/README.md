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

The city's [Facilities Database][facdb] (FacDB, Socrata `ji82-xba5`), which is what the `facdb:`
identifier prefix refers to. Two subsets of it are places a student might read in — the
`LIBRARIES` facility group and the `COLLEGES OR UNIVERSITIES` subgroup — which is 390 public,
academic, and institutional libraries and campuses across the five boroughs.

Cafés come from [DOHMH Restaurant Inspection Results][dohmh] (`43nn-pn8j`) filtered to
`cuisine_description = 'Coffee/Tea'`, which is what the `dohmh:` prefix refers to. That is about
2,160 establishments. `cuisine_description` is the health department's own classification of what
a place serves, chosen from a fixed list, and it is the whole of the category test: the importer
does not read names, because deciding what a business is from the words in its name is guessing.

That dataset is one row per inspection — roughly 21,000 rows for those establishments — so the
importer folds it down to the most recent inspection of each `camis`. The most recent row is the
one whose `action` says whether the place is currently closed and whose address and geocode are
the freshest the city has. `dba` and `(building, street)` are constant within every `camis` in the
dataset, so no choice of row here could change a published name or address.

Sidewalk-dining licences come from [Dining Out NYC][dining] (`fpeh-f7ci`), read for the
`outdoor_seating` attribute alone. Only `Issued` `Sidewalk` licences: the register also carries
applications that were never granted, and crediting a café with seating on the strength of an
ungranted application would be a false statement about a real business, while a `Roadway` licence
is a dining structure in a parking lane rather than somewhere to sit with a laptop.

Neighborhood names come from the [2020 Neighborhood Tabulation Areas][nta] (`9nt8-h7nd`), read two
ways. FacDB publishes the 2020 code but not its name, so a facility's neighborhood is a dictionary
lookup. DOHMH publishes no 2020 code — its `nta` column is the 2010 vintage, four characters where
a 2020 code is six — so a café's neighborhood *and* borough come from locating its coordinates
inside the boundary polygons. That costs a 4.5 MB download of coastline per run and is worth it:
joining 2010 codes to 2010 names would put two neighborhood vocabularies in one snapshot and make
the `neighborhood` filter depend on which source a spot came from.

Requests identify themselves and page politely. `NYC_OPEN_DATA_APP_TOKEN` raises the rate limit
from the shared anonymous pool to a personal one; the importer runs without it, and the token is
read from the environment so it never reaches version control.

FacDB itself lists no cafés, and never will: it is a register of facilities the city *operates*,
while a café is a business the city *inspects*.

### What a cuisine classification does and does not say

It says the health department recorded this establishment as serving coffee or tea, which is the
question the category asks. It says nothing about hours, Wi-Fi, power, noise, seating, or whether
anyone may sit with a laptop and one coffee for three hours. The contract has no field for any of
that and the application promises none.

It is still an inspection log rather than a directory of open businesses. An establishment closed
at its most recent inspection is dropped, which catches inspection-ordered closures and nothing
else: **a café that shut quietly, with no final inspection to record it, is still in here**, and
nothing in the data says so. That is the price of the category meaning anything at all.

### What this replaced, and why

Until this was fixed, cafés came from Dining Out NYC and *every row of it* was published as a café
on the strength of holding an outdoor-dining licence. A sidewalk licence says a business puts
tables on the pavement; it says nothing whatever about what the business sells. Of the 1,652
records that reached the snapshot that way, around 270 read as bars, pubs, pizzerias or
restaurants — *Good Bar*, *P.Mcdaid's Irish Pub*, *Mchale's Bar & Grill*, *Koronet Pizza* —
against about 210 whose name reads like a coffee shop. The application was telling students an
Irish pub was a café. It also missed every indoor-only coffee shop in the city, because no
pavement tables meant no licence and so no row.

Regenerating against DOHMH took that measure from 272 names reading as a bar, pub, pizzeria or
restaurant down to 28, on a set of cafés 31% larger.

### `outdoor_seating` is a join, and a strict one

A Dining Out licence sets `outdoor_seating` on a café when the licence's name *and* street address
both match. `false` means no licence matched, not that there is nowhere to sit outside.

The strictness is because the failure modes are not symmetric. Matching on street address alone
would credit a café with whichever other business shares its building: 28 cafés share an address
with a licence held under a different name, and inspecting them shows almost every one is a
different business — *787 Coffee* at 100 Lexington Ave shares its address with *Bhatti Indian
Grill*, *Joe Coffee* at 405 W 23 St with *Henry & The Lions*. A café missing its licence reads as
a `false`, which is what the field is documented to mean. A café credited with someone else's
licence is a claim about a real business that is simply untrue. Those 28 are left unmatched on
purpose, and 108 cafés carry the attribute.

The two registers spell an address differently and neither is wrong — DOHMH stores `102` and
`HICKS STREET` in separate columns where Dining Out stores `102 HICKS STREET` — so street types,
compass directions and ordinals are folded to one form before comparing. Those match keys are
never published.

## `operator` is who runs it

FacDB's `opname`. For the 226 public branches it is the system — 91 New York Public Library, 68
Brooklyn, 67 Queens — and it is the only field that says so: a branch is named after its
neighbourhood, so *Howard Beach* and *Fresh Meadows* carry nothing else to connect them to Queens
Public Library. The three systems have separate membership, which makes it worth publishing and
not only searching.

It is not title-cased. Upstream already capitalises this field, unlike `facname`, so passing it
through the title-caser would leave *Nyu Tamiment Library* exactly as wrong as it arrives. For
academic and special libraries it repeats the facility's own name, where it adds nothing and does
no harm. Cafés have none: DOHMH records the establishment rather than who runs it, and the licence
register it replaced named only the company holding the licence — *CGM-LLNR LLC* where the trading
name was *JEAN'S*.

## Identifiers

A café identifier is `dohmh:` and the establishment's `camis`, as in `dohmh:50037080`. `camis` is
the health department's own permit number and is stable across inspections, a renaming and a
re-geocode, which is exactly what the churn argument below asks of an identifier. The previous
source had no such key, so the identifier was a digest of name and address: renaming a café
deleted it and created a stranger in its place.

A facility identifier is the source prefix and FacDB's own `uid`, as in
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

`cafe`, `public_library`, `special_library`, `academic_library` and `university_building` are the published vocabulary. The model leaves `category` a free string on purpose, so the vocabulary lives in
`ingest.py`. The FacDB categories are keyed on its most specific facility type; `cafe` is keyed on DOHMH's
`cuisine_description` being `Coffee/Tea`. A type nobody has mapped fails the import rather than
landing in a near-enough bucket: inventing a category would publish a guess as data, and mapping
it to the closest existing one would bury the fact that FacDB changed.

`public_library` and `special_library` are separate because the difference is the one a reader
cares about. A branch of NYPL, BPL or QPL is somewhere anyone can walk into. A special library is
an institutional collection — a club's, a society's, a hospital's — and many are open by
appointment or to members only, so publishing them as public would claim access the data does not
support. That is the same overclaim `free_public_wifi` and `university` are each worded to avoid.

The institution records in FacDB's higher-education subgroup are read but never published. An
administrative point for "Daemen University-Brooklyn Branch" is a registration rather than a room,
and campus access is restricted in any case; they exist here only to anchor the `university`
label. The campus study space the snapshot does publish is the curated NYU list.

None of this is a guarantee of entry. The contract has no field for access and the application
promises none: these are candidate locations, not guarantees of Wi-Fi, outlets, seating,
quietness, or entry.

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

**Cafés never carry one.** A café is a third place in its own right, not somewhere you reach
through a campus: a library beside a campus is plausibly *its* library, while the café on the
same corner is just a café. Leaving the field set would also have been unreliable in a way no
parameter fixes. FacDB stores one point per institution whatever its size, so Columbia's entire
Morningside campus is a single coordinate and its nearest café is 181 metres away, while a school
occupying one floor has one at 67 metres. Narrowing the radius therefore drops the universities
students attend before it drops the vocational schools nobody is looking for, and `factype`,
`capacity` and `optype` cannot tell the two apart either — Columbia and the NY School of Interior
Design are both `4-YEAR INDEPENDENT`, and every campus record has a capacity of `0`.

A named campus is not an affiliation, an endorsement, or a claim that anyone may walk in. One
hundred and sixty-nine metres is what the data says about "125th Street Library" and "Touro
University - Harlem", and it says nothing more than that.

[dining]: https://data.cityofnewyork.us/resource/fpeh-f7ci
[dohmh]: https://data.cityofnewyork.us/resource/43nn-pn8j
[facdb]: https://data.cityofnewyork.us/City-Government/Facilities-Database/ji82-xba5
[nta]: https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd
