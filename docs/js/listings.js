/* Daily listings page (SPEC.md sections 7.2 and 7.3). */
"use strict";

(() => {
  const { el } = SS;
  const PRINT_FORMATS = new Set(["35mm", "70mm", "16mm", "Film"]);
  const HIDDEN_KEY = "ss.hiddenVenues";

  const dom = {
    content: document.getElementById("listings"),
    prev: document.getElementById("prev-day"),
    next: document.getElementById("next-day"),
    dateButton: document.getElementById("date-button"),
    dateInput: document.getElementById("date-input"),
    onFilm: document.getElementById("on-film"),
    venuesButton: document.getElementById("venues-button"),
    panel: document.getElementById("venue-filter"),
    venueList: document.getElementById("venue-checkboxes"),
    regalButton: document.getElementById("toggle-regal"),
    allButton: document.getElementById("show-all"),
  };

  let data = null; // { venues, screenings, status, range }
  let current = null; // "YYYY-MM-DD"

  // ------------------------------------------------------------- filters (7.2)
  // Hidden venues persist in localStorage when the browser allows it; otherwise
  // they live in memory for the visit. "On Film" is for this visit only.

  const hidden = loadHidden();
  let onFilmOnly = false;

  function loadHidden() {
    try {
      const saved = JSON.parse(localStorage.getItem(HIDDEN_KEY) || "[]");
      return new Set(Array.isArray(saved) ? saved.filter((id) => typeof id === "string") : []);
    } catch {
      return new Set();
    }
  }

  function saveHidden() {
    try { localStorage.setItem(HIDDEN_KEY, JSON.stringify([...hidden])); } catch { /* memory only */ }
  }

  function regalIds() {
    return data.venues.filter((v) => v.group === "regal").map((v) => v.id);
  }

  function updateFilterControls() {
    const known = data.venues.filter((v) => hidden.has(v.id)).length;
    dom.venuesButton.textContent = known ? `Venues (${known} hidden)` : "Venues";
    for (const box of dom.venueList.querySelectorAll("input")) box.checked = !hidden.has(box.value);
    const allRegalHidden = regalIds().every((id) => hidden.has(id));
    dom.regalButton.textContent = allRegalHidden ? "Show Regal" : "Hide Regal";
  }

  function filtersChanged() {
    saveHidden();
    updateFilterControls();
    render();
  }

  function initFilters() {
    dom.venueList.replaceChildren(...data.venues.map((venue) => el("li", {},
      el("label", { className: "checkbox serif" },
        el("input", {
          type: "checkbox",
          value: venue.id,
          onchange: (event) => {
            if (event.target.checked) hidden.delete(venue.id);
            else hidden.add(venue.id);
            filtersChanged();
          },
        }),
        venue.name))));

    dom.venuesButton.addEventListener("click", () => {
      const open = dom.panel.hidden;
      dom.panel.hidden = !open;
      dom.venuesButton.setAttribute("aria-expanded", String(open));
    });
    dom.panel.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        dom.panel.hidden = true;
        dom.venuesButton.setAttribute("aria-expanded", "false");
        dom.venuesButton.focus();
      }
    });
    dom.regalButton.addEventListener("click", () => {
      const ids = regalIds();
      const allHidden = ids.every((id) => hidden.has(id));
      for (const id of ids) {
        if (allHidden) hidden.delete(id);
        else hidden.add(id);
      }
      filtersChanged();
    });
    dom.allButton.addEventListener("click", () => {
      hidden.clear();
      filtersChanged();
    });
    dom.onFilm.addEventListener("change", () => {
      onFilmOnly = dom.onFilm.checked;
      render();
    });
    updateFilterControls();
  }

  // ------------------------------------------------------------- one screening

  function metaLine(s) {
    const parts = [];
    if (s.directors && s.directors.length) parts.push(s.directors.join(" & "));
    if (s.year) parts.push(String(s.year));
    if (s.runtime_min) parts.push(`${s.runtime_min}M`);
    if (!parts.length && !s.format) return null;
    const line = el("p", { className: "small meta" }, parts.join(", "));
    if (s.format) {
      // Keep the format and its film-strip mark together on one line.
      line.append(parts.length ? ", " : "",
        el("span", { className: "nowrap" }, s.format, PRINT_FORMATS.has(s.format) ? SS.filmGlyph() : null));
    }
    return line;
  }

  function seriesLine(s) {
    let text = s.series || "";
    if (s.kind === "event") text = text ? `${text} · Live event` : "Live event";
    return text ? el("p", { className: "small series" }, text) : null;
  }

  function titleNode(s) {
    const url = SS.safeUrl(s.url);
    return el("h3", { className: "title serif" }, url ? SS.externalLink(url, s.title) : s.title);
  }

  function showtimeRow(s) {
    // Each distinct note gets *, **, *** in order of first appearance.
    const marks = new Map();
    for (const show of s.showtimes) {
      if (show.note && !marks.has(show.note)) marks.set(show.note, "*".repeat(marks.size + 1));
    }
    const times = el("p", { className: "small times" });
    for (const show of s.showtimes) {
      const label = SS.formatTime(show.time) + (show.note ? marks.get(show.note) : "");
      const noted = show.note ? " noted" : "";
      if (show.sold_out) {
        times.append(el("span", { className: `sold-out${noted}`, title: "Sold out" }, label,
          el("span", { className: "visually-hidden" }, " (sold out)")));
        continue;
      }
      const href = SS.safeUrl(show.ticket_url) || SS.safeUrl(s.url);
      times.append(href
        ? el("a", { href, target: "_blank", rel: "noopener", className: noted.trim() || null }, label)
        : el("span", { className: noted.trim() || null }, label));
    }
    const wrap = el("div", { className: "showtimes" }, times);
    for (const [note, mark] of marks) {
      wrap.append(el("p", { className: "small footnotes" }, `${mark} ${note}`));
    }
    return wrap;
  }

  function cell(s) {
    const notes = (s.notes || []).length
      ? el("div", { className: "notes serif" }, s.notes.map((n) => el("p", {}, n)))
      : null;
    return el("li", { className: "cell" },
      el("div", { className: "cell-body" }, seriesLine(s), titleNode(s), metaLine(s), notes),
      showtimeRow(s));
  }

  // ------------------------------------------------------------- one day

  function venueBlock(venue, screenings) {
    const state = SS.sourceState(data.status, venue.source);
    const url = SS.safeUrl(venue.url);
    const name = el("h2", { className: "venue-name" }, url ? SS.externalLink(url, venue.name) : venue.name);
    const stale = state.stale ? el("p", { className: "stale" }, SS.staleText(state)) : null;
    return el("section", { className: "venue-block", "aria-label": venue.name },
      name, stale, el("ul", { className: "grid" }, screenings.map(cell)));
  }

  function byFirstShowtime(a, b) {
    const t = a.showtimes[0].time.localeCompare(b.showtimes[0].time);
    if (t) return t;
    if (a.kind !== b.kind) return a.kind === "film" ? -1 : 1;
    return a.title.localeCompare(b.title);
  }

  function render() {
    document.title = `${SS.formatLongDate(current)} — Seattle Screens`;
    dom.dateButton.textContent = SS.formatLongDate(current);
    dom.dateInput.value = current;
    dom.prev.disabled = current <= data.range.start;
    dom.next.disabled = current >= data.range.end;

    const today = data.screenings.filter((s) => s.date === current && (!onFilmOnly || PRINT_FORMATS.has(s.format)));
    const blocks = [];
    for (const venue of data.venues) {
      if (hidden.has(venue.id)) continue;
      const own = today.filter((s) => s.venue_id === venue.id && s.showtimes && s.showtimes.length);
      if (own.length) blocks.push(venueBlock(venue, own.sort(byFirstShowtime)));
    }
    if (blocks.length) dom.content.replaceChildren(...blocks);
    else SS.showMessage(dom.content, "No listings for this date.");
  }

  // ------------------------------------------------------------- navigation

  function go(date, { push = true } = {}) {
    if (!SS.isISODate(date)) return;
    current = date;
    if (push) history.pushState({ date }, "", `?date=${date}`);
    render();
  }

  function step(days) {
    const target = SS.addDays(current, days);
    if ((days < 0 && current <= data.range.start) || (days > 0 && current >= data.range.end)) return;
    go(target);
  }

  function initControls() {
    dom.prev.addEventListener("click", () => step(-1));
    dom.next.addEventListener("click", () => step(1));
    dom.dateInput.min = data.range.start;
    dom.dateInput.max = data.range.end;
    dom.dateButton.addEventListener("click", () => {
      try { dom.dateInput.showPicker(); } catch { dom.dateInput.focus(); }
    });
    dom.dateInput.addEventListener("change", () => {
      const value = dom.dateInput.value;
      if (SS.isISODate(value) && value >= data.range.start && value <= data.range.end) go(value);
    });
    document.addEventListener("keydown", (event) => {
      if (event.altKey || event.ctrlKey || event.metaKey) return;
      if (event.target.closest("input, textarea, select, .filter-panel")) return;
      if (event.key === "ArrowLeft") step(-1);
      if (event.key === "ArrowRight") step(1);
    });
    window.addEventListener("popstate", () => go(dateFromUrl(), { push: false }));
  }

  function dateFromUrl() {
    const asked = new URLSearchParams(location.search).get("date");
    return SS.isISODate(asked) ? asked : SS.todayPT();
  }

  async function init() {
    current = dateFromUrl();
    dom.dateButton.textContent = SS.formatLongDate(current);
    try {
      const [venues, screenings, status] = await Promise.all([
        SS.loadJSON("data/venues.json"),
        SS.loadJSON("data/screenings.json"),
        SS.loadJSON("data/status.json").catch(() => ({ sources: {} })),
      ]);
      data = { venues, screenings: screenings.screenings, range: screenings.range, status };
    } catch (error) {
      dom.prev.disabled = dom.next.disabled = true;
      SS.showLoadError(dom.content, error);
      return;
    }
    initControls();
    initFilters();
    render();
  }

  init();
})();
