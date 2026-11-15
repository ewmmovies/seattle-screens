# Seattle Screens — Project Brief

A personal website for daily screening listings at Seattle-area theaters I've chosen, modeled on screenslate.com in function and visual style. It is NOT affiliated with Screen Slate: don't use its name, wordmark, logo or tagline. The footer must say: "A personal project. Not affiliated with Screen Slate."

---

## Theaters (12 listings, 11 venues)

| # | Venue | URL |
|---|---|---|
| 1 | Historic Admiral Theater | https://www.farawayentertainment.com/ |
| 2 | Northwest Film Forum | https://nwfilmforum.org/ |
| 3 | Tasveer Film Center | https://filmcenter.tasveer.org/home/ |
| 4 | Majestic Bay Theatre | https://www.majesticbay.com/ |
| 5 | SIFF Cinema Uptown | https://www.siff.net/cinema/cinema-venues/siff-cinema-uptown |
| 6 | SIFF Cinema Downtown | https://www.siff.net/cinema/cinema-venues/siff-cinema-downtown |
| 7 | SIFF Film Center | https://www.siff.net/cinema/cinema-venues/siff-film-center |
| 8 | The Beacon | https://thebeacon.film/calendar |
| 9 | North Bend Theatre | https://www.northbendtheatre.com/ |
| 10 | Regal Thornton Place | https://www.regmovies.com/theatres/regal-thornton-place-1937 |
| 11 | Regal Cinebarre Mountlake Terrace | https://www.regmovies.com/theatres/regal-cinebarre-mountlake-1958 |
| 12 | Regal Meridian | https://www.regmovies.com/theatres/regal-meridian-4dx-1931 |

Notes: The three SIFF venues share one site. The three Regals share one chain site, which probably blocks automated access.

---

## Features

**Keep from Screen Slate**
- Daily listings grouped by venue, with previous/next day navigation and the full date as a heading
- Fields for each screening: title, series or program name, director, year, runtime, format (35mm, 70mm, DCP, digital), showtimes, notes (Q&A, intro, open captions, special event), and a ticket link
- A venues page (address, neighborhood, link)
- Search across upcoming listings
- Venue filters, so I can hide the Regals on days I only want repertory screenings

**Replace "Articles" with "Posts"**
- A combined feed of news, blog posts and announcements from each independent theater's own website or RSS feed
- No Instagram or other social-media scraping
- Leave the Regals out of this feed

**Drop**
- Store, Patreon, newsletter, submit form, social links, membership prompts
- No user accounts and no review or rating features

---

## Architecture (decided)

- Host on GitHub Pages as a static site, free tier
- GitHub Actions runs the scrapers on a schedule (suggest how often) and on demand through a manual "run now" trigger
- The scrapers write standardized JSON into the repo, and the front end reads it
- A "last updated" time per venue, shown on the site
- If one venue's scraper fails, the site keeps that venue's last good data and marks it as out of date; the run continues for every other venue
- Add noindex tags so search engines don't list the site

---

## Design

Study screenslate.com directly in the browser. Match its layout, information density, type hierarchy, spacing, colors and restrained feel as closely as possible, using the Seattle Screens name and no Screen Slate branding. Must work well on a phone.

---

## Phases

**Phase 1: Survey (Fable; read-only, build nothing)**
For each theater, find where its schedule comes from (its own HTML, a ticketing platform, a JSON API, iCal or RSS) and whether a news or blog page or RSS feed exists. Note which theaters share a source.
Return a table: venue | schedule source | method | fields available | news source | difficulty (S/M/L) | risks.
Test the Regal site specifically and say plainly whether automated collection is possible, and if not, what the fallback is.

**Phase 2: Spec (Fable)**
Write SPEC.md for a different model (Claude Opus) to build from without asking questions. Cover:
- repository structure
- a standard data model for screenings, venues and posts
- the scraper interface and how errors are handled
- the GitHub Actions workflow
- detailed design notes (fonts, colors, spacing, component list)
- acceptance criteria
- a phased build order, ranked by value for effort

**Phase 3: Reference scraper (Fable)**
Build and test one scraper against a live site, choosing the hardest source likely to work. It will be the pattern every other scraper copies.

**Phase 4: Build (Opus)**
Build everything in SPEC.md, following its build order and copying the reference scraper's pattern.

**Phase 5: Review (Fable)**
Check the finished repo against SPEC.md's acceptance criteria.

Stop after each phase and show me the results before continuing.
