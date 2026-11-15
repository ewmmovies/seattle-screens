# Seattle Screens — Phase 1 Survey

Surveyed 2026-11-14 in a real browser, then re-tested each source with a plain automated fetch from a datacenter (the closest stand-in for GitHub Actions available without a repo).

## Summary

- 12 listings come from **8 distinct sources**. The three SIFF venues are one page; the three Regals are one site. Every other theater is on a different platform, so there is little scraper reuse.
- 7 of 8 sources are collectable from GitHub Actions with plain HTTP requests. No headless browser needed for any of them.
- **Regal is not collectable from GitHub Actions.** See the Regal section.
- Only 3 theaters publish news (NWFF, SIFF, Tasveer). The Posts feed will be thin.

## Survey table

| Venue | Schedule source | Method | Fields available | News source | Difficulty | Risks |
|---|---|---|---|---|---|---|
| Historic Admiral | farawayentertainment.com, built on the Mobile Moviegoing platform | JSON API, POST to `api-v3.mobilemoviegoing.cloud/include/app/getShowtimesByDayDisplay.php` with `{eid, pos_route, date, mode:"now", location:"00001-00001-00002"}`. One request per day. | Title, synopsis, runtime, rating, showtimes, per-showtime notes (open captions, discount pricing). Advance-ticket titles listed separately. No director, year or format on the page. | None | M | Response JSON shape not yet inspected (see Open items). Undocumented API; `eid` is a site key embedded in page JS and could change. Site is shared with 4 other Far Away cinemas, so the location code is what selects the Admiral. |
| Northwest Film Forum | nwfilmforum.org (WordPress) | Server-rendered HTML. `/calendar/?start=YYYY-MM-DD` gives one week; `/films/<slug>/` gives detail. | Title, series, director, country, year, runtime, language, all showtimes, prices, ticket link (Eventive), type (Film / Event / Workshop), tags (On Film, Visiting Artist, Live Music, Discussion). | `/news/` HTML page. The site RSS feed exists but its newest item is from 2021, and `/news/feed/` is not a feed. | S | One extra request per film for director/year (cache by slug). Non-film events and workshops share the calendar and need filtering. |
| Tasveer Film Center | filmcenter.tasveer.org, built on the INDY Cinema Group platform | GraphQL at `/graphql` (`showingsForDate`, `datesWithShowing`). The showtimes page HTML also carries titles and times as a fallback. | Title, director, cast, runtime, release date, rating, country, language, showtimes (UTC), badges (Open Captions, subtitled, accessibility, Q&A in title), showing ID for ticket link. No format. | tasveer.org (parent organization, WordPress): RSS at `/feed/`, plus an events iCal. | M | Schedule only runs about 6 days ahead. GraphQL query text must be copied from the site's JS. Titles carry suffixes like "(2026, Spain, Spanish)" that need cleaning. The tasveer.org feed refused an automated fetch; it may block bots, and its content is mostly festival news, not Film Center news. |
| Majestic Bay | majesticbay.com (Gatsby site on Boxoffice / Webedia) | JSON API, plain GET: `/api/gatsby-source-boxofficeapi/schedule?from=&to=&theaters=`, `/scheduledMovies?theaterId=X05TV`, `/movies?ids=` | Title, directors, cast, runtime, release date, rating, distributor, synopsis, format tag (e.g. `Format.Projection.Digital`), showtimes, screen, per-showtime ticket link (Veezi). | None | S | Undocumented API. Cleanest source of the set. |
| SIFF Cinema Uptown / Downtown / Film Center | siff.net, one shared calendar | Server-rendered HTML: `/calendar?view=list&date=YYYY-MM-DD` covers all three venues for a day. Each showtime button embeds a JSON blob (`data-screening`). | Title, country, year, runtime, director, venue, showtime (epoch), showtime ID, sold-out percentage, notes (voucher alerts). Series appears as a title prefix ("Romanian Film Festival Seattle: ..."); format appears in the title text ("Paper Tiger (35mm)"). | `/media/blog` and `/media/news-x39250`, both HTML. No RSS. | M | One request per day of horizon (14 days = 14 requests). Series and format must be parsed out of title text. Ticket link: the Elevent showtime ID is available but the direct URL pattern still has to be worked out; the film detail page is the safe fallback link. |
| The Beacon | thebeacon.film (Astro, static HTML) | Server-rendered HTML. The entire calendar is on `/calendar` in one request; `/calendar/movie/<slug>` gives detail with JSON-LD. | Title, year, director, cast, runtime, description, showtimes, sold-out flag, ticket link (`?showtime=` ID). Format not stated in structured form. Series live on separate `/series` and `/programs` pages. | None | S | "RENT THE BEACON" private-rental slots sit in the calendar and must be dropped. Site looks recently rebuilt, so markup may still shift. One request per film for detail (cache). |
| North Bend Theatre | tix.northbendtheatre.com (ThunderTix ticketing). The main site is a Square Online page with free-text listings only. | Server-rendered HTML. One event per showtime, grouped by category. | Title, time, category (works as series: "Analog Anomalies", "Love & War", "Mountain Film Festival"), ticket link. No director, year, runtime or format. | None | M | The date lives in free text inside the event title ("(Sunday Nov. 15th @3pm)") with inconsistent formatting and no year; an event page may hold a cleaner date (not yet checked). Live comedy and other non-film events are mixed in. |
| Regal Thornton Place / Cinebarre Mountlake Terrace / Meridian | regmovies.com (Next.js behind Cloudflare) | In a real browser, each theatre page embeds all data as JSON (`__NEXT_DATA__`). Automated fetch is blocked. | Title, directors, cast, runtime, rating, opening date, studio, showtimes for about 48 dates, format and attribute tags (Standard, 4DX, Open Captioned, subtitled). | Excluded by the brief | L | Blocked for automated access. See below. |

## Regal: plain answer

Automated collection from GitHub Actions is not possible with a normal scraper. The theatre page loads fine in a real browser and contains everything needed, but the same URL fetched from a datacenter was refused, and the page loads Cloudflare's challenge script. A headless browser running in GitHub Actions would most likely be refused too, because the block is tied to datacenter IP addresses and bot fingerprinting; that specific case was not tested because there is no repo yet.

Fallbacks, ranked by value for effort:

| Option | What it means | Effort | Trade-off |
|---|---|---|---|
| A. Link out only | Regals appear on the Venues page with a link to their showtimes page; no Regal listings on the daily page. | S | Loses Regal listings and makes the "hide Regals" filter unnecessary. Zero maintenance. |
| B. Scrape from your own PC | A scheduled task on your Windows machine opens the three Regal pages in a real browser, saves the JSON and pushes it to the repo. The site treats it like any other venue, including the "out of date" marker when the PC was off. | M | Works because it comes from a home connection. Depends on the PC being on; needs Git credentials stored locally. Could still break if Regal tightens its checks. |
| C. Third-party showtime source | Fandango or similar, or a paid showtimes API. | L | The free ones are bot-protected the same way; the reliable ones cost money. Not worth it. |

Recommendation: spec the site so it is complete without Regal (A), with B as an optional add-on built last. The 9 non-Regal listings are the point of the site, and B is the only piece that needs anything installed on your computer.

## Posts feed

| Source | Method | Note |
|---|---|---|
| NWFF | Scrape `/news/` HTML | Press-release style, a few per month |
| SIFF | Scrape `/media/blog` and `/media/news-x39250` HTML | Blog is active (film notes, monthly previews) |
| Tasveer | RSS at tasveer.org/feed/ | Parent organization's feed; refused an automated fetch, so it may not work from Actions |
| Admiral, Majestic Bay, Beacon, North Bend | None | No news or blog page exists |

Three sources, two of them HTML scraping, one uncertain. This is the lowest value-for-effort feature in the brief; it belongs last in the build order.

## Field coverage against the brief

| Field | Good | Partial | Missing |
|---|---|---|---|
| Title, showtimes | All | | |
| Ticket link | NWFF, Majestic Bay, Beacon, North Bend, Tasveer | SIFF, Admiral (film page link as fallback) | |
| Director | NWFF, Tasveer, Majestic Bay, SIFF, Beacon | | Admiral, North Bend |
| Year | NWFF, SIFF, Beacon | Tasveer, Majestic Bay (release date) | Admiral, North Bend |
| Runtime | All but North Bend | | North Bend |
| Series / program | NWFF, North Bend (category) | SIFF (title prefix), Beacon (separate pages) | Admiral, Majestic Bay, Tasveer |
| Format (35mm etc.) | Majestic Bay (tag) | SIFF (in title text), NWFF ("On Film" tag only) | Beacon, Tasveer, Admiral, North Bend |
| Notes | Admiral, Tasveer, SIFF, NWFF | | |

Format is the weak field. Outside SIFF and NWFF it will mostly be blank or "Digital".

## Screen Slate design notes (for Phase 2)

- Type: headings, dates and film titles in Cooper Light BT (a commercial font; the site cannot copy the font files, so a free look-alike serif is needed). Everything else in Helvetica Neue / Helvetica / Arial.
- Color: black on white, one accent, purple `#8B4DFF` (series names, section labels, showtimes with notes, rules).
- Listings page: fixed left rail with stacked nav items separated by rules; centered date heading (36px serif, underlined) with arrow buttons either side; "On Film" and "Upcoming" checkboxes; venue name centered in 30px uppercase sans; screenings in a 3-column grid with dashed dividers; each cell is series (14px uppercase purple), title (20px serif, underlined link), meta line (14px uppercase: director, year, runtime, format), showtimes pinned to the bottom of the cell; asterisked footnotes for notes.
- Mobile layout and the Venues page still need to be captured in Phase 2.

## Open items

1. **Folder path.** `~/Projects/seattle-screens` does not exist. The folder is at `C:\Users\elija\OneDrive\Documents\Projects\seattle-screens` (empty), which matches the Project instructions; this file was saved there. A separate `C:\Users\elija\seattle-screenings` folder also exists and was not touched.
2. **Admiral API response not inspected.** Reading the JSON directly was blocked by a safety check on this session, so the Admiral's field list comes from the rendered page. The API's exact shape gets confirmed when its scraper is written.
3. **Regal decision needed** before Phase 2: A (link out), or A plus B (PC-based scraper).
4. **North Bend non-film events:** include with a label, or drop.
5. **Tasveer posts:** keep the parent-organization feed if it works, or drop Tasveer from Posts.
