# Admiral fixtures

Captured from the live API on 2026-11-15 with a real browser, then trimmed.

- `showtimes_20261115.json`: response of `getShowtimesByDayDisplay.php` for the Admiral
  (location `00001-00001-00002`) on 2026-11-15. Kept: `error`, `tzone`, `current_date`, the first
  25 `validDates`, and per film the id, name, release date, rating, runtime (seconds), directors
  and screenings (id, site, screen, start time as Unix seconds, sold-out and visibility flags,
  attributes). Removed: posters, synopses, cast, ticket inventory.
- `home.html`: the line of the farawayentertainment.com home page that holds the `eid` site key.

To refresh: `python -m scrapers.run --source admiral --save-fixtures`.
