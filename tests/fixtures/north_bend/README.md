# North Bend fixtures

Captured from the live site on 2026-11-15 with a real browser, then trimmed.

- `index.html`: the by-category event list from `https://tix.northbendtheatre.com/`, a selection
  of its categories and events. "Alien Private Eye" appears under two categories, as on the site.
- `event_mrs-miniver-sunday-nov-15th-3pm.html`: title bar and description of that event page,
  including the `1942 [Not Rated] 2h 14m` line.
- `event_the-hunger-games-…-saturday-nov-28th-7pm.html`: an event whose web address says 7pm but
  whose page says 3:00pm. The page is right; this is why dates are never read from titles or links.

To refresh with full pages: `python -m scrapers.run --source north_bend --save-fixtures`.
