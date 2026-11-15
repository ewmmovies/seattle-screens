# Tasveer fixtures

Captured from the live GraphQL endpoint (`https://filmcenter.tasveer.org/graphql`) on 2026-11-15
with a real browser, using the exact queries in `scrapers/sources/tasveer.py`. Not trimmed.

- `dates.json`: `datesWithShowing` for site 262.
- `showings_2026-11-16.json`: `showingsForDate` for 2026-11-16. Times are UTC; the 00:15Z showing
  is 4:15 PM on the 16th in Seattle.

To refresh: `python -m scrapers.run --source tasveer --save-fixtures`.
