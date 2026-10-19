# End-to-end tests

Every other suite in this repository tests one part against stand-ins: the
backend runs Django against a test database, the frontend runs components
against a mocked `fetch`, and the data suite runs the importer against committed
fixtures. The failures those cannot see are the ones in the seams -- CloudFront
routing `/api/*` to the wrong origin, a migration that was never applied, a
deployment whose database is empty.

These tests drive a real, running StudySpot over HTTP. They need a base URL and
are skipped without one:

```shell
STUDYSPOT_E2E_URL=https://d1ulyrfyi06kwp.cloudfront.net just test-e2e
```

Any reachable deployment works. Against the local stack:

```shell
just start
STUDYSPOT_E2E_URL=http://localhost:7500 just test-e2e
```

They are not part of `just check` or `just test`, because those must pass on a
checkout with nothing running.

## What they assert

Invariants, not counts. `data/spots.json` is regenerated whenever the upstream
data changes, so a test pinned to "48 spots in the Bronx" would fail on a
perfectly good snapshot. What holds regardless:

- a borough filter returns only that borough, and narrows rather than widens;
- the facet counts add up to the result set they describe, and every value a
  facet offers returns exactly the number of spots it claims;
- paging neither repeats a row nor skips one;
- a misspelling still finds something, and an unrelated query finds nothing;
- an identifier survives CloudFront, API Gateway and Django's URL routing with
  its `facdb:` prefix intact.

Everything here is a GET. The API exposes no mutation, and these tests are safe
to run against the deployed site.
