/* Search page (SPEC.md section 7.4). Searches every venue, ignoring the listings filter. */
"use strict";

(() => {
  const { el } = SS;
  const form = document.getElementById("search-form");
  const input = document.getElementById("q");
  const results = document.getElementById("results");

  let rows = []; // [{ screening, venue, haystack }]
  let venueRank = new Map();

  /** Lower case, accents and apostrophes removed: "Maud’s" and "mauds" match; "Éric" and "eric" match. */
  function normalize(text) {
    return String(text || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .replace(/['’‘`]/g, "")
      .toLowerCase();
  }

  function words(query) {
    return normalize(query).split(/\s+/).filter(Boolean);
  }

  function resultRow(s, venue) {
    const times = s.showtimes.map((t) => SS.formatTime(t.time)).join(" ");
    return el("li", {},
      el("a", { href: `index.html?date=${s.date}`, className: "small" },
        `${times} — `,
        el("span", { className: "result-title" }, s.title),
        ` — ${venue ? venue.name : s.venue_id}`,
        s.series ? [" — ", el("span", { className: "result-series" }, s.series)] : null));
  }

  function show(query) {
    const terms = words(query);
    if (!terms.length) {
      SS.showMessage(results, "Search by title, director, series or theater.");
      return;
    }
    const matches = rows.filter((row) => terms.every((term) => row.haystack.includes(term)));
    if (!matches.length) {
      SS.showMessage(results, "No upcoming screenings match.");
      return;
    }
    matches.sort((a, b) =>
      a.screening.date.localeCompare(b.screening.date)
      || a.screening.showtimes[0].time.localeCompare(b.screening.showtimes[0].time)
      || (venueRank.get(a.screening.venue_id) ?? 99) - (venueRank.get(b.screening.venue_id) ?? 99));

    const days = new Map();
    for (const row of matches) {
      if (!days.has(row.screening.date)) days.set(row.screening.date, []);
      days.get(row.screening.date).push(row);
    }
    const count = el("p", { className: "small search-count" },
      `${matches.length} ${matches.length === 1 ? "screening" : "screenings"}`);
    results.replaceChildren(count, ...[...days].map(([date, dayRows]) =>
      el("section", { className: "result-day", "aria-label": SS.formatShortDate(date) },
        el("h2", { className: "result-date serif" }, SS.formatShortDate(date)),
        el("ul", { className: "results" }, dayRows.map((r) => resultRow(r.screening, r.venue))))));
  }

  function syncUrl(query) {
    const url = query ? `?q=${encodeURIComponent(query)}` : location.pathname;
    history.replaceState(null, "", url);
  }

  async function init() {
    const initial = new URLSearchParams(location.search).get("q") || "";
    input.value = initial;
    try {
      const [venues, screenings] = await Promise.all([
        SS.loadJSON("data/venues.json"),
        SS.loadJSON("data/screenings.json"),
      ]);
      const byId = new Map(venues.map((v) => [v.id, v]));
      venueRank = new Map(venues.map((v, i) => [v.id, i]));
      const today = SS.todayPT();
      rows = screenings.screenings
        .filter((s) => s.date >= today && s.showtimes && s.showtimes.length)
        .map((s) => {
          const venue = byId.get(s.venue_id);
          return {
            screening: s,
            venue,
            haystack: normalize([s.title, ...(s.directors || []), s.series, venue && venue.name].join(" | ")),
          };
        });
    } catch (error) {
      SS.showLoadError(results, error);
      return;
    }

    let timer = null;
    input.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        syncUrl(input.value.trim());
        show(input.value);
      }, 150);
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      syncUrl(input.value.trim());
      show(input.value);
    });
    show(initial);
  }

  init();
})();
