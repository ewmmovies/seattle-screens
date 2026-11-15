/* Venues page (SPEC.md section 7.6). */
"use strict";

(() => {
  const { el } = SS;
  const content = document.getElementById("venues");

  function card(venue, status) {
    const state = SS.sourceState(status, venue.source);
    const url = SS.safeUrl(venue.url);
    const maps = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${venue.name}, ${venue.address}`)}`;
    const showtimes = venue.group === "regal" && SS.safeUrl(venue.showtimes_url)
      ? el("p", { className: "small card-links" }, SS.externalLink(venue.showtimes_url, "Showtimes"))
      : null;
    const updated = state.stale
      ? el("p", { className: "stale updated" }, SS.staleText(state))
      : el("p", { className: "small updated" }, `Last updated ${SS.formatStamp(state.lastSuccess)}`);
    return el("li", { className: "cell" },
      el("div", { className: "cell-body" },
        el("h2", { className: "title serif" }, url ? SS.externalLink(url, venue.name) : venue.name),
        el("p", { className: "small neighborhood" }, venue.neighborhood),
        el("p", { className: "address" }, SS.externalLink(maps, venue.address)),
        showtimes,
        updated));
  }

  async function init() {
    try {
      const [venues, status] = await Promise.all([
        SS.loadJSON("data/venues.json"),
        SS.loadJSON("data/status.json").catch(() => ({ sources: {} })),
      ]);
      content.replaceChildren(el("ul", { className: "grid card-grid" }, venues.map((v) => card(v, status))));
    } catch (error) {
      SS.showLoadError(content, error);
    }
  }

  init();
})();
