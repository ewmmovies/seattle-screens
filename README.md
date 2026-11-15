# Seattle Screens

A personal listings site for screenings at Seattle-area theaters. Not affiliated with Screen Slate. SPEC.md is the source of truth for how it works.

## How it fits together

1. **Scrapers** (`scrapers/sources/`) read each theater's website and return screenings.
2. **The runner** (`python -m scrapers.run`) runs every scraper. Good results go to `data/sources/<source>.json`. A failed scraper keeps its previous data and is marked out of date in `data/status.json`.
3. **The build** (`python -m scrapers.build`) merges everything in `data/` into the files the website reads, in `docs/data/`.
4. **The website** (`docs/`) is plain HTML, CSS and JavaScript. GitHub Pages publishes it.

A scheduled GitHub Actions job runs steps 2 and 3 four times a day and republishes the site.

## Commands

```
pip install -r requirements.txt
python -m scrapers.run                   # every source
python -m scrapers.run --source siff     # one source
python -m scrapers.run --save-fixtures   # also save real pages for tests
python -m scrapers.build                 # rebuild docs/data/
pytest                                   # offline tests
python -m http.server -d docs            # view the site at http://localhost:8000
```

## Adding a source

Copy the layout of `scrapers/sources/siff.py`: constants, pure parsing functions, cleaning functions, then `fetch(ctx)`. Add its venues to `docs/data/venues.json` first. Save fixtures with `--save-fixtures` and write `tests/test_<source>.py` against them.
