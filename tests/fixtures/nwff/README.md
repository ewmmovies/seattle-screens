# NWFF fixtures

Captured from the live site on 2026-11-14 with a real browser, then trimmed.

- `calendar_2026-11-14.html`, `calendar_2026-11-20.html`: a selection of `div.calendar__item` entries
  from two calendar weeks, with the "Next Week" links. Item markup is as sent, minus image previews.
  Note the week runs Friday to Thursday (`?start=2026-11-14` returns Nov 13 to Nov 19).
- `film_unstreamable-love-streams.html`, `film_go-fish-4k-restoration.html`: title, ticket button,
  credits (`div.film-details`), series line and first About paragraph from each film page.

To refresh with full pages: `python -m scrapers.run --source nwff --save-fixtures`.
