/* Happening Now block on the listings page (reworked 2026-11-15).

   Top slot: the Beacon's current series (or a now-playing Beacon program if it has
   none), changed only with the small arrows under the right-hand label.
   Row: SIFF programs/events, NWFF festivals/series and Beacon programs that are on
   now. Three tiles (one on phones); every 7 seconds the row pushes one tile from
   right to left. Arrows step it by hand. It pauses while the pointer or keyboard
   focus is on it, with the pause button, when the tab is hidden, and never moves on
   its own for people whose device asks for reduced motion.
   Images are the theaters' own, loaded from their servers. */
"use strict";

(() => {
  const { el } = SS;
  const STEP_MS = 7000;
  const SLIDE_MS = 650;
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const phone = window.matchMedia("(max-width: 639px)");

  const dom = {
    section: document.getElementById("features"),
    rule: document.getElementById("features-rule"),
    lead: document.getElementById("feature-lead"),
    carousel: document.getElementById("feature-carousel"),
    track: document.getElementById("feature-row"),
    controls: document.getElementById("row-controls"),
    prev: document.getElementById("row-prev"),
    next: document.getElementById("row-next"),
    pause: document.getElementById("row-pause"),
  };

  // ------------------------------------------------------------- shared pieces

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

  const kindLabel = (item) => [item.venue, item.kind].filter(Boolean).join(" · ") || "Happening now";
  const link = (item, attrs, ...children) =>
    el("a", { href: item.url, target: "_blank", rel: "noopener", ...attrs }, ...children);

  // ------------------------------------------------------------- top slot

  let leadItems = [];
  let leadIndex = 0;

  function renderLead() {
    const item = leadItems[leadIndex];
    const many = leadItems.length > 1;
    const side = el("div", { className: "lead-side" },
      el("span", { className: "side-label when" }, item.when || ""),
      many ? el("div", { className: "lead-controls" },
        el("button", { className: "mini-button mini-prev", type: "button", "aria-label": "Previous series",
          onclick: () => stepLead(-1) }),
        el("span", { className: "lead-count", "aria-live": "polite" }, `${leadIndex + 1} / ${leadItems.length}`),
        el("button", { className: "mini-button mini-next", type: "button", "aria-label": "Next series",
          onclick: () => stepLead(1) })) : null);
    dom.lead.replaceChildren(el("div", { className: "feature-lead" },
      el("h3", { className: "feature-title serif" }, link(item, { className: "feature-link" }, item.title)),
      el("div", { className: "feature-frame" },
        el("span", { className: "side-label kind" }, kindLabel(item)),
        link(item, { className: "feature-link", tabindex: "-1", "aria-hidden": "true" }, image(item) || el("span")),
        side),
      el("div", { className: "feature-text" },
        item.description
          ? el("p", { className: "feature-description serif" }, item.description)
          : (item.byline ? el("p", { className: "byline" }, item.byline) : null),
        item.months ? el("p", { className: "byline feature-months" }, `Scheduled ${item.months}`) : null)));
  }

  function stepLead(delta) {
    leadIndex = (leadIndex + delta + leadItems.length) % leadItems.length;
    renderLead();
    const again = dom.lead.querySelector(delta < 0 ? ".mini-prev" : ".mini-next");
    if (again) again.focus(); // keep keyboard focus on the arrow after re-rendering
  }

  // ------------------------------------------------------------- rotating row

  function tile(item) {
    return el("li", { className: "carousel-tile" },
      link(item, { className: "feature-link feature-small" },
        el("div", { className: "feature-frame" },
          el("span", { className: "side-label kind" }, kindLabel(item)),
          el("div", { className: "feature-middle" },
            el("h3", { className: "feature-title serif" }, item.title),
            item.byline ? el("p", { className: "byline" }, item.byline) : null),
          el("span", { className: "side-label when" }, item.when || "")),
        image(item)));
  }

  const row = { count: 0, busy: false, paused: false, hover: false, focus: false, timer: null };

  const perView = () => (phone.matches ? 1 : 3);
  const canMove = () => row.count > perView();
  const shift = () => `translateX(${-100 / perView()}%)`;

  function slide(direction) {
    if (row.busy || !canMove()) return;
    const instant = reduceMotion.matches;
    row.busy = true;
    const track = dom.track;
    const finish = () => {
      if (direction > 0) track.appendChild(track.firstElementChild); // the tile that left goes to the back
      track.style.transition = "none";
      track.style.transform = "translateX(0)";
      void track.offsetWidth; // apply before the next move
      row.busy = false;
    };
    if (direction < 0) { // bring the last tile in from the left
      track.style.transition = "none";
      track.insertBefore(track.lastElementChild, track.firstElementChild);
      track.style.transform = shift();
      void track.offsetWidth;
    }
    if (instant) {
      if (direction > 0) finish();
      else { track.style.transform = "translateX(0)"; row.busy = false; }
      return;
    }
    track.style.transition = `transform ${SLIDE_MS}ms ease`;
    track.style.transform = direction > 0 ? shift() : "translateX(0)";
    window.setTimeout(direction > 0 ? finish : () => { row.busy = false; }, SLIDE_MS + 30);
  }

  function restartTimer() {
    window.clearInterval(row.timer);
    row.timer = window.setInterval(() => {
      if (row.paused || row.hover || row.focus || document.hidden || reduceMotion.matches) return;
      slide(1);
    }, STEP_MS);
  }

  function setPaused(paused) {
    row.paused = paused;
    dom.pause.setAttribute("aria-pressed", String(paused));
    dom.pause.setAttribute("aria-label", paused ? "Resume rotation" : "Pause rotation");
  }

  function updateControls() {
    dom.controls.hidden = !canMove();
    dom.pause.hidden = reduceMotion.matches; // nothing moves on its own, so nothing to pause
  }

  function initRow(items) {
    row.count = items.length;
    dom.track.replaceChildren(...items.map(tile));
    dom.carousel.hidden = !items.length;
    dom.prev.addEventListener("click", () => { slide(-1); restartTimer(); });
    dom.next.addEventListener("click", () => { slide(1); restartTimer(); });
    dom.pause.addEventListener("click", () => setPaused(!row.paused));
    const viewport = dom.carousel.querySelector(".carousel-viewport");
    viewport.addEventListener("mouseenter", () => { row.hover = true; });
    viewport.addEventListener("mouseleave", () => { row.hover = false; });
    dom.carousel.addEventListener("focusin", () => { row.focus = true; });
    dom.carousel.addEventListener("focusout", (event) => {
      if (!dom.carousel.contains(event.relatedTarget)) row.focus = false;
    });
    phone.addEventListener("change", updateControls);
    reduceMotion.addEventListener("change", updateControls);
    updateControls();
    restartTimer();
  }

  // ------------------------------------------------------------- start

  async function init() {
    let data;
    try {
      data = await SS.loadJSON("data/features.json");
    } catch (error) {
      return; // optional block: without data it stays hidden
    }
    const valid = (list) => (list || []).filter((f) => f && f.title && SS.safeUrl(f.url));
    leadItems = valid(data.lead);
    const rowItems = valid(data.row);
    if (!leadItems.length && !rowItems.length) return;
    if (leadItems.length) renderLead();
    initRow(rowItems);
    dom.section.hidden = false;
    dom.rule.hidden = false;
  }

  init();
})();
