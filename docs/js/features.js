/* "At the Beacon" block on the listings page (added 2026-11-15).
   Up to four of the Beacon's current series and programs (series first), each linking
   to its page on thebeacon.film. Images are the Beacon's own, loaded from its servers. */
"use strict";

(() => {
  const { el } = SS;
  const section = document.getElementById("features");
  const rule = document.getElementById("features-rule");
  const lead = document.getElementById("feature-lead");
  const row = document.getElementById("feature-row");

  function image(item) {
    const primary = SS.safeUrl(item.image);
    const fallback = SS.safeUrl(item.image_fallback);
    if (!primary && !fallback) return null;
    const img = el("img", {
      className: "feature-image",
      src: primary || fallback,
      alt: "",
      loading: "lazy",
      decoding: "async",
      referrerpolicy: "no-referrer",
    });
    img.addEventListener("error", () => {
      if (fallback && img.src !== fallback) img.src = fallback;
      else img.remove(); // no picture rather than a broken one
    });
    return img;
  }

  function labels(item) {
    return [
      el("span", { className: "side-label kind" }, item.kind || "The Beacon"),
      el("span", { className: "side-label when" }, item.when || ""),
    ];
  }

  function leadItem(item) {
    const [kind, when] = labels(item);
    return el("a", { className: "feature-link feature-lead", href: item.url, target: "_blank", rel: "noopener" },
      el("h3", { className: "feature-title serif" }, item.title),
      el("div", { className: "feature-frame" }, kind, image(item) || el("span"), when),
      item.byline ? el("p", { className: "byline" }, item.byline) : null);
  }

  function smallItem(item) {
    const [kind, when] = labels(item);
    return el("li", {},
      el("a", { className: "feature-link feature-small", href: item.url, target: "_blank", rel: "noopener" },
        el("div", { className: "feature-frame" },
          kind,
          el("div", { className: "feature-middle" },
            el("h3", { className: "feature-title serif" }, item.title),
            item.byline ? el("p", { className: "byline" }, item.byline) : null),
          when),
        image(item)));
  }

  async function init() {
    let items;
    try {
      items = ((await SS.loadJSON("data/features.json")).features || [])
        .filter((f) => f && f.title && SS.safeUrl(f.url))
        .slice(0, 4);
    } catch (error) {
      return; // the block is optional: without data it simply stays hidden
    }
    if (!items.length) return;
    lead.replaceChildren(leadItem(items[0]));
    row.replaceChildren(...items.slice(1).map(smallItem));
    row.hidden = items.length < 2;
    section.hidden = false;
    rule.hidden = false;
  }

  init();
})();
