/* Past Programs page (added 2026-11-15): the Beacon's past programs and past series
   in one list, newest month first (data/past.json). Blocks are laid out like the News
   page, each with the Beacon's own picture below the text, as on the Listings row.
   Pictures load from the Beacon's servers; if one fails, the original file is tried,
   then the block goes without. */
"use strict";

(() => {
  const { el } = SS;
  const container = document.getElementById("past");

  function picture(item) {
    const primary = SS.safeUrl(item.image);
    const fallback = SS.safeUrl(item.image_fallback);
    if (!primary && !fallback) return null;
    const img = el("img", {
      className: "past-image",
      src: primary || fallback,
      alt: "",
      loading: "lazy",
      decoding: "async",
      referrerpolicy: "no-referrer",
    });
    img.addEventListener("error", () => {
      if (fallback && img.src !== fallback) img.src = fallback;
      else img.remove();
    });
    return img;
  }

  function cell(item) {
    const url = SS.safeUrl(item.url);
    const img = picture(item);
    return el("li", { className: "cell past-cell" },
      el("div", { className: "cell-body" },
        el("p", { className: "small post-source" }, [item.venue, item.kind].filter(Boolean).join(" · ")),
        el("h3", { className: "title serif" }, url ? SS.externalLink(url, item.title) : item.title),
        item.when ? el("p", { className: "small post-date" }, item.when) : null,
        item.description ? el("p", { className: "post-summary past-summary", title: item.description }, item.description) : null),
      img && url ? el("a", { href: url, target: "_blank", rel: "noopener", tabindex: "-1", "aria-hidden": "true",
        className: "past-image-link" }, img) : img);
  }

  async function show() {
    try {
      const items = ((await SS.loadJSON("data/past.json")).items || []).filter((x) => x && x.title);
      if (!items.length) SS.showMessage(container, "No past programs listed.");
      else container.replaceChildren(el("ul", { className: "grid post-grid past-grid" }, items.map(cell)));
    } catch (error) {
      SS.showMessage(container, "Past programs could not be loaded.");
      console.error(error);
    }
  }

  show();
})();
