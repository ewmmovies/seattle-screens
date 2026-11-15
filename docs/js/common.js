/* Shared helpers for every page (SPEC.md section 7.7).
   Scraped text is only ever inserted with textContent, never innerHTML. */
"use strict";

const SS = (() => {
  const TZ = "America/Los_Angeles";
  const STALE_HOURS = 36;
  const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
                  "August", "September", "October", "November", "December"];
  const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
  const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

  async function loadJSON(path) {
    const response = await fetch(path, { cache: "no-cache" });
    if (!response.ok) throw new Error(`${path}: ${response.status}`);
    return response.json();
  }

  /** Today's date in Seattle as "YYYY-MM-DD", whatever the viewer's own time zone. */
  function todayPT() {
    const parts = new Intl.DateTimeFormat("en-CA", {
      timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date());
    const get = (type) => parts.find((p) => p.type === type).value;
    return `${get("year")}-${get("month")}-${get("day")}`;
  }

  function isISODate(value) {
    if (!DATE_RE.test(value || "")) return false;
    const d = new Date(`${value}T12:00:00Z`);
    return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === value;
  }

  /** Calendar arithmetic on "YYYY-MM-DD" strings (done in UTC, so no DST surprises). */
  function addDays(iso, days) {
    const d = new Date(`${iso}T12:00:00Z`);
    d.setUTCDate(d.getUTCDate() + days);
    return d.toISOString().slice(0, 10);
  }

  function ordinal(n) {
    const tens = n % 100;
    if (tens >= 11 && tens <= 13) return `${n}th`;
    return n + ({ 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th");
  }

  /** "2026-11-14" -> "Saturday, November 14th 2026" */
  function formatLongDate(iso) {
    const d = new Date(`${iso}T12:00:00Z`);
    return `${DAYS[d.getUTCDay()]}, ${MONTHS[d.getUTCMonth()]} ${ordinal(d.getUTCDate())} ${d.getUTCFullYear()}`;
  }

  /** "2026-11-14" -> "Saturday, November 14" (search subheadings). */
  function formatShortDate(iso) {
    const d = new Date(`${iso}T12:00:00Z`);
    return `${DAYS[d.getUTCDay()]}, ${MONTHS[d.getUTCMonth()]} ${ordinal(d.getUTCDate())}`;
  }

  /** "19:05" -> "7:05PM" */
  function formatTime(hhmm) {
    const [h, m] = hhmm.split(":").map(Number);
    return `${h % 12 || 12}:${String(m).padStart(2, "0")}${h < 12 ? "AM" : "PM"}`;
  }

  /** ISO timestamp -> "NOV 13, 6:17 PM", in Seattle time. */
  function formatStamp(timestamp) {
    const text = new Intl.DateTimeFormat("en-US", {
      timeZone: TZ, month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
    }).format(new Date(timestamp));
    return text.toUpperCase();
  }

  /** Section 4.5: out of date when the run failed, the last success is old, or it never ran. */
  function sourceState(status, sourceId, now = Date.now()) {
    const entry = status && status.sources && status.sources[sourceId];
    const lastSuccess = entry && entry.last_success ? entry.last_success : null;
    const old = !lastSuccess || now - new Date(lastSuccess).getTime() > STALE_HOURS * 3600 * 1000;
    return { stale: !entry || entry.ok === false || old, lastSuccess };
  }

  function staleText(state) {
    return state.lastSuccess
      ? `Out of date · Last updated ${formatStamp(state.lastSuccess)}`
      : "Out of date · Not yet updated";
  }

  /** Small DOM builder: el("a", { href, className }, "text", childNode). Strings become text nodes. */
  function el(tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "className") node.className = value;
      else if (key === "dataset") Object.assign(node.dataset, value);
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value === true ? "" : value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  function externalLink(href, ...children) {
    return el("a", { href, target: "_blank", rel: "noopener" }, ...children);
  }

  /** Only http(s) links from scraped data are used. */
  function safeUrl(url) {
    return typeof url === "string" && /^https?:\/\//i.test(url) ? url : null;
  }

  /** A small film-strip mark, drawn for this site. Built with DOM calls, not innerHTML. */
  function filmGlyph() {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("viewBox", "0 0 13 11");
    svg.setAttribute("class", "film-glyph");
    svg.setAttribute("aria-hidden", "true");
    const add = (name, attrs) => {
      const shape = document.createElementNS(ns, name);
      for (const [k, v] of Object.entries(attrs)) shape.setAttribute(k, v);
      svg.append(shape);
    };
    add("rect", { x: "0.5", y: "0.5", width: "12", height: "10", fill: "none", stroke: "currentColor" });
    add("rect", { x: "3.5", y: "2.5", width: "6", height: "6", fill: "none", stroke: "currentColor" });
    for (const y of [1.5, 4.5, 7.5]) {
      add("rect", { x: "1.2", y: String(y), width: "1.2", height: "1.6", fill: "currentColor" });
      add("rect", { x: "10.6", y: String(y), width: "1.2", height: "1.6", fill: "currentColor" });
    }
    return svg;
  }

  function showMessage(container, text) {
    container.replaceChildren(el("p", { className: "message serif" }, text));
  }

  function showLoadError(container, error) {
    console.error(error);
    showMessage(container, "Listings could not be loaded.");
  }

  /** Mobile menu toggle (section 9.4). */
  function initMenu() {
    const button = document.querySelector(".menu-button");
    const nav = document.getElementById("site-nav");
    if (!button || !nav) return;
    button.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      button.setAttribute("aria-expanded", String(open));
      button.setAttribute("aria-label", open ? "Close menu" : "Open menu");
    });
  }

  document.addEventListener("DOMContentLoaded", initMenu);

  return {
    loadJSON, todayPT, isISODate, addDays, formatLongDate, formatShortDate, formatTime,
    formatStamp, sourceState, staleText, el, externalLink, safeUrl, filmGlyph,
    showMessage, showLoadError,
  };
})();
