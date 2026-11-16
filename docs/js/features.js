/* Happening Now block on the listings page (reworked 2026-11-15).

   Top slot: the Beacon's current series, then its Coming Soon programs (or a
   now-playing Beacon program if it has neither). Every 21 seconds it pushes the next
   one in from the right; the arrows under the image step it by hand.
   Row: SIFF programs/events, NWFF festivals/series and Beacon programs that are on
   now. Three tiles (one on phones); every 10 seconds the row pushes one tile from
   right to left. Arrows step it by hand. Both pause while the pointer or keyboard
   focus is on it, with the pause button, when the tab is hidden, and never moves on
   its own for people whose device asks for reduced motion.
   Images are the theaters' own, loaded from their servers. */
"use strict";

(() => {
  const { el } = SS;
  const ROW_STEP_MS = 10000; // the row of three
  const LEAD_STEP_MS = 21000; // the top slot (2026-11-15)
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

  // ------------------------------------------------------------- sliding

  /* One slider for both the top slot and the row. Items sit side by side in one or
     more tracks; a step pushes every track one item to the left (or right), then the
     item that left is moved to the other end, so the loop never runs out. Several
     tracks move together: the top slot slides its picture half and its text half
     separately, with the arrows standing still between them. */
  function slider({ tracks, perView, stepMs, onMove }) {
    const s = { busy: false, paused: false, hover: false, focus: false, timer: null, offset: 0 };
    const count = () => tracks[0].children.length;
    s.canMove = () => count() > perView();
    const shift = () => `translateX(${-100 / perView()}%)`;

    // Items outside the frame cannot be clicked or reached with the Tab key; without
    // this, tabbing to a hidden item makes the browser scroll the track out of place.
    s.markVisible = () => tracks.forEach((t) => [...t.children].forEach((item, i) => { item.inert = i >= perView(); }));

    const setAll = (transition, transform) => tracks.forEach((t) => {
      t.style.transition = transition;
      t.style.transform = transform;
    });

    s.slide = (direction) => {
      if (s.busy || !s.canMove()) return;
      s.busy = true;
      s.offset = (s.offset + direction + count()) % count();
      if (onMove) onMove(s.offset);
      const finish = () => {
        if (direction > 0) tracks.forEach((t) => t.appendChild(t.firstElementChild)); // the item that left goes to the back
        setAll("none", "translateX(0)");
        tracks.forEach((t) => void t.offsetWidth); // apply before the next move
        s.markVisible();
        s.busy = false;
      };
      if (direction < 0) { // bring the last item in from the left
        tracks.forEach((t) => t.insertBefore(t.lastElementChild, t.firstElementChild));
        setAll("none", shift());
        tracks.forEach((t) => void t.offsetWidth);
        s.markVisible();
      }
      if (reduceMotion.matches) { // no movement: change at once
        if (direction > 0) finish();
        else { setAll("none", "translateX(0)"); s.busy = false; }
        return;
      }
      setAll(`transform ${SLIDE_MS}ms ease`, direction > 0 ? shift() : "translateX(0)");
      window.setTimeout(direction > 0 ? finish : () => { s.busy = false; }, SLIDE_MS + 30);
    };

    s.restart = () => {
      window.clearInterval(s.timer);
      s.timer = window.setInterval(() => {
        if (s.paused || s.hover || s.focus || document.hidden || reduceMotion.matches) return;
        s.slide(1);
      }, stepMs);
    };

    // Pauses while the pointer is over `hoverArea` or keyboard focus is inside `focusArea`.
    s.watch = (hoverArea, focusArea) => {
      hoverArea.addEventListener("mouseenter", () => { s.hover = true; });
      hoverArea.addEventListener("mouseleave", () => { s.hover = false; });
      // Keyboard focus only: a mouse click on an arrow should not stop the rotation.
      focusArea.addEventListener("focusin", (event) => { s.focus = event.target.matches(":focus-visible"); });
      focusArea.addEventListener("focusout", (event) => {
        if (!focusArea.contains(event.relatedTarget)) s.focus = false;
      });
    };

    s.pauseButton = (button) => {
      const set = (paused) => {
        s.paused = paused;
        button.setAttribute("aria-pressed", String(paused));
        button.setAttribute("aria-label", paused ? "Resume rotation" : "Pause rotation");
      };
      set(false);
      button.addEventListener("click", () => set(!s.paused));
    };
    return s;
  }

  // ------------------------------------------------------------- top slot

  /* The Beacon's series, then its Coming Soon programs. Every 21 seconds the slot
     pushes the next one in from the right (same pauses as the row). Every item is the
     same height so nothing jumps: the title is one line, the description is held to
     two lines (longer text ends with an ellipsis) and the months are one line. The
     arrows, counter and pause button stay put between the picture and the text. */
  function initLead(items) {
    const top = el("div", { className: "lead-track" });
    const bottom = el("div", { className: "lead-track" });
    for (const item of items) {
      top.appendChild(el("div", { className: "lead-slide" },
        el("h3", { className: "feature-title serif" }, link(item, { className: "feature-link", title: item.title }, item.title)),
        el("div", { className: "feature-frame" },
          el("span", { className: "side-label kind" }, kindLabel(item)),
          link(item, { className: "feature-link", tabindex: "-1", "aria-hidden": "true" }, image(item) || el("span", { className: "feature-image" })),
          el("span", { className: "side-label when" }, item.when || ""))));
      const description = item.description || item.byline || "";
      bottom.appendChild(el("div", { className: "lead-slide feature-text" },
        el("p", { className: item.description ? "feature-description serif" : "feature-description byline", title: description }, description),
        el("p", { className: "byline feature-months" }, item.months ? `Scheduled ${item.months}` : "")));
    }
    const many = items.length > 1;
    const count = el("span", { className: "lead-count", "aria-live": "polite" }, many ? `1 / ${items.length}` : "");
    const lead = slider({
      tracks: [top, bottom],
      perView: () => 1,
      stepMs: LEAD_STEP_MS,
      onMove: (i) => { count.textContent = `${i + 1} / ${items.length}`; },
    });
    const prev = el("button", { className: "mini-button mini-prev", type: "button", "aria-label": "Previous", hidden: !many,
      onclick: () => { lead.slide(-1); lead.restart(); } });
    const next = el("button", { className: "mini-button mini-next", type: "button", "aria-label": "Next", hidden: !many,
      onclick: () => { lead.slide(1); lead.restart(); } });
    const pause = el("button", { className: "mini-button mini-pause", type: "button", hidden: !many || reduceMotion.matches });
    const box = el("div", { className: "feature-lead", "aria-roledescription": "carousel", "aria-label": "Featured at the Beacon" },
      el("div", { className: "lead-viewport" }, top),
      el("div", { className: "lead-controls" }, prev, count, next, pause),
      el("div", { className: "lead-viewport" }, bottom));
    dom.lead.replaceChildren(box);
    lead.markVisible();
    lead.pauseButton(pause);
    lead.watch(box, box);
    reduceMotion.addEventListener("change", () => { pause.hidden = !many || reduceMotion.matches; });
    if (many) lead.restart();
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

  function initRow(items) {
    dom.track.replaceChildren(...items.map(tile));
    dom.carousel.hidden = !items.length;
    const row = slider({ tracks: [dom.track], perView: () => (phone.matches ? 1 : 3), stepMs: ROW_STEP_MS });
    const updateControls = () => {
      dom.controls.hidden = !row.canMove();
      dom.pause.hidden = reduceMotion.matches; // nothing moves on its own, so nothing to pause
    };
    row.markVisible();
    dom.prev.addEventListener("click", () => { row.slide(-1); row.restart(); });
    dom.next.addEventListener("click", () => { row.slide(1); row.restart(); });
    row.pauseButton(dom.pause);
    row.watch(dom.carousel.querySelector(".carousel-viewport"), dom.carousel);
    phone.addEventListener("change", () => { row.markVisible(); updateControls(); });
    reduceMotion.addEventListener("change", updateControls);
    updateControls();
    row.restart();
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
    const leadItems = valid(data.lead);
    const rowItems = valid(data.row);
    if (!leadItems.length && !rowItems.length) return;
    if (leadItems.length) initLead(leadItems);
    initRow(rowItems);
    dom.section.hidden = false;
    dom.rule.hidden = false;
  }

  init();
})();
