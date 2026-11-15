# Majestic Bay fixtures

Captured from the live API on 2026-11-14 with a real browser, then trimmed.

- `schedule.json`: response of `/api/gatsby-source-boxofficeapi/schedule` for 2026-11-14 to
  2026-12-06, cut to the first two dates of each film, with only the `default` (Veezi) ticketing
  entry kept per showtime and occupancy figures removed.
- `movies.json`: `/api/gatsby-source-boxofficeapi/movies` for those films, cut to the fields the
  scraper reads (id, title, runtime, direction, release, certificate).

To refresh with full responses: `python -m scrapers.run --source majestic_bay --save-fixtures`.
