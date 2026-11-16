# Seattle Screens — SPEC

Version 1.0, 2026-11-14. Source of truth for the build. Read BRIEF.md and SURVEY.md first; where they differ from this file, this file wins. Do not change a decision in this file without asking Elijah.

**For the builder (Claude Opus):** Elijah is not experienced with GitHub, hosting or app setup. Explain every setup step in plain language. Ask before installing anything, creating accounts or repositories, or storing tokens. Stop and report at the end of each build stage in section 12.

---

## 1. Decisions already made

| Topic | Decision |
|---|---|
| Hosting | GitHub Pages, free tier, static site. This requires a **public** repository: the code and scraped data are publicly visible even though the site is `noindex`. |
| Scrapers | Python 3.12, `requests` + `beautifulsoup4`. No headless browser in GitHub Actions. |
| Front end | Plain HTML, CSS and vanilla JavaScript. No framework, no build step, no npm. |
| Data | Scrapers write JSON into the repo; the front end fetches it. |
| Regal | Not scraped in GitHub Actions (Cloudflare blocks it). Regal venues always appear on the Venues page with a link out. Regal listings come from an optional scraper that runs on Elijah's Windows PC (section 8). The site must be complete and correct without it. |
| North Bend non-film events | Included, labelled "Live event". |
| News page (was Posts) | Changed 2026-11-15 with Elijah: the Posts page is now News, at news.html; posts.html forwards there. Two sections. "Happening Now": the same items as the Happening Now block. "Latest News": NWFF news, SIFF blog and press releases, Tasveer's own blog (tasveer.org/feed; not its Press page), released in the last 12 months (changed from 6 on 2026-11-15 with Elijah, because 6 months left the page nearly empty), newest first; posts with no release date are left out. Beacon, SIFF and NWFF series, festivals and programs appear only under Happening Now. No Regal, no social media. SIFF press-release dates are read from each release's own page. |
| Time zone | `America/Los_Angeles` for every date and time, in scrapers and in the browser. |
| Branding | Site name "Seattle Screens". No Screen Slate name, wordmark, logo, tagline or anniversary banner anywhere except the required footer line. |
| Happening Now block | Changed 2026-11-15 with Elijah (replaces "At the Beacon"; same sizes and spacing): top of the listings page, modelled on Screen Slate's Articles block. Top slot: the Beacon's Now Playing series, changed only with small arrows and a "1 / 2" counter centred directly under the image, above the description (hidden for one item; the row keeps its space). If the Beacon has no series, a Now Playing Beacon program takes the slot. It spans the full width and shows the Beacon page's own description: the first sentence, plus the second only if both fit in two lines (about 165 characters); never more than two lines on screen, and a sentence that runs longer ends with an ellipsis. Then "Scheduled <first month> – <last month>" from the Beacon calendar. Changed 2026-11-15 with Elijah: every lead item is exactly the same height (one-line title, two-line description, one-line months), so nothing shifts when cycling. Pages with no charset in their headers are read as UTF-8 (fixes "itâs"). Row: three tiles (one on phones, with its image) rotating through SIFF Programs & Events (festivals, series, cinema programs; grants skipped), NWFF festivals and series ("Current" only) and Beacon Now Playing programs, alternating theaters SIFF, NWFF, Beacon. A SIFF or NWFF item counts as happening only if that theater has a screening in the next 3 weeks whose series name matches the item's title (loose match: ignores "SIFF"/"the", plurals, a trailing year; partial matches need two or more words). SIFF's program pages do not list films, so name matching is the method. Every 10 seconds (changed from 7 on 2026-11-15) the row pushes one tile right to left within its frame; ◀ ▶ arrows step it; it pauses on hover or keyboard focus, has a pause/play button, and does not move on its own under prefers-reduced-motion. Tile labels: left (purple) theater · type, e.g. "SIFF · SERIES"; right "NEXT: NOV 20" (Beacon programs keep their month). Tile text: the first sentence of the item's blurb (Beacon programs: film count). NWFF's wide banners are cropped to fill 16:9. Every item links to its page on the theater's site; images load from the theaters' servers, never copied into the repository. Two heavy rules separate it from the listings; hidden when there is no data. Built into docs/data/features.json as {lead, row}. |
| Indexing | `<meta name="robots" content="noindex, nofollow">` on every page. No robots.txt (a project site under `username.github.io/repo/` cannot use one, and blocking crawlers would stop them seeing the noindex tag). |

---

## 2. Repository structure

Local folder: `C:\Users\elija\OneDrive\Documents\Projects\seattle-screens` (currently holds only SURVEY.md and SPEC.md). Repository name: `seattle-screens`.

```
seattle-screens/
├── BRIEF.md  SURVEY.md  SPEC.md  README.md
├── requirements.txt            # requests, beautifulsoup4, pytest
├── requirements-local.txt      # playwright (Regal PC scraper only)
├── .github/workflows/update.yml
├── scrapers/
│   ├── __init__.py
│   ├── run.py                  # runner: python -m scrapers.run [--source ID ...]
│   ├── build.py                # merges data/sources/* into docs/data/*
│   ├── http.py                 # shared session, retries, politeness delay
│   ├── context.py              # the ctx object handed to each scraper
│   ├── models.py               # dataclasses + validation
│   ├── util.py                 # date/time parsing, slugify, title cleaning
│   ├── sources/
│   │   ├── siff.py   nwff.py   beacon.py   majestic_bay.py
│   │   ├── tasveer.py   admiral.py   north_bend.py
│   └── posts/
│       ├── nwff.py   siff.py
├── local/
│   ├── regal.py                # Playwright scraper, runs on Elijah's PC
│   ├── run_regal.bat           # pull, scrape, build, commit, push
│   └── README.md               # plain-language setup
├── data/                       # last-good store; not served
│   ├── sources/<source_id>.json
│   ├── posts/<source_id>.json
│   ├── cache/<source_id>.json  # detail-page cache
│   └── status.json
├── docs/                       # the published site (Pages root)
│   ├── index.html              # listings
│   ├── venues.html
│   ├── news.html          (posts.html forwards here)
│   ├── search.html
│   ├── css/site.css
│   ├── js/common.js  listings.js  venues.js  posts.js  search.js
│   ├── fonts/Fraunces-VariableFont.woff2  OFL.txt
│   └── data/
│       ├── venues.json         # hand-authored (section 3.1)
│       ├── screenings.json     # generated
│       ├── posts.json          # generated
│       └── status.json         # generated
└── tests/
    ├── fixtures/<source_id>/…  # saved real responses
    └── test_<source_id>.py
```

All paths inside `docs/` must be relative (`css/site.css`, `data/screenings.json`), because the site is served from `https://<username>.github.io/seattle-screens/`.

---

## 3. Data model

### 3.1 Venues — `docs/data/venues.json` (hand-authored, order = display order)

```json
{
  "id": "siff-uptown",
  "name": "SIFF Cinema Uptown",
  "address": "511 Queen Anne Ave N, Seattle, WA 98109",
  "neighborhood": "Uptown",
  "url": "https://www.siff.net/cinema/cinema-venues/siff-cinema-uptown",
  "showtimes_url": "https://www.siff.net/calendar",
  "source": "siff",
  "group": "independent"
}
```

`group` is `"independent"` or `"regal"`. Seed data, in display order (independents alphabetical, Regals last):

| id | name | address | neighborhood | source | url |
|---|---|---|---|---|---|
| `admiral` | Historic Admiral Theater | 2343 California Ave SW, Seattle, WA 98116 | West Seattle | `admiral` | https://www.farawayentertainment.com/ |
| `beacon` | The Beacon | 4405 Rainier Ave S, Seattle, WA 98118 | Columbia City | `beacon` | https://thebeacon.film/calendar |
| `majestic-bay` | Majestic Bay Theatre | 2044 NW Market St, Seattle, WA 98107 | Ballard | `majestic_bay` | https://www.majesticbay.com/ |
| `north-bend` | North Bend Theatre | 125 Bendigo Blvd N, North Bend, WA 98045 | North Bend | `north_bend` | https://www.northbendtheatre.com/ |
| `nwff` | Northwest Film Forum | 1515 12th Ave, Seattle, WA 98122 | Capitol Hill | `nwff` | https://nwfilmforum.org/ |
| `siff-downtown` | SIFF Cinema Downtown | 2100 4th Ave, Seattle, WA 98121 | Belltown | `siff` | https://www.siff.net/cinema/cinema-venues/siff-cinema-downtown |
| `siff-film-center` | SIFF Film Center | 305 Harrison St, Seattle, WA 98109 | Seattle Center | `siff` | https://www.siff.net/cinema/cinema-venues/siff-film-center |
| `siff-uptown` | SIFF Cinema Uptown | 511 Queen Anne Ave N, Seattle, WA 98109 | Uptown | `siff` | https://www.siff.net/cinema/cinema-venues/siff-cinema-uptown |
| `tasveer` | Tasveer Film Center | 4812 Rainier Ave S, Seattle, WA 98118 | Columbia City | `tasveer` | https://filmcenter.tasveer.org/home/ |
| `regal-thornton` | Regal Thornton Place | 316 NE Thornton Pl, Seattle, WA 98125 | Northgate | `regal` | https://www.regmovies.com/theatres/regal-thornton-place-1937 |
| `regal-cinebarre` | Regal Cinebarre Mountlake Terrace | 6009 244th St SW, Mountlake Terrace, WA 98043 | Mountlake Terrace | `regal` | https://www.regmovies.com/theatres/regal-cinebarre-mountlake-1958 |
| `regal-meridian` | Regal Meridian | 1501 7th Ave, Seattle, WA 98101 | Downtown | `regal` | https://www.regmovies.com/theatres/regal-meridian-4dx-1931 |

Addresses for Majestic Bay, SIFF Uptown, SIFF Film Center, Regal Cinebarre and Regal Meridian were not confirmed during the survey: check each against the venue's own site before committing.

### 3.2 Screening

One record = one title at one venue on one calendar date, with all its showtimes that day (the same unit Screen Slate uses for a listing cell).

```json
{
  "id": "siff-uptown|2026-11-16|paper-tiger",
  "venue_id": "siff-uptown",
  "date": "2026-11-16",
  "title": "Paper Tiger",
  "kind": "film",
  "series": null,
  "directors": ["James Gray"],
  "year": 2026,
  "runtime_min": 114,
  "format": "35mm",
  "notes": [],
  "url": "https://www.siff.net/cinema/in-theaters/paper-tiger-(35mm)",
  "showtimes": [
    { "time": "16:00", "ticket_url": null, "note": null, "sold_out": false },
    { "time": "19:00", "ticket_url": null, "note": "Q&A with director", "sold_out": false }
  ]
}
```

| Field | Type | Rules |
|---|---|---|
| `id` | string | `venue_id|date|slug(title)`. Must be unique; if two records collide, merge their showtimes. |
| `venue_id` | string | Must exist in venues.json. |
| `date` | `YYYY-MM-DD` | The date the venue lists the show under. A 12:15 AM show listed under Friday stays on Friday. |
| `title` | string | Cleaned: no series prefix, no format suffix, no date text, no "(2026, Spain, Spanish)" style suffix. Keep the venue's capitalization, except convert ALL-CAPS titles to title case. |
| `kind` | `"film"` or `"event"` | `event` = non-film (live comedy etc.). |
| `series` | string or null | Series, program or festival name. |
| `directors` | string[] | Empty array if unknown. |
| `year` | int or null | Release year. From a full release date, take the year. |
| `runtime_min` | int or null | |
| `format` | string or null | One of `35mm`, `70mm`, `16mm`, `DCP`, `Digital`, `Film` (a print, gauge unknown), or null. Never guess: null when the source does not say. |
| `notes` | string[] | Screening-level notes, each at most 200 characters, plain text. |
| `url` | string or null | The venue's own page for this title. |
| `showtimes[].time` | `HH:MM` 24-hour | Sorted ascending. |
| `showtimes[].ticket_url` | string or null | Direct purchase link when the source gives one. The front end falls back to `url`. |
| `showtimes[].note` | string or null | Showtime-level note (open captions, Q&A, discount). |
| `showtimes[].sold_out` | bool | |

### 3.3 Post

```json
{
  "id": "siff|/media/blog/november-2026-at-siff-cinemas",
  "source": "siff",
  "source_name": "SIFF",
  "title": "November 2026 at SIFF Cinemas",
  "url": "https://www.siff.net/media/blog/november-2026-at-siff-cinemas",
  "published": "2026-10-30",
  "category": "Cinema",
  "summary": "With the new month we welcome a new lineup…"
}
```

`summary` is at most 240 characters, plain text, cut at a word boundary with an ellipsis. No images are copied or hot-linked. `published` may be null if the source gives no date; such posts sort by first-seen date (store `first_seen`).

### 3.4 Generated files

`data/sources/<source_id>.json` (last-good store, one per scraper):
```json
{ "source": "siff", "scraped_at": "2026-11-14T18:17:04-08:00", "screenings": [ … ] }
```

`docs/data/screenings.json`:
```json
{ "generated_at": "…", "range": { "start": "2026-11-07", "end": "2026-12-12" }, "screenings": [ … ] }
```
Sorted by date, then venue display order, then first showtime.

`docs/data/status.json` (copy of `data/status.json`):
```json
{
  "generated_at": "2026-11-14T18:17:40-08:00",
  "sources": {
    "siff": {
      "last_attempt": "2026-11-14T18:17:04-08:00",
      "last_success": "2026-11-14T18:17:04-08:00",
      "ok": true,
      "error": null,
      "count": 212,
      "venue_ids": ["siff-uptown", "siff-downtown", "siff-film-center"]
    }
  }
}
```

`docs/data/posts.json`: `{ "generated_at": "…", "posts": [ … ] }`, newest first, at most 60.

---

## 4. Scraper interface and error handling

### 4.1 Interface

Each file in `scrapers/sources/` exposes:

```python
SOURCE_ID = "siff"
VENUE_IDS = ["siff-uptown", "siff-downtown", "siff-film-center"]

def fetch(ctx) -> list[Screening]:
    """Fetch and parse. Raise on any failure. Never return partial data silently."""
```

`ctx` provides `ctx.http` (shared session), `ctx.today` (PT date), `ctx.horizon_days` (default 21), `ctx.cache` (dict persisted to `data/cache/<source>.json`) and `ctx.save_fixture(name, text)` (writes to `tests/fixtures/<source>/` only when run with `--save-fixtures`).

Inside each source, keep network and parsing apart: `fetch()` downloads, pure functions (`parse_day(html)`, `parse_detail(html)`) turn text into records. Tests call only the pure functions against fixtures.

Post scrapers in `scrapers/posts/` follow the same shape with `fetch(ctx) -> list[Post]`.

### 4.2 Runner (`python -m scrapers.run`)

For each source, independently:

1. Record `last_attempt`.
2. Call `fetch(ctx)` inside try/except. A failure in one source never stops the others.
3. Validate every record against section 3.2. Any invalid record fails the whole source.
4. Sanity check: zero screenings dated today or later counts as a failure ("empty result").
5. On success: write `data/sources/<id>.json`, set `ok: true`, `last_success`, `count`, clear `error`.
6. On failure: leave `data/sources/<id>.json` untouched, set `ok: false` and a one-line `error`. Print the full traceback to the log.

Merge rule on success: new records replace all stored records dated today or later. Stored records dated before today are kept for 7 days so "previous day" navigation works, then dropped.

Exit code is 0 even when sources fail (the workflow must go on to publish). Exit non-zero only if every source failed. Options: `--source ID` (repeatable), `--save-fixtures`, `--posts-only`, `--no-posts`.

### 4.3 Build (`python -m scrapers.build`)

Reads every `data/sources/*.json` (including stale ones and `regal.json` if present) and `data/posts/*.json`; writes `docs/data/screenings.json`, `posts.json`, `status.json`. Drops screenings older than 7 days. Never fails because a source file is missing.

### 4.4 HTTP rules (`scrapers/http.py`)

- User-Agent: `SeattleScreens/1.0 (personal listings project; +<repo URL>)`.
- Timeout 30 s; 2 retries with backoff on network errors and 5xx; no retry on 4xx.
- At least 1 second between requests to the same host.
- Detail pages (per-film pages) are cached in `ctx.cache` by URL with a fetch date; refetch after 7 days. A typical full run should stay under about 120 requests.

### 4.5 Staleness (computed in the browser from status.json)

A source is **out of date** when `ok` is false, or `last_success` is more than 36 hours old, or the source is missing from status.json. The 36-hour rule is what flags the Regal PC scraper when the PC has been off.

---

## 5. Source notes

Details below were observed on 2026-11-14. Markup changes; for every source, the first job is `--save-fixtures`, then write the parser against the saved files. SIFF is built in Phase 3 as the reference; copy its structure.

### 5.1 `siff` (reference scraper, built in Phase 3)

**Built and tested: `scrapers/sources/siff.py`, `tests/test_siff.py`.** `models.py`, `util.py`, `http.py` and `context.py` also exist; extend them, do not rewrite them. The notes below record how it works. Where they differ from the code, the code is right.

- One GET per day: `https://www.siff.net/calendar?view=list&date=YYYY-MM-DD` for today through today + horizon. Stop early after 5 consecutive days with no items.
- Each film is a `div.item` inside `div.listing`. Title and detail link: `.small-copy h3 a`. Meta line: `p.meta`, pipe-separated `Country | Year | 175 min. | Director, Director` (director may be absent; runtime may lack "min.").
- A film can have more than one `div.times` block, one per venue. Venue name: `.times h3 a`. Showtimes: `a.elevent[data-screening]`; the attribute is JSON with `VenueName`, `Showtime` as `/Date(epoch_ms)/` (convert to PT), `LengthInMinutes`, `ShowtimeId`, `HasTicketsOnSale`, `PublicAllocationSoldOutPercentage` (100 = sold out).
- Venue id comes from the venue link in `.times h3 a` (href ends in `siff-cinema-uptown`, `siff-cinema-downtown` or `siff-film-center`). Do not use `VenueName` from the JSON: it names the auditorium ("SIFF Cinema Uptown House 2"). Blocks for any other venue are skipped.
- The page prints its own date (`.h1 span`, "Tuesday, November 17, 2026"). The scraper checks it against the date requested and fails on a mismatch. A day with nothing on has no `div.listing` at all.
- Format: a title suffix `(35mm)`, `(70mm)`, `(16mm)` becomes `format` and is removed from the title.
- Series: split `Prefix: Title` when the ticketing name in the JSON (`EventName`, which omits the series) matches the part after the colon; or the prefix is in the `SERIES_PREFIXES` list in the source file; or the same prefix appears on two or more different titles in the run. `NOT_SERIES_PREFIXES` is the manual override. This protects titles like "Mission: Impossible".
- Notes: `p.alert` inside the item (for example the passes-and-vouchers notice).
- `url` = `https://www.siff.net` + detail href. `ticket_url` = null (tickets open in a pop-up; the detail page is the working link).

### 5.2 `nwff`

- GET `https://nwfilmforum.org/calendar/?start=YYYY-MM-DD` in 7-day steps starting from the most recent Saturday (the calendar week runs Saturday to Friday).
- Each entry is `div.calendar__item` with schema.org microdata: `meta[itemprop=startDate]` (local time, e.g. `2026-11-20T19:00:00`), `meta[itemprop=duration]` (`PT140M`), `meta[itemprop=name]`, `meta[itemprop=mainEntityOfPage]` (detail URL). The class carries the type: `calendar__item--film`, `--event`, `--workshop`.
- Keep films and events (`kind` accordingly); skip workshops.
- Attributes ("On Film", "Visiting Artist", "Live Music", "Discussion") sit in `.calendar-popup__attributes`. "On Film" sets `format: "Film"`; the others become notes.
- Detail page (cached) gives director, country, year, runtime and a `Series - <name>` line; a parenthetical like `(John Cassavetes, 1984, United States, 140 min, in English)` is a fallback. If a gauge (35mm/16mm) appears in the detail text next to the credits, use it for `format`.
- Title cleaning: when the detail page gives a series, strip a matching `Series - ` or `Series: ` prefix from the title ("Unstreamable - Love Streams" becomes "Love Streams", series "Unstreamable"). Strip a trailing "(4K Restoration)" into a note.
- `ticket_url`: the Eventive link on the detail page ("Get Tickets", host `nwfilmforum.eventive.org`).

### 5.3 `beacon`

- One GET: `https://thebeacon.film/calendar` holds every upcoming date. Entries are `div.cal-entry` with `a.cal-movie` (title, detail href), `span.cal-time`, and `a.cal-ticket` (href carries `?showtime=<id>`). The day number and month come from the surrounding calendar cell and month heading: work out the full date, handling the year rollover.
- Skip any entry titled "RENT THE BEACON" (case-insensitive) or without a `/calendar/movie/` link.
- "SOLD OUT" in the entry sets `sold_out`.
- Detail page (cached): year, Director, Runtime ("116 minutes"), plus JSON-LD `Movie`. Titles are ALL CAPS on the site: convert to title case.
- `ticket_url` = absolute `a.cal-ticket` href.
- Series: optional. `/series` and `/programs` list them; only add if a film's detail page names its series plainly. Otherwise null.

### 5.4 `majestic_bay`

- JSON over plain GET, theater id `X05TV`:
  - `/api/gatsby-source-boxofficeapi/scheduledMovies?theaterId=X05TV` returns `scheduledDays` (movie id to dates).
  - `/api/gatsby-source-boxofficeapi/schedule?from=<date>T03:00:00&to=<date+1>T03:00:00&theaters={"id":"X05TV","timeZone":"America/Los_Angeles"}` (URL-encode the JSON) returns `X05TV.schedule[movieId][date][]` with `startsAt` (local), `tags`, `screen.name`, `data.ticketing[]`. Try one request spanning the whole horizon first; if the API rejects or truncates it, request day by day for the dates in `scheduledDays`.
  - `/api/gatsby-source-boxofficeapi/movies?basic=false&castingLimit=3&ids=<id>&ids=<id>` returns `title`, `runtime` (seconds), `direction[]`, `release` (ISO date), `certificate`.
- `format`: tag `Format.Projection.Digital` gives "Digital"; other `Format.Projection.*` values map by name (35mm, 70mm); unknown values null.
- `ticket_url`: first URL of the ticketing entry with `provider: "default"` (Veezi).
- `url`: `https://www.majesticbay.com/`.

### 5.5 `tasveer`

- Platform: INDY Cinema Group. Primary method is GraphQL: POST `https://filmcenter.tasveer.org/graphql`. Operations seen: `datesWithShowing` (returns a JSON string list of dates) and `showingsForDate` (returns `data[]` of showings with `time` in UTC, `published`, `private`, `movie{ name, directedBy, duration, releaseDate, urlSlug, displayMetaData }`, and `displayMetaData.classes` on the showing).
- The query text and variables are not known yet. Get them from the site's JS bundle (`/js/app.*.js`, search for `showingsForDate`) or from the browser's network tab, and store the query in the source file. Request only the fields used.
- Fallback if GraphQL cannot be made to work within a reasonable effort: parse the server-rendered HTML of `https://filmcenter.tasveer.org/showtimes/` (movie blocks carry `data-test-id="showtimes-list-view-movie-container"`). Say which method was used in the stage report.
- Skip showings with `published: false` or `private: true`. Convert UTC to PT; the PT date is the record date.
- Title cleaning: strip a trailing parenthetical that contains a year or a country/language ("La Bola Negra (2026, Spain, Spanish)" becomes "La Bola Negra"); move "with post-film Q&A" style text into a note.
- Notes from badges in `movie.displayMetaData` / showing classes: keep "Open Captions" and subtitle badges as showtime notes; ignore accessibility-of-building badges.
- `year` from `releaseDate`; `directors` from `directedBy` split on commas; `url` = `https://filmcenter.tasveer.org/movie/<urlSlug>/`; `ticket_url` null unless the checkout URL pattern is evident from the site.
- This source only publishes about 6 days ahead. That is normal, not a failure.

### 5.6 `admiral`

- Platform: Mobile Moviegoing. POST `https://api-v3.mobilemoviegoing.cloud/include/app/getShowtimesByDayDisplay.php`, body is a JSON string sent without a JSON content-type header (the site uses a bare `fetch` with `JSON.stringify`): `{"eid": "<eid>", "pos_route": 1, "date": "YYYYMMDD", "mode": "now", "location": "00001-00001-00002"}`. Location `00001-00001-00002` is the Admiral.
- `eid` is a site key in the page's JavaScript. Read it at run time from `https://www.farawayentertainment.com/` (a UUID assigned to `eid`); fall back to `efbc509c-5e9b-4178-8dc6-a2e635ba8057` if it cannot be found.
- Response fields seen in the site code: `films`, `validDates`, `error`, `error_message`, `tzone`. **The shape of `films` was not inspected during the survey.** Save a fixture first and write the parser from it. Use `validDates` to decide which dates to request; one request per date.
- The rendered page shows, per film: title, runtime ("2hr. 10min."), rating, showtimes, and per-showtime labels such as "THIS SCREENING WILL HAVE OPEN CAPTIONED SUBTITLES" and "** DISCOUNTED PRICING **". Map those to showtime notes ("Open captions", "Discount pricing"). Director, year and format are not expected: leave them empty.
- `url` and `ticket_url`: `https://www.farawayentertainment.com/` unless the response carries a per-showtime purchase link.

### 5.7 `north_bend`

- Platform: ThunderTix. GET `https://tix.northbendtheatre.com/` lists every event under category headings; links are `div.title a[href^="/event/"]`. An event can appear under more than one category: de-duplicate by URL.
- For each event URL (cached), GET the event page. It contains a line like `November 15th, 2026 @ 3:00pm PST`: parse that for date and time. Do not parse the date from the title.
- Title: strip the trailing parenthetical with the day and time ("Mrs. Miniver (Sunday Nov. 15th @3pm)" becomes "Mrs. Miniver").
- Series: the category name, except skip generic categories ("Free Shows!", "Show All Categories") and any category that is just the film's own title. "Free Shows!" becomes a note ("Free admission").
- `kind: "event"` when the event's category is in `NON_FILM_CATEGORIES` (seed: "Live Comedy", "Seattle International Comedy Competition"). The front end labels these "Live event".
- Year and runtime: the description sometimes has a line like `1942 [Not Rated] 2h 14m`; parse it when present.
- `ticket_url` and `url`: the event page.

### 5.8 Posts

- `nwff`: GET `https://nwfilmforum.org/news/`. Each entry has a title link, a date line ("October 8, 2026") and an excerpt. First page only. (The site's RSS feed is stale: do not use it.)
- `siff`: GET `https://www.siff.net/media/blog` (title, date, category label, excerpt; links under `/media/blog/`) and `https://www.siff.net/media/news-x39250` (press releases: title, excerpt, "More Details" link; no date on the index page, so use `first_seen`). First page of each.
- Merge rule: keep previously stored posts, add new ones by `id`, cap each source at 40.

---

## 6. GitHub Actions workflow — `.github/workflows/update.yml`

One workflow, two jobs.

- **Triggers:** `schedule` four times a day at `17 1,7,13,19 * * *` UTC (about 5 AM, 11 AM, 5 PM and 11 PM Pacific; exact local times shift by an hour with daylight saving, and GitHub may start scheduled runs late); `workflow_dispatch` (the manual "Run workflow" button) with an optional `source` text input; `push` to `main` (so code changes and the PC's Regal pushes publish immediately).
- **Permissions:** `contents: write`, `pages: write`, `id-token: write`.
- **Concurrency:** group `update`, `cancel-in-progress: false`.
- **Job `scrape`** (skipped on `push` events): checkout; set up Python 3.12 with pip cache; `pip install -r requirements.txt`; `python -m scrapers.run` (pass `--source` when the input is set); `python -m scrapers.build`; commit `data/` and `docs/data/` as `github-actions[bot]` with message `Update listings <UTC timestamp>` and push. If the push is rejected because the PC pushed meanwhile, `git pull --rebase` and retry once. Commit every run (status timestamps always change); this also keeps the schedule alive, since GitHub pauses schedules on repositories with no activity for 60 days.
- **Job `deploy`** (`needs: scrape`, runs with `if: always()` so it also runs on push): checkout the latest `main`; `actions/configure-pages`; `actions/upload-pages-artifact` with `path: docs`; `actions/deploy-pages`.
- A scraper failure must not fail the workflow. The job fails only if the runner exits non-zero (every source failed) or the commit/deploy steps fail.
- Pin actions to current major versions; check the versions at build time.

---

## 7. Front end

### 7.1 Pages

| Page | Content |
|---|---|
| `index.html` | Daily listings. Date from `?date=YYYY-MM-DD`, default today (PT). |
| `venues.html` | All 12 venues: name, neighborhood, address, link, last updated, out-of-date mark. |
| `news.html` | Happening Now items, then Latest News from posts.json, newest first. `posts.html` forwards to it. |
| `search.html` | Search across screenings dated today or later. `?q=` in the URL. |

Every page: left rail (desktop) or top bar with menu (mobile), noindex meta tag, footer with exactly: **A personal project. Not affiliated with Screen Slate.**

### 7.2 Listings behavior

- Heading: full date, "Saturday, November 14th 2026", with previous and next arrow buttons. Arrows change `?date=` without a full reload (History API) and are disabled outside `range.start`–`range.end`. Clicking the date opens a native date input limited to that range. Left/right arrow keys also move a day.
- Controls row under the date: "On Film" checkbox (show only records whose format is 35mm, 70mm, 16mm or Film) and a "Venues" button opening the venue filter.
- Venue filter: a panel with a checkbox per venue in display order, plus two shortcuts: "Hide Regal" / "Show Regal" (toggles all three) and "All". Stored in `localStorage` under `ss.hiddenVenues` (wrap reads and writes in try/catch; fall back to in-memory). The button shows a count when anything is hidden ("Venues (3 hidden)").
- Body: for each visible venue with screenings that day, in display order: venue name (link to the venue's site), then its screenings sorted by first showtime, films before events at the same time.
- Out-of-date venue: directly under the venue name, small purple uppercase line: `OUT OF DATE · LAST UPDATED NOV 13, 6:17 PM`. Venues that are current show nothing here.
- Venue with no screenings that day: omitted. If the venue's source is out of date and it has no data, still omitted.
- If nothing is visible: "No listings for this date." centered in the serif face.
- Regal venues with no data at all (PC scraper never run): never appear on the listings page; no error.

### 7.3 Listing cell (one screening)

In order, all centered:

1. Series, if any: 14px uppercase sans, purple. Events show "LIVE EVENT" here when there is no series, or "SERIES · LIVE EVENT" when there is.
2. Title: 20px serif, underlined link to `url` (opens in a new tab; plain text if no url).
3. Meta line: 14px uppercase sans, comma-separated, only the parts that exist: `DIRECTOR(S), YEAR, 99M, FORMAT`. Formats of 35mm/70mm/16mm/Film are followed by a small film-strip glyph (inline SVG drawn for this site).
4. Notes: 14px serif, one per line.
5. Showtimes, pinned to the bottom of the cell: 14px uppercase sans, `4:00PM 7:00PM`, separated by spaces. Each is a link to its `ticket_url` or the record `url`. Sold-out times are struck through and not linked. A showtime with a note is purple with an asterisk, and the notes are listed under the row as `* Q&A with director`; when different showtimes have different notes use `*`, `**`, `***`.

### 7.4 Search

One text input, autofocus. Matches case-insensitively and accent-insensitively on title, directors, series and venue name; every word typed must match somewhere. Results: grouped by date (date as a serif subheading), each row `TIME(S) — Title — VENUE — series`, linking to `index.html?date=…`. Respects nothing from the venue filter (search covers all venues). Empty query shows a one-line prompt; no results shows "No upcoming screenings match."

### 7.5 News (was Posts)

Two sections, "Happening Now" then "Latest News", each a 3-column grid (1 column on mobile) of cells separated by rules: source or theater · type (14px uppercase purple), title (20px serif link, new tab), date or next screening (14px uppercase), summary or first sentence (14px sans). No images.

### 7.6 Venues

3-column grid (1 on mobile): venue name (20px serif link), neighborhood (14px uppercase purple), address (14px sans, linked to a maps search URL), "Showtimes" link for Regal venues, and `LAST UPDATED NOV 14, 5:17 PM` or the out-of-date line. No images, no purple placeholder blocks.

### 7.7 Shared JS (`common.js`)

Loads the JSON files with `fetch(url, { cache: "no-cache" })` and exposes helpers: PT "today" via `Intl.DateTimeFormat` with `timeZone: "America/Los_Angeles"`, date formatting with ordinal suffixes, 12-hour time formatting, staleness check, HTML escaping. All scraped text is inserted with `textContent` or escaped; never `innerHTML` with scraped strings. If a JSON file fails to load, show "Listings could not be loaded." in place of the content.

---

## 8. Regal PC scraper (`local/`) — optional, built last

Runs on Elijah's Windows PC because Regal blocks datacenter requests. **Ask before installing anything.** It needs: Python, Git, the `playwright` package and its Chromium download, and Git credentials able to push to the repo. Explain each in `local/README.md` in plain language, including how to undo it.

- `local/regal.py`: launches Chromium with Playwright using a persistent profile folder (`local/.profile/`, git-ignored), headed (not headless). For each theatre code (`1937` Thornton Place, `1958` Cinebarre Mountlake Terrace, `1931` Meridian): open the theatre page, wait for it to load, then from inside the page call `fetch('/api/getShowtimes?theatres=<code>&date=MM-DD-YYYY&hoCode=&ignoreCache=false&moviesOnly=false')` for each of the next 14 days, with a 1–2 second pause between calls. The theatre page's `__NEXT_DATA__` JSON (`props.pageProps`) also holds `movies[]` (`Title`, `Duration`, `Rating`, `OpeningDate`, `Directors[]`, `MasterMovieCode`) and `attributes[]`.
- Showtime shape (from the page data): `Film[] { Title, MasterMovieCode, Performances[] { CalendarShowTime (local), PerformanceAttributes, PerformanceId, StopSales } }`. Join to `movies` by `MasterMovieCode` for directors, runtime and year (from `OpeningDate`).
- Mapping: attributes "OC"/"Open Captioned" become the showtime note "Open captions"; "4DX", "3D" become notes; `format` is "Digital". Titles: strip "(Open Cap/Eng Sub)" style suffixes into the note. `url` = the theatre page. `ticket_url` null.
- Writes `data/sources/regal.json` and updates the `regal` entry in `data/status.json` using the same runner logic (import `scrapers.run` helpers; do not duplicate validation).
- If a Cloudflare challenge page appears, do not try to solve or bypass it: exit with a failure status so the site shows the Regals as out of date.
- `local/run_regal.bat`: `git pull --rebase`, run the scraper, `python -m scrapers.build`, commit `data/` and `docs/data/`, push. The push triggers the deploy job.
- Scheduling: Windows Task Scheduler, once daily at 9:13 AM, "run only when user is logged on" (a visible browser window opens for about two minutes). Document the steps with screenshots-free plain instructions.

---

## 9. Design

Model: screenslate.com's listings page, measured 2026-11-14. Match layout, density, hierarchy and restraint. Do not copy its logo, wordmark, tagline, scrolling banner, images or font files.

### 9.1 Tokens

| Token | Value |
|---|---|
| `--black` | `#000000` (text, rules) |
| `--white` | `#FFFFFF` (background) |
| `--accent` | `#8B4DFF` (series, section labels, active nav, noted showtimes, stale line, accent rules) |
| Serif | `"Fraunces", Georgia, serif`, weight 300, with `font-variation-settings: "SOFT" 100, "WONK" 0`. Stands in for Screen Slate's commercial Cooper Light. Self-host the variable woff2 in `docs/fonts/` with its OFL licence text; `font-display: swap`. |
| Sans | `"Helvetica Neue", Helvetica, Arial, sans-serif`, weight 400 |
| Base | 16px / 1.15, black on white. No grey text, no shadows, no rounded corners, no gradients. |

No other colors. No bold anywhere; hierarchy comes from size, case and typeface.

### 9.2 Type scale

| Element | Face | Size / line height | Case | Other |
|---|---|---|---|---|
| Date heading | Serif | 36px / 45px (26px on mobile) | As written | 1px solid black underline (border-bottom), centered |
| Section label ("SCREENINGS") | Sans | 24px | Uppercase | Purple, centered, 1px purple rule above and below, 14px padding |
| Venue name | Sans | 30px / 28px | Uppercase | Centered, margin-bottom 30px |
| Film title | Serif | 20px / 26px | As written | Underlined link |
| Series, meta, showtimes, small labels | Sans | 14px / 16px | Uppercase | Series purple |
| Notes, checkbox labels | Serif | 14px–20px | As written | |
| Nav items (rail) | Sans | 20px | Uppercase | Active item purple |
| Site name (rail) | Sans | 24px / 1 | Uppercase | Two lines: SEATTLE / SCREENS |
| Footer | Sans | 12px | Uppercase | |

### 9.3 Layout

- Page max width 1300px. Top margin 30px.
- **Left rail** (desktop, 150px wide, `position: sticky; top: 0`): site name as plain text (no logo), a one-line descriptor in 11px uppercase sans ("Screenings at Seattle-area theaters"), then nav items LISTINGS, VENUES, POSTS, SEARCH stacked, each separated by a 1px black rule, text centered. A 1px black vertical rule separates rail from content.
- **Content column:** the rest, with 10px side padding.
- **Venue block:** padding-top 20px, 2px dashed black border-bottom.
- **Screening grid:** flex-wrap, three equal columns at desktop. Each cell: padding 0 20px, margin-bottom 20px, 2px dashed black border-bottom, and a 2px dashed black vertical divider between neighbors in a row (not on the last in a row). Cell is a column flexbox so showtimes sit at the bottom; minimum 50px gap between the meta/notes block and the showtimes.
- **Controls:** date row is `◀ date ▶` with solid black triangle buttons (CSS or inline SVG), 15px gaps. Checkboxes are custom: 22px square, 2px black border, filled black when checked, serif label.
- **Buttons** (venue filter shortcuts, search submit): 14px uppercase sans, 1px black border, white background; active/pressed state is black background with white text.

### 9.4 Responsive

| Width | Behavior |
|---|---|
| ≥ 1000px | Rail + 3-column grid |
| 640–999px | Rail + 2-column grid |
| < 640px | No rail. Top bar: site name left (18px), hamburger button right (three 2px black lines), 2px black rule below. Menu opens as a full-width stacked list. Single-column grid, no vertical dividers, cells full width. Date heading 26px with arrows at the edges. Venue name 30px wrapping to two lines. Tap targets at least 44px high. |

### 9.5 Accessibility floor

Semantic landmarks (`nav`, `main`, `footer`), one `h1` per page (the date, or page name), venue names as `h2`, titles as `h3`. Visible focus outline (2px purple). Buttons are real `<button>`s with `aria-label`s for the arrows and menu. Purple `#8B4DFF` on white is about 4.2:1: acceptable for the 24px label but under AA for 14px text. Keep it (it is the look being matched), and never use purple as the only carrier of meaning: stale lines say "OUT OF DATE", noted showtimes have asterisks.

### 9.6 Component list

Rail / mobile top bar and menu; date navigator; checkbox; venue filter panel; section label; venue block; screening cell; showtime row with footnotes; stale line; post cell; venue card; search input and result row; empty/error message; footer.

---

## 10. Tests

- `pytest` runs offline against `tests/fixtures/`. For every source: at least one fixture per page type, and tests asserting record count, one fully checked record (every field), and each cleaning rule the source uses (series split, format suffix, title case, skipped entries).
- Runner tests with fake sources: one raising, one returning invalid data, one returning empty, one healthy. Assert the healthy one is written, the others keep their old file, status.json is right, exit code 0.
- Build test: stale source file plus fresh one both appear in screenings.json; records older than 7 days are dropped.
- The workflow does not run tests on the schedule. Add a separate lightweight `test.yml` only if it takes under 15 minutes to set up; otherwise tests are run locally.

---

## 11. Acceptance criteria

Phase 5 reviews against this list.

**Data**
1. `python -m scrapers.run` followed by `python -m scrapers.build` produces valid `screenings.json`, `posts.json` and `status.json` with screenings for all 9 non-Regal venues (given each has shows scheduled).
2. Every record passes section 3.2 validation; no title contains a series prefix, format suffix, or date text.
3. Spot check: for 3 venues, one day's listings on the site match the venue's own site exactly (titles and times).
4. Forcing one source to fail (e.g. bad URL) leaves its previous data on the site, marks its venues out of date, and every other source updates.
5. `pytest` passes offline.
6. Rental slots (Beacon) and workshops (NWFF) do not appear; North Bend comedy appears labelled "Live event".

**Automation**
7. The workflow runs on schedule and from the "Run workflow" button, commits data, and deploys to Pages without manual steps.
8. A run with one failing source still finishes green and publishes.

**Site**
9. Listings page shows the full date, venue groups, and all fields in section 7.3; previous/next navigation works and updates the URL; `?date=` links load directly.
10. Venue filter hides and shows venues, has a one-click Regal toggle, and persists across reloads.
11. "On Film" shows only film-print screenings.
12. Search finds upcoming screenings by title, director, series and venue.
13. Venues page lists all 12 venues with address, neighborhood, link and last-updated time.
14. Posts page shows a combined NWFF + SIFF feed, newest first, with no Regal, Tasveer or social-media content.
15. Out-of-date venues are marked on both the listings and venues pages.
16. With no `regal.json`, the site shows no errors and no Regal listings; the Regals still appear on the Venues page with links.
17. Every page has the noindex meta tag and the exact footer line. The words "Screen Slate" appear nowhere else in `docs/`. No store, Patreon, newsletter, submit form, social links, membership prompts, accounts, reviews or ratings.
18. Design matches section 9: two typefaces, black/white/purple only, dashed dividers, 3/2/1-column grid at the stated widths.
19. On a 375px-wide phone: no horizontal scrolling, menu works, tap targets at least 44px, text readable without zoom.
20. All asset and data paths are relative; the site works at `https://<username>.github.io/seattle-screens/` and from `python -m http.server -d docs`.

**Regal add-on (only if built)**
21. `local/run_regal.bat` produces Regal listings for 3 venues, pushes, and the site updates. Stopping the task for 36+ hours marks the Regals out of date.

---

## 12. Build order

Ranked by value for effort. Stop and show Elijah the result after each stage.

| Stage | Work | Effort | Why here |
|---|---|---|---|
| 0 | Setup with Elijah (section 13): Git, GitHub account, repository, first push. | S | Nothing ships without it. |
| 1 | `models.py`, `http.py`, `util.py`, runner, build, tests for runner and build. Confirm the Phase 3 SIFF scraper runs inside this structure. | M | The frame every scraper plugs into. |
| 2 | Front end: listings page, venues page, shared CSS/JS, against real SIFF data. Mobile layout included. | M | Usable site with 3 venues. |
| 3 | Workflow + Pages deploy. Site is live and self-updating. | S | Live early; every later scraper appears automatically. |
| 4 | Scrapers: `beacon`, `nwff`, `majestic_bay` (the three easy ones, and the core of the repertory listings). | M | Most value per hour. |
| 5 | Search page; venue filter; "On Film"; stale markers. | S | Cheap once data exists. |
| 6 | Scrapers: `north_bend`, `tasveer`, `admiral`. | M | Harder sources, less central. |
| 7 | Posts: `nwff`, `siff`, posts page. | S | Lowest-value feature in the brief. |
| 8 | Regal PC scraper. | M | Optional; needs installs on Elijah's PC. Ask before starting. |

If a source in stage 6 takes more than about half a day, stop, report what blocks it, and move on.

---

## 13. Setup steps to walk Elijah through (stage 0)

Explain each in plain language and ask before doing it.

1. **Git** on the PC (the tool that tracks file versions and sends them to GitHub). Check whether it is installed before proposing an install.
2. **GitHub account** (the site that hosts the code and runs the scheduled jobs). Ask whether he has one.
3. **Repository** named `seattle-screens`, **public** (required for free Pages; say plainly that the code and data will be publicly visible, though unlisted in search engines).
4. **OneDrive caution:** the project folder is inside OneDrive. Git works there, but OneDrive syncing the hidden `.git` folder can cause conflicts or slow syncs. Tell Elijah, and recommend either excluding the folder from OneDrive sync or accepting the risk; do not move the folder without asking.
5. **First push**, then in the repository's Settings → Pages, set Source to "GitHub Actions".
6. **Actions permissions:** Settings → Actions → General → Workflow permissions → "Read and write permissions".
7. Run the workflow once from the Actions tab ("Run workflow") and open the site URL together.

No tokens are needed for the GitHub Actions path. Only the Regal PC scraper needs stored Git credentials; ask before setting that up.

---

## 14. Known gaps (accepted)

- Format will be blank for most Beacon, Tasveer, Admiral and North Bend listings. Not a defect.
- Director and year are missing for Admiral and most North Bend listings. Do not add a third-party film database to fill them.
- Tasveer publishes about 6 days ahead; North Bend and Regal data are thinner than the rest.
- Scheduled runs may start late; listings can be several hours behind a venue's last-minute change.
- Admiral (decided with Elijah 2026-11-15): its server returns 403 to GitHub Actions for both the home page and the showtimes API. The Admiral stays on the Venues page marked out of date and does not appear on Listings. If the Regal PC scraper (stage 8) is built, add the Admiral to it.
- Multi-film programs (shorts blocks) are shown as a single title, as the venue names them.
