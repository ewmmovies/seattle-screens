# Beacon fixtures

Captured from the live site on 2026-11-14 with a real browser, then trimmed.

- `calendar.html`: the list view from `https://thebeacon.film/calendar` for a selection of days
  (November 15–24 and January 2–30), markup exactly as sent. The grid view (same data), page
  chrome, images and styling attributes were removed.
- `movie_the-strange-love-of-martha-ivers.html`: the Movie JSON-LD block and credits text from
  that film's page.

To refresh with full pages: `python -m scrapers.run --source beacon --save-fixtures`.
