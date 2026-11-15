# SIFF fixtures

Captured from the live site on 2026-11-14 with a real browser.

- `calendar_2026-11-17.html`: the date heading and the whole `div.listing` block from
  `https://www.siff.net/calendar?view=list&date=2026-11-17`, as the server sent it.
  Removed to keep the file small: site header, navigation, footer, scripts, poster
  images and trailer pop-ups. Nothing the scraper reads was altered.
- `calendar_2027-03-02_empty.html`: a day with nothing scheduled, cut down to the
  date heading and day links. On the real page there is no `div.listing` at all.

To refresh with full pages: `python -m scrapers.run --source siff --save-fixtures`.
